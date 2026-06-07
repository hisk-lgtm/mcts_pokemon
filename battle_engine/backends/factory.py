from __future__ import annotations

from pathlib import Path
from typing import Any

from ..model import PokemonSet
from .base import BattleBackend, BackendName
from .python_backend import PythonBattleBackend
from .showdown_backend import ShowdownBattleBackend


def create_backend(
    name: BackendName,
    team1: list[PokemonSet] | None = None,
    team2: list[PokemonSet] | None = None,
    *,
    seed: int = 1,
    showdown_root: str | Path | None = None,
    node_bin: str = "node",
    format_id: str = "gen5ou",
    timeout_seconds: int = 30,
) -> BattleBackend:
    """Create a battle backend by name and optionally reset it with teams.

    This keeps examples and future CLIs from each growing their own backend
    selection logic. The Python backend ignores Showdown-specific options.
    """
    if name == "python":
        backend: BattleBackend = PythonBattleBackend()
    elif name == "showdown":
        backend = ShowdownBattleBackend(
            showdown_root=showdown_root,
            node_bin=node_bin,
            format_id=format_id,
            timeout_seconds=timeout_seconds,
        )
    else:
        raise ValueError(f"Unknown backend {name!r}. Expected 'python' or 'showdown'.")

    if (team1 is None) != (team2 is None):
        raise ValueError("team1 and team2 must both be provided, or neither.")
    if team1 is not None and team2 is not None:
        backend.reset(team1, team2, seed=seed)
    return backend
