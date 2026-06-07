from __future__ import annotations

from typing import Any

from ..engine import legal_actions as engine_legal_actions
from ..engine import needs_replacement as engine_needs_replacement
from ..engine import replace_fainted as engine_replace_fainted
from ..engine import step as engine_step
from ..features import state_summary as engine_state_summary
from ..model import Action, BattleState, PokemonSet, make_battle
from .base import BattleBackend, BackendTurnResult


class PythonBattleBackend(BattleBackend):
    """Adapter around the current Python battle engine."""

    name = "python"

    def __init__(
        self,
        team1: list[PokemonSet] | None = None,
        team2: list[PokemonSet] | None = None,
        *,
        seed: int = 1,
    ) -> None:
        self.state: BattleState | None = None
        if team1 is not None and team2 is not None:
            self.reset(team1, team2, seed=seed)

    def _require_state(self) -> BattleState:
        if self.state is None:
            raise RuntimeError("Backend has not been reset with teams yet.")
        return self.state

    def reset(
        self,
        team1: list[PokemonSet],
        team2: list[PokemonSet],
        *,
        seed: int = 1,
    ) -> dict[str, Any]:
        self.state = make_battle(team1, team2, seed=seed)
        return self.state_summary()

    def legal_actions(self, player: int) -> list[Action]:
        return engine_legal_actions(self._require_state(), player)

    def step(
        self,
        p1_action: Action,
        p2_action: Action,
        *,
        debug_damage: bool = False,
    ) -> BackendTurnResult:
        self.state, log = engine_step(
            self._require_state(),
            p1_action,
            p2_action,
            debug_damage=debug_damage,
        )
        return BackendTurnResult(
            state_summary=self.state_summary(),
            log_lines=log.all_lines(),
            winner=self.winner(),
            raw={"turn_log": log.lines, "debug_lines": log.debug_lines},
        )

    def needs_replacement(self, player: int) -> bool:
        return engine_needs_replacement(self._require_state(), player)

    def clone(self) -> "PythonBattleBackend":
        cloned = PythonBattleBackend()
        cloned.state = self.state.clone() if self.state is not None else None
        return cloned

    def replace_fainted(self, player: int, new_index: int) -> BackendTurnResult:
        self.state, log = engine_replace_fainted(self._require_state(), player, new_index)
        return BackendTurnResult(
            state_summary=self.state_summary(),
            log_lines=log.all_lines(),
            winner=self.winner(),
            raw={"turn_log": log.lines, "debug_lines": log.debug_lines},
        )

    def state_summary(self) -> dict[str, Any]:
        return engine_state_summary(self._require_state())

    def winner(self) -> int | None:
        return self._require_state().winner
