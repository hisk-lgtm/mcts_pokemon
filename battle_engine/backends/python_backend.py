from __future__ import annotations

from typing import Any

from ..engine import legal_actions as engine_legal_actions
from ..engine import needs_replacement as engine_needs_replacement
from ..engine import replace_fainted as engine_replace_fainted
from ..engine import step as engine_step
from ..features import state_summary as engine_state_summary
from ..model import Action, BattleState, PokemonSet, make_battle
from .base import BattleBackend, BackendTurnResult


def _move_id(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def _move_metadata(move_name: str) -> dict[str, Any]:
    from ..data import MOVES

    data = MOVES.get(move_name)
    if data is None:
        return {"id": _move_id(move_name), "name": move_name}
    return {
        "id": _move_id(move_name),
        "name": move_name,
        "type": data.type,
        "category": data.category,
        "base_power": data.power,
        "accuracy": data.accuracy,
        "priority": data.priority,
        "contact": data.contact,
        "effect": data.effect,
    }


def _pokemon_types(species: str) -> list[str]:
    from ..data import SPECIES

    data = SPECIES.get(species)
    return list(data.types) if data is not None else []


def _switch_metadata(state: BattleState, player: int, index: int) -> dict[str, Any]:
    team = state.p1 if player == 1 else state.p2
    if index < 0 or index >= len(team.mons):
        return {}
    mon = team.mons[index]
    return {
        "species": mon.species,
        "types": _pokemon_types(mon.species),
        "level": mon.set.level,
        "stats": dict(mon.stats),
        "boosts": dict(mon.boosts),
        "ability": mon.ability,
        "item": mon.item,
        "hp": mon.hp,
        "max_hp": mon.max_hp,
        "hp_fraction": mon.hp / mon.max_hp if mon.max_hp > 0 else 0.0,
        "status": mon.status,
        "fainted": mon.fainted or mon.hp <= 0,
    }


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
        state = self._require_state()
        team = state.p1 if player == 1 else state.p2
        active = team.active_mon()
        enriched: list[Action] = []
        for action in engine_legal_actions(state, player):
            if action.kind == "move" and 0 <= action.index < len(active.moves):
                enriched.append(Action(action.kind, action.index, _move_metadata(active.moves[action.index])))
            elif action.kind == "switch":
                enriched.append(Action(action.kind, action.index, _switch_metadata(state, player, action.index)))
            else:
                enriched.append(action)
        return enriched

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
