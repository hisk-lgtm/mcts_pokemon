from __future__ import annotations

from copy import deepcopy

from battle_engine.backends.base import BackendTurnResult, BattleBackend
from battle_engine.mcts import MCTSAgent, MCTSConfig
from battle_engine.model import Action, PokemonSet


class TinyBackend(BattleBackend):
    name = "python"

    def __init__(self, *, last_p1_action: int | None = None) -> None:
        self.last_p1_action = last_p1_action
        self.actions = [Action("move", 0), Action("move", 1)]

    def reset(self, team1: list[PokemonSet], team2: list[PokemonSet], *, seed: int = 1) -> dict:
        self.last_p1_action = None
        return self.state_summary()

    def legal_actions(self, player: int) -> list[Action]:
        return list(self.actions)

    def step(self, p1_action: Action, p2_action: Action, *, debug_damage: bool = False) -> BackendTurnResult:
        self.last_p1_action = p1_action.index
        return BackendTurnResult(state_summary=self.state_summary(), log_lines=[], winner=None)

    def needs_replacement(self, player: int) -> bool:
        return False

    def replace_fainted(self, player: int, new_index: int) -> BackendTurnResult:
        return BackendTurnResult(state_summary=self.state_summary(), log_lines=[], winner=None)

    def clone(self) -> "TinyBackend":
        return deepcopy(self)

    def state_summary(self) -> dict:
        return {
            "turn": 1,
            "last_p1_action": self.last_p1_action,
            "p1": {"hp": 10, "max_hp": 10, "alive": 1},
            "p2": {"hp": 10, "max_hp": 10, "alive": 1},
        }

    def winner(self) -> int | None:
        return None


def test_backend_mcts_uses_root_policy_priors():
    backend = TinyBackend()
    agent = MCTSAgent(MCTSConfig(simulations=1, max_depth=0, exploration=1.4))

    def priors(summary: dict, player: int, actions: list[Action]) -> dict[Action, float]:
        return {action: (0.99 if action.index == 1 else 0.01) for action in actions}

    result = agent.search_backend(backend, 1, policy_prior=priors)

    assert result.action == Action("move", 1)
    stat_by_action = {stat.action: stat for stat in result.stats}
    assert stat_by_action[Action("move", 1)].prior == 0.99
    assert stat_by_action[Action("move", 0)].prior == 0.01


def test_backend_mcts_uses_leaf_value_fn():
    backend = TinyBackend()
    agent = MCTSAgent(MCTSConfig(simulations=12, max_depth=0, exploration=0.1))

    def value(summary: dict, player: int) -> float:
        return 1.0 if summary.get("last_p1_action") == 1 else -1.0

    result = agent.search_backend(backend, 1, value_fn=value)

    assert result.action == Action("move", 1)
    stat_by_action = {stat.action: stat for stat in result.stats}
    assert stat_by_action[Action("move", 1)].mean_value > 0.0
    assert stat_by_action[Action("move", 0)].mean_value < 0.0