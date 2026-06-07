from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
import random
from pathlib import Path

from .features import action_features, dot, state_features
from .model import Action, BattleState, PokemonSet
from .team_roles import team_features


def _stable_sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1 / (1 + z)
    z = math.exp(x)
    return z / (1 + z)


@dataclass
class LinearPolicyValueAgent:
    policy_weights: dict[str, float] = field(default_factory=dict)
    value_weights: dict[str, float] = field(default_factory=dict)
    team_weights: dict[str, float] = field(default_factory=dict)
    learning_rate: float = 0.05
    name: str = "linear-agent"
    elo: float = 1000.0

    def score_action(self, state: BattleState, player: int, action: Action) -> float:
        return dot(self.policy_weights, action_features(state, player, action))

    def action_priors(self, state: BattleState, player: int, actions: list[Action]) -> dict[Action, float]:
        if not actions:
            return {}
        scores = [self.score_action(state, player, action) for action in actions]
        max_score = max(scores)
        exps = [math.exp(max(-40.0, min(40.0, s - max_score))) for s in scores]
        total = sum(exps) or 1.0
        return {action: exps[i] / total for i, action in enumerate(actions)}

    def evaluate(self, state: BattleState, player: int) -> float:
        raw = dot(self.value_weights, state_features(state, player))
        return 2 * _stable_sigmoid(raw) - 1

    def choose_action(
        self,
        state: BattleState,
        player: int,
        actions: list[Action],
        *,
        temperature: float = 0.0,
        rng: random.Random | None = None,
    ) -> Action:
        if not actions:
            raise ValueError("No legal actions to choose from.")
        rng = rng or random.Random()
        scores = [self.score_action(state, player, action) for action in actions]
        if temperature <= 0:
            return actions[max(range(len(actions)), key=lambda i: scores[i])]

        max_score = max(scores)
        exps = [math.exp((s - max_score) / max(temperature, 1e-6)) for s in scores]
        total = sum(exps)
        r = rng.random() * total
        c = 0.0
        for action, weight in zip(actions, exps):
            c += weight
            if c >= r:
                return action
        return actions[-1]

    def update_policy_toward(self, state: BattleState, player: int, chosen: Action, legal: list[Action]) -> None:
        if not legal:
            return
        priors = self.action_priors(state, player, legal)
        chosen_features = action_features(state, player, chosen)

        # Multiclass logistic gradient: chosen features minus expected features.
        expected: dict[str, float] = {}
        for action, prob in priors.items():
            for key, value in action_features(state, player, action).items():
                expected[key] = expected.get(key, 0.0) + prob * value

        for key, value in chosen_features.items():
            grad = value - expected.get(key, 0.0)
            self.policy_weights[key] = self.policy_weights.get(key, 0.0) + self.learning_rate * grad

    def update_value(self, state: BattleState, player: int, target_value: float) -> None:
        features = state_features(state, player)
        pred = self.evaluate(state, player)
        error = target_value - pred
        for key, value in features.items():
            self.value_weights[key] = self.value_weights.get(key, 0.0) + self.learning_rate * error * value


    def score_team(self, team: list[PokemonSet]) -> float:
        return dot(self.team_weights, team_features(team))

    def evaluate_team(self, team: list[PokemonSet]) -> float:
        return 2 * _stable_sigmoid(self.score_team(team)) - 1

    def choose_team(
        self,
        candidate_teams: list[list[PokemonSet]],
        *,
        temperature: float = 0.0,
        rng: random.Random | None = None,
    ) -> list[PokemonSet]:
        if not candidate_teams:
            raise ValueError("No candidate teams to choose from.")
        rng = rng or random.Random()
        scores = [self.score_team(team) for team in candidate_teams]
        if temperature <= 0:
            return candidate_teams[max(range(len(candidate_teams)), key=lambda i: scores[i])]

        max_score = max(scores)
        exps = [math.exp((score - max_score) / max(temperature, 1e-6)) for score in scores]
        total = sum(exps)
        r = rng.random() * total
        c = 0.0
        for team, weight in zip(candidate_teams, exps):
            c += weight
            if c >= r:
                return team
        return candidate_teams[-1]

    def update_team_value(self, team: list[PokemonSet], target_value: float) -> None:
        features = team_features(team)
        pred = self.evaluate_team(team)
        error = target_value - pred
        for key, value in features.items():
            self.team_weights[key] = self.team_weights.get(key, 0.0) + self.learning_rate * error * value

    def mutate(self, *, scale: float = 0.01, rng: random.Random | None = None) -> "LinearPolicyValueAgent":
        rng = rng or random.Random()
        clone = LinearPolicyValueAgent(
            policy_weights=dict(self.policy_weights),
            value_weights=dict(self.value_weights),
            team_weights=dict(self.team_weights),
            learning_rate=self.learning_rate,
            name=self.name + "-mutant",
            elo=self.elo,
        )
        action_keys = set(clone.policy_weights) | set(clone.value_weights) | {"bias", "active_hp_diff", "move_power", "move_super_effective", "move_immune", "action_is_switch"}
        for key in action_keys:
            clone.policy_weights[key] = clone.policy_weights.get(key, 0.0) + rng.gauss(0, scale)
            clone.value_weights[key] = clone.value_weights.get(key, 0.0) + rng.gauss(0, scale)

        team_keys = set(clone.team_weights) | {
            "team_bias",
            "team_has_hazard_setter",
            "team_has_hazard_removal",
            "team_has_speed_control",
            "team_has_pivot",
            "team_has_physical_attacker",
            "team_has_special_attacker",
            "team_missing_hazard_removal",
            "team_missing_speed_control",
            "team_no_ground_immunity",
            "team_role_diversity",
        }
        for key in team_keys:
            clone.team_weights[key] = clone.team_weights.get(key, 0.0) + rng.gauss(0, scale)
        return clone

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "learning_rate": self.learning_rate,
            "policy_weights": self.policy_weights,
            "value_weights": self.value_weights,
            "team_weights": self.team_weights,
            "elo": self.elo,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LinearPolicyValueAgent":
        return cls(
            policy_weights=dict(data.get("policy_weights", {})),
            value_weights=dict(data.get("value_weights", {})),
            team_weights=dict(data.get("team_weights", {})),
            learning_rate=float(data.get("learning_rate", 0.05)),
            name=data.get("name", "linear-agent"),
            elo=float(data.get("elo", 1000.0)),
        )

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "LinearPolicyValueAgent":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
