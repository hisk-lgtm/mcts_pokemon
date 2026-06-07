from __future__ import annotations

from dataclasses import asdict
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any

from ..model import Action, PokemonSet
from .base import BattleBackend, BackendTurnResult, BackendUnavailableError


DEFAULT_BRIDGE = Path(__file__).resolve().parents[2] / "tools" / "showdown_bridge" / "run_battle.mjs"


def showdown_set_text(pokeset: PokemonSet) -> str:
    """Convert a PokemonSet into Pokémon Showdown importable text."""
    evs = " / ".join(
        f"{value} {label}"
        for key, label in (
            ("hp", "HP"),
            ("atk", "Atk"),
            ("def", "Def"),
            ("spa", "SpA"),
            ("spd", "SpD"),
            ("spe", "Spe"),
        )
        if (value := pokeset.evs.get(key, 0))
    )
    ivs = " / ".join(
        f"{value} {label}"
        for key, label in (
            ("hp", "HP"),
            ("atk", "Atk"),
            ("def", "Def"),
            ("spa", "SpA"),
            ("spd", "SpD"),
            ("spe", "Spe"),
        )
        if (value := pokeset.ivs.get(key, 31)) != 31
    )

    lines = [f"{pokeset.species} @ {pokeset.item}" if pokeset.item else pokeset.species]
    if pokeset.ability:
        lines.append(f"Ability: {pokeset.ability}")
    if pokeset.level != 100:
        lines.append(f"Level: {pokeset.level}")
    if evs:
        lines.append(f"EVs: {evs}")
    if ivs:
        lines.append(f"IVs: {ivs}")
    if pokeset.nature:
        lines.append(f"{pokeset.nature} Nature")
    for move in pokeset.moves:
        lines.append(f"- {move}")
    return "\n".join(lines)


def showdown_team_text(team: list[PokemonSet]) -> str:
    return "\n\n".join(showdown_set_text(p) for p in team)


def _action_to_payload(action: Action | None) -> dict[str, Any] | None:
    if action is None:
        return None
    return {"kind": action.kind, "index": action.index}


def _payload_to_actions(raw_actions: list[dict[str, Any]]) -> list[Action]:
    actions: list[Action] = []
    for raw in raw_actions:
        kind = raw.get("kind")
        index = raw.get("index")
        if kind in {"move", "switch"} and isinstance(index, int):
            actions.append(Action(kind, index))
    return actions


class ShowdownBattleBackend(BattleBackend):
    """Adapter around a local Pokémon Showdown-style simulator.

    This backend deliberately does not talk to the public MMO Showdown server.
    It shells out to ``tools/showdown_bridge/run_battle.mjs`` with a full battle
    payload. The first implementation is stateless: every call replays the
    teams plus prior choices into a fresh BattleStream, which keeps it simple
    and deterministic while the bridge is still being proven out.
    """

    name = "showdown"

    def __init__(
        self,
        *,
        bridge_script: str | Path | None = None,
        showdown_root: str | Path | None = None,
        node_bin: str = "node",
        format_id: str = "gen5ou",
        timeout_seconds: int = 30,
    ) -> None:
        self.bridge_script = Path(bridge_script) if bridge_script else DEFAULT_BRIDGE
        self.showdown_root = Path(showdown_root) if showdown_root else (
            Path(os.environ["SHOWDOWN_ROOT"]) if os.environ.get("SHOWDOWN_ROOT") else None
        )
        self.node_bin = node_bin
        self.format_id = format_id
        self.timeout_seconds = timeout_seconds
        self._last_summary: dict[str, Any] = {}
        self._last_raw: dict[str, Any] = {}
        self._winner: int | None = None
        self._team1: list[PokemonSet] | None = None
        self._team2: list[PokemonSet] | None = None
        self._seed: int = 1
        self._history: list[dict[str, Any]] = []
        self._legal_actions: dict[int, list[Action]] = {1: [], 2: []}
        self._needs_replacement: dict[int, bool] = {1: False, 2: False}

    def check_available(self) -> dict[str, Any]:
        if shutil.which(self.node_bin) is None:
            return {
                "available": False,
                "reason": f"Node executable not found: {self.node_bin}",
                "node_bin": self.node_bin,
                "bridge_script": str(self.bridge_script),
                "showdown_root": str(self.showdown_root) if self.showdown_root else None,
            }
        if not self.bridge_script.exists():
            return {
                "available": False,
                "reason": f"Bridge script not found: {self.bridge_script}",
                "node_bin": self.node_bin,
                "bridge_script": str(self.bridge_script),
                "showdown_root": str(self.showdown_root) if self.showdown_root else None,
            }

        cmd = [self.node_bin, str(self.bridge_script), "--check"]
        env = os.environ.copy()
        if self.showdown_root is not None:
            env["SHOWDOWN_ROOT"] = str(self.showdown_root)
        proc = subprocess.run(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=20,
        )
        try:
            payload = json.loads(proc.stdout or "{}")
        except json.JSONDecodeError:
            payload = {"available": False, "reason": proc.stderr or proc.stdout}
        payload.setdefault("returncode", proc.returncode)
        payload.setdefault("node_bin", self.node_bin)
        payload.setdefault("bridge_script", str(self.bridge_script))
        return payload

    def _not_wired(self) -> BackendUnavailableError:
        check = self.check_available()
        return BackendUnavailableError(
            "Showdown backend is not ready for battle stepping. "
            f"Availability check: {json.dumps(check, sort_keys=True)}"
        )

    def _fallback_reset_summary(self, team1: list[PokemonSet], team2: list[PokemonSet], seed: int) -> dict[str, Any]:
        return {
            "backend": "showdown",
            "format": self.format_id,
            "seed": seed,
            "team1_importable": showdown_team_text(team1),
            "team2_importable": showdown_team_text(team2),
            "available": self.check_available(),
        }

    def _bridge_env(self) -> dict[str, str]:
        env = os.environ.copy()
        if self.showdown_root is not None:
            env["SHOWDOWN_ROOT"] = str(self.showdown_root)
        return env

    def _bridge_payload(self, history: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        if self._team1 is None or self._team2 is None:
            raise RuntimeError("Backend has not been reset with teams yet.")
        return {
            "format": self.format_id,
            "seed": self._seed,
            "team1": [asdict(pokeset) for pokeset in self._team1],
            "team2": [asdict(pokeset) for pokeset in self._team2],
            "actions": history if history is not None else self._history,
        }

    def _run_bridge(self, history: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        if shutil.which(self.node_bin) is None or not self.bridge_script.exists():
            raise self._not_wired()

        cmd = [self.node_bin, str(self.bridge_script)]
        proc = subprocess.run(
            cmd,
            input=json.dumps(self._bridge_payload(history)),
            env=self._bridge_env(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=self.timeout_seconds,
        )
        try:
            payload = json.loads(proc.stdout or "{}")
        except json.JSONDecodeError as exc:
            raise BackendUnavailableError(
                "Showdown bridge returned non-JSON output. "
                f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
            ) from exc

        if proc.returncode != 0 or not payload.get("ok"):
            reason = payload.get("reason") or proc.stderr or "unknown bridge failure"
            raise BackendUnavailableError(f"Showdown bridge failed: {reason}")

        self._last_raw = payload
        self._last_summary = dict(payload.get("state_summary") or {})
        self._winner = payload.get("winner")
        self._legal_actions = {
            1: _payload_to_actions(payload.get("legal_actions", {}).get("p1", [])),
            2: _payload_to_actions(payload.get("legal_actions", {}).get("p2", [])),
        }
        self._needs_replacement = {
            1: bool(payload.get("needs_replacement", {}).get("p1", False)),
            2: bool(payload.get("needs_replacement", {}).get("p2", False)),
        }
        return payload

    def reset(
        self,
        team1: list[PokemonSet],
        team2: list[PokemonSet],
        *,
        seed: int = 1,
    ) -> dict[str, Any]:
        self._team1 = list(team1)
        self._team2 = list(team2)
        self._seed = seed
        self._history = []
        self._winner = None
        self._legal_actions = {1: [], 2: []}
        self._needs_replacement = {1: False, 2: False}

        check = self.check_available()
        if not check.get("available"):
            self._last_summary = self._fallback_reset_summary(team1, team2, seed)
            return self.state_summary()

        payload = self._run_bridge([])
        summary = self.state_summary()
        summary["team1_importable"] = showdown_team_text(team1)
        summary["team2_importable"] = showdown_team_text(team2)
        return summary

    def legal_actions(self, player: int) -> list[Action]:
        if player not in {1, 2}:
            raise ValueError(f"player must be 1 or 2, got {player!r}")
        if not self._last_raw and self._team1 is not None and self._team2 is not None:
            raise self._not_wired()
        return list(self._legal_actions[player])

    def step(
        self,
        p1_action: Action,
        p2_action: Action,
        *,
        debug_damage: bool = False,
    ) -> BackendTurnResult:
        next_history = self._history + [{"p1": _action_to_payload(p1_action), "p2": _action_to_payload(p2_action)}]
        payload = self._run_bridge(next_history)
        self._history = next_history
        return BackendTurnResult(
            state_summary=self.state_summary(),
            log_lines=list(payload.get("log_lines", [])),
            winner=self.winner(),
            raw=payload.get("raw", {}),
        )

    def needs_replacement(self, player: int) -> bool:
        if player not in {1, 2}:
            raise ValueError(f"player must be 1 or 2, got {player!r}")
        if not self._last_raw and self._team1 is not None and self._team2 is not None:
            raise self._not_wired()
        return self._needs_replacement[player]

    def clone(self) -> "ShowdownBattleBackend":
        cloned = ShowdownBattleBackend(
            bridge_script=self.bridge_script,
            showdown_root=self.showdown_root,
            node_bin=self.node_bin,
            format_id=self.format_id,
            timeout_seconds=self.timeout_seconds,
        )
        cloned._last_summary = copy.deepcopy(self._last_summary)
        cloned._last_raw = copy.deepcopy(self._last_raw)
        cloned._winner = self._winner
        cloned._team1 = copy.deepcopy(self._team1)
        cloned._team2 = copy.deepcopy(self._team2)
        cloned._seed = self._seed
        cloned._history = copy.deepcopy(self._history)
        cloned._legal_actions = copy.deepcopy(self._legal_actions)
        cloned._needs_replacement = copy.deepcopy(self._needs_replacement)
        return cloned

    def replace_fainted(self, player: int, new_index: int) -> BackendTurnResult:
        if player not in {1, 2}:
            raise ValueError(f"player must be 1 or 2, got {player!r}")
        event = {"p1": None, "p2": None}
        event[f"p{player}"] = _action_to_payload(Action("switch", new_index))
        next_history = self._history + [event]
        payload = self._run_bridge(next_history)
        self._history = next_history
        return BackendTurnResult(
            state_summary=self.state_summary(),
            log_lines=list(payload.get("log_lines", [])),
            winner=self.winner(),
            raw=payload.get("raw", {}),
        )

    def state_summary(self) -> dict[str, Any]:
        return dict(self._last_summary)

    def winner(self) -> int | None:
        return self._winner
