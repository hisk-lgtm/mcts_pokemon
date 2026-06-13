from __future__ import annotations

from dataclasses import dataclass, field
import math
import random
from typing import Any, Callable

from .backends.base import BattleBackend
from .engine import evaluate_material, legal_actions, needs_replacement, replace_fainted, step
from .features import action_label
from .model import Action, BattleState




def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _action_payload(action: Action) -> dict:
    payload = {"kind": action.kind, "index": action.index}
    if action.metadata:
        payload.update(action.metadata)
    return payload


def _backend_action_label(summary: dict, player: int, action: Action) -> str:
    metadata = getattr(action, "metadata", {}) or {}
    if action.kind == "move":
        move_name = metadata.get("name") or metadata.get("move") or metadata.get("id")
        if move_name:
            return f"move:{move_name}"
    elif action.kind == "switch":
        species = metadata.get("species")
        if species:
            return f"switch:{species}"

    side = summary.get(f"p{player}", {})
    mons = side.get("mons") if isinstance(side, dict) else None

    if action.kind == "move":
        if isinstance(mons, list):
            active_index = side.get("active_index", 0)
            if isinstance(active_index, int) and 0 <= active_index < len(mons):
                moves = mons[active_index].get("moves", []) if isinstance(mons[active_index], dict) else []
                if action.index < len(moves):
                    move = moves[action.index]
                    if isinstance(move, dict):
                        return f"move:{move.get('move') or move.get('id') or action.index}"
        return f"move[{action.index}]"

    if isinstance(mons, list) and action.index < len(mons):
        mon = mons[action.index]
        if isinstance(mon, dict):
            return f"switch:{mon.get('species') or mon.get('name') or action.index}"
    return f"switch[{action.index}]"


def _summary_mon_score(mon: dict) -> float:
    hp = _safe_float(mon.get("hp"))
    max_hp = _safe_float(mon.get("max_hp"))
    fainted = bool(mon.get("fainted")) or hp <= 0
    if fainted or max_hp <= 0:
        return 0.0
    return 1.0 + hp / max_hp


def _summary_side_score(side: dict) -> float:
    mons = side.get("mons")
    if isinstance(mons, list):
        return sum(_summary_mon_score(mon) for mon in mons if isinstance(mon, dict))

    alive = _safe_float(side.get("alive_count", side.get("alive", 0)))
    hp = _safe_float(side.get("hp"))
    max_hp = _safe_float(side.get("max_hp"))
    active_fraction = hp / max_hp if max_hp > 0 and hp > 0 else 0.0
    return alive + active_fraction

def _normalize_backend_priors(actions: list[Action], priors: dict[Action, float]) -> dict[Action, float]:
    positive = {action: max(0.0, float(priors.get(action, 0.0))) for action in actions}
    total = sum(positive.values())
    if total <= 0.0:
        return {action: 1.0 / len(actions) for action in actions} if actions else {}
    return {action: value / total for action, value in positive.items()}


def _call_backend_policy_prior(
    policy_prior: Callable[[dict[str, Any], int, list[Action]], dict[Action, float]] | None,
    summary: dict[str, Any],
    player: int,
    actions: list[Action],
) -> dict[Action, float]:
    if policy_prior is None:
        return {}
    try:
        priors = policy_prior(summary, player, actions)
    except Exception:
        return {}
    if not isinstance(priors, dict):
        return {}

    cleaned: dict[Action, float] = {}
    for action in actions:
        try:
            cleaned[action] = float(priors.get(action, 0.0))
        except (TypeError, ValueError):
            cleaned[action] = 0.0
    return cleaned


def _call_backend_value_fn(
    value_fn: Callable[[dict[str, Any], int], float] | None,
    summary: dict[str, Any],
    player: int,
) -> float | None:
    if value_fn is None:
        return None
    try:
        return max(-1.0, min(1.0, float(value_fn(summary, player))))
    except Exception:
        return None

def _evaluate_backend_material(backend: BattleBackend, player: int) -> float:
    summary = backend.state_summary()
    own = _summary_side_score(summary.get(f"p{player}", {}))
    opp = _summary_side_score(summary.get(f"p{3 - player}", {}))
    if own + opp == 0:
        return 0.0
    return (own - opp) / (own + opp)

@dataclass
class MCTSConfig:
    simulations: int = 64
    max_depth: int = 30
    exploration: float = 1.4
    rollout_temperature: float = 1.0
    player: int = 1


@dataclass
class RootActionStats:
    action: Action
    label: str
    visits: int = 0
    total_value: float = 0.0
    prior: float = 0.0

    @property
    def mean_value(self) -> float:
        return self.total_value / self.visits if self.visits else 0.0


@dataclass
class MCTSResult:
    action: Action
    stats: list[RootActionStats]
    simulations: int

    def as_log_dict(self) -> dict:
        return {
            "chosen": _action_payload(self.action),
            "simulations": self.simulations,
            "stats": [
                {
                    "label": s.label,
                    "visits": s.visits,
                    "mean_value": round(s.mean_value, 4),
                    "prior": round(s.prior, 4),
                }
                for s in sorted(self.stats, key=lambda x: x.visits, reverse=True)
            ],
        }


class MCTSAgent:
    def __init__(
        self,
        config: MCTSConfig | None = None,
        *,
        policy_prior: Callable[[BattleState, int, list[Action]], dict[Action, float]] | None = None,
        value_fn: Callable[[BattleState, int], float] | None = None,
        rng: random.Random | None = None,
    ) -> None:
        self.config = config or MCTSConfig()
        self.policy_prior = policy_prior
        self.value_fn = value_fn
        self.rng = rng or random.Random()

    def search(self, state: BattleState, player: int | None = None) -> MCTSResult:
        player = player or self.config.player
        root_actions = legal_actions(state, player)
        if not root_actions:
            raise ValueError("No legal actions at MCTS root.")

        priors = self.policy_prior(state, player, root_actions) if self.policy_prior else {}
        if not priors:
            priors = {action: 1.0 / len(root_actions) for action in root_actions}

        stats = {
            action: RootActionStats(
                action=action,
                label=action_label(state, player, action),
                prior=priors.get(action, 0.0),
            )
            for action in root_actions
        }

        for _ in range(self.config.simulations):
            action = self._select_root_action(stats)
            value = self._simulate_after_root_action(state, player, action)
            stats[action].visits += 1
            stats[action].total_value += value

        best = max(stats.values(), key=lambda s: (s.visits, s.mean_value, s.prior))
        return MCTSResult(action=best.action, stats=list(stats.values()), simulations=self.config.simulations)

    def search_backend(
        self,
        backend: BattleBackend,
        player: int | None = None,
        *,
        policy_prior: Callable[[dict[str, Any], int, list[Action]], dict[Action, float]] | None = None,
        value_fn: Callable[[dict[str, Any], int], float] | None = None,
    ) -> MCTSResult:
        """Run root-action MCTS using a mutable BattleBackend.

        Backend search can optionally use backend-neutral policy priors and leaf
        values. A trained BackendLinearPolicyValueAgent already exposes methods
        with the right shape: pass agent.action_priors and agent.evaluate.
        """
        player = player or self.config.player
        root_actions = backend.legal_actions(player)
        if not root_actions:
            raise ValueError("No legal actions at MCTS root.")

        summary = backend.state_summary()
        raw_priors = _call_backend_policy_prior(policy_prior, summary, player, root_actions)
        priors = _normalize_backend_priors(root_actions, raw_priors)
        stats = {
            action: RootActionStats(
                action=action,
                label=_backend_action_label(summary, player, action),
                prior=priors.get(action, 0.0),
            )
            for action in root_actions
        }

        for _ in range(self.config.simulations):
            action = self._select_root_action(stats)
            value = self._simulate_after_root_backend_action(
                backend,
                player,
                action,
                policy_prior=policy_prior,
                value_fn=value_fn,
            )
            stats[action].visits += 1
            stats[action].total_value += value

        best = max(stats.values(), key=lambda s: (s.visits, s.mean_value, s.prior))
        return MCTSResult(action=best.action, stats=list(stats.values()), simulations=self.config.simulations)
    def _select_root_action(self, stats: dict[Action, RootActionStats]) -> Action:
        total_visits = sum(s.visits for s in stats.values()) + 1
        best_score = -1e18
        best_action = next(iter(stats))
        for action, stat in stats.items():
            q = stat.mean_value
            u = self.config.exploration * stat.prior * math.sqrt(total_visits) / (1 + stat.visits)
            noise = self.rng.random() * 1e-9
            score = q + u + noise
            if score > best_score:
                best_score = score
                best_action = action
        return best_action

    def _simulate_after_root_action(self, state: BattleState, player: int, root_action: Action) -> float:
        sim = state.clone()
        opponent = 3 - player
        opponent_action = self._sample_action(sim, opponent)
        if player == 1:
            sim, _ = step(sim, root_action, opponent_action)
        else:
            sim, _ = step(sim, opponent_action, root_action)
        return self._rollout(sim, player)

    def _rollout(self, state: BattleState, player: int) -> float:
        sim = state
        for _ in range(self.config.max_depth):
            if sim.winner is not None:
                if sim.winner == 0:
                    return 0.0
                return 1.0 if sim.winner == player else -1.0

            sim = self._handle_replacements_randomly(sim)

            p1_actions = legal_actions(sim, 1)
            p2_actions = legal_actions(sim, 2)
            if not p1_actions or not p2_actions:
                return evaluate_material(sim, player)

            a1 = self._sample_action(sim, 1)
            a2 = self._sample_action(sim, 2)
            sim, _ = step(sim, a1, a2)

        if self.value_fn is not None:
            return self.value_fn(sim, player)
        return evaluate_material(sim, player)

    def _handle_replacements_randomly(self, state: BattleState) -> BattleState:
        sim = state
        changed = True
        while changed and sim.winner is None:
            changed = False
            for player in (1, 2):
                if needs_replacement(sim, player):
                    actions = legal_actions(sim, player)
                    switches = [a for a in actions if a.kind == "switch"]
                    if switches:
                        sim, _ = replace_fainted(sim, player, self.rng.choice(switches).index)
                        changed = True
        return sim

    def _sample_action(self, state: BattleState, player: int) -> Action:
        actions = legal_actions(state, player)
        if not actions:
            raise ValueError(f"No legal actions for player {player}.")
        if self.policy_prior:
            priors = self.policy_prior(state, player, actions)
            total = sum(max(0.0, priors.get(a, 0.0)) for a in actions)
            if total > 0:
                r = self.rng.random() * total
                c = 0.0
                for action in actions:
                    c += max(0.0, priors.get(action, 0.0))
                    if c >= r:
                        return action
        return self.rng.choice(actions)

    def _simulate_after_root_backend_action(
        self,
        backend: BattleBackend,
        player: int,
        root_action: Action,
        *,
        policy_prior: Callable[[dict[str, Any], int, list[Action]], dict[Action, float]] | None = None,
        value_fn: Callable[[dict[str, Any], int], float] | None = None,
    ) -> float:
        sim = backend.clone()
        opponent = 3 - player
        opponent_actions = sim.legal_actions(opponent)
        if not opponent_actions:
            return self._evaluate_backend_leaf(sim, player, value_fn=value_fn)

        opponent_action = self._sample_backend_action(sim, opponent, policy_prior=policy_prior)
        if player == 1:
            sim.step(root_action, opponent_action)
        else:
            sim.step(opponent_action, root_action)
        return self._rollout_backend(sim, player, policy_prior=policy_prior, value_fn=value_fn)

    def _rollout_backend(
        self,
        backend: BattleBackend,
        player: int,
        *,
        policy_prior: Callable[[dict[str, Any], int, list[Action]], dict[Action, float]] | None = None,
        value_fn: Callable[[dict[str, Any], int], float] | None = None,
    ) -> float:
        sim = backend
        for _ in range(self.config.max_depth):
            winner = sim.winner()
            if winner is not None:
                if winner == 0:
                    return 0.0
                return 1.0 if winner == player else -1.0

            self._handle_backend_replacements_randomly(sim)

            p1_actions = sim.legal_actions(1)
            p2_actions = sim.legal_actions(2)
            if not p1_actions or not p2_actions:
                return self._evaluate_backend_leaf(sim, player, value_fn=value_fn)

            sim.step(
                self._sample_backend_action(sim, 1, policy_prior=policy_prior),
                self._sample_backend_action(sim, 2, policy_prior=policy_prior),
            )

        winner = sim.winner()
        if winner is not None:
            if winner == 0:
                return 0.0
            return 1.0 if winner == player else -1.0
        return self._evaluate_backend_leaf(sim, player, value_fn=value_fn)

    def _sample_backend_action(
        self,
        backend: BattleBackend,
        player: int,
        *,
        policy_prior: Callable[[dict[str, Any], int, list[Action]], dict[Action, float]] | None = None,
    ) -> Action:
        actions = backend.legal_actions(player)
        if not actions:
            raise ValueError(f"No legal actions for player {player}.")
        priors = _normalize_backend_priors(
            actions,
            _call_backend_policy_prior(policy_prior, backend.state_summary(), player, actions),
        )
        if priors:
            r = self.rng.random()
            c = 0.0
            for action in actions:
                c += priors.get(action, 0.0)
                if c >= r:
                    return action
        return self.rng.choice(actions)

    def _evaluate_backend_leaf(
        self,
        backend: BattleBackend,
        player: int,
        *,
        value_fn: Callable[[dict[str, Any], int], float] | None = None,
    ) -> float:
        value = _call_backend_value_fn(value_fn, backend.state_summary(), player)
        if value is not None:
            return value
        return _evaluate_backend_material(backend, player)

    def _rollout_backend(self, backend: BattleBackend, player: int) -> float:
        sim = backend
        for _ in range(self.config.max_depth):
            winner = sim.winner()
            if winner is not None:
                if winner == 0:
                    return 0.0
                return 1.0 if winner == player else -1.0

            self._handle_backend_replacements_randomly(sim)

            p1_actions = sim.legal_actions(1)
            p2_actions = sim.legal_actions(2)
            if not p1_actions or not p2_actions:
                return _evaluate_backend_material(sim, player)

            sim.step(self.rng.choice(p1_actions), self.rng.choice(p2_actions))

        winner = sim.winner()
        if winner is not None:
            if winner == 0:
                return 0.0
            return 1.0 if winner == player else -1.0
        return _evaluate_backend_material(sim, player)

    def _handle_backend_replacements_randomly(self, backend: BattleBackend) -> None:
        changed = True
        while changed and backend.winner() is None:
            changed = False
            for player in (1, 2):
                if backend.needs_replacement(player):
                    switches = [a for a in backend.legal_actions(player) if a.kind == "switch"]
                    if switches:
                        backend.replace_fainted(player, self.rng.choice(switches).index)
                        changed = True
