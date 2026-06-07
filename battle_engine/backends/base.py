from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal

from ..model import Action, PokemonSet


BackendName = Literal["python", "showdown"]


@dataclass
class BackendTurnResult:
    """Backend-neutral result from resolving one simultaneous-action turn."""
    state_summary: dict[str, Any]
    log_lines: list[str]
    winner: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class BattleBackend(ABC):
    """Small simulator interface used by agents.

    The goal is to keep MCTS/training code from depending directly on one
    battle engine. Our current Python simulator is one backend. A local
    Pokémon Showdown / PokeMMO-aware bridge can become another.
    """

    name: BackendName

    @abstractmethod
    def reset(
        self,
        team1: list[PokemonSet],
        team2: list[PokemonSet],
        *,
        seed: int = 1,
    ) -> dict[str, Any]:
        """Start a new battle and return a state summary."""

    @abstractmethod
    def legal_actions(self, player: int) -> list[Action]:
        """Return legal actions for the current state."""

    @abstractmethod
    def step(
        self,
        p1_action: Action,
        p2_action: Action,
        *,
        debug_damage: bool = False,
    ) -> BackendTurnResult:
        """Resolve one turn."""

    @abstractmethod
    def needs_replacement(self, player: int) -> bool:
        """Whether a player must choose a free replacement."""

    @abstractmethod
    def replace_fainted(self, player: int, new_index: int) -> BackendTurnResult:
        """Perform a free replacement after fainting."""

    @abstractmethod
    def clone(self) -> "BattleBackend":
        """Return an independent copy of this backend at the same battle state.

        MCTS simulations need to branch from the current root without mutating
        the real battle. Backend implementations may choose the cheapest
        available representation: the Python backend deep-copies BattleState,
        while the first Showdown backend copies the replay history.
        """

    @abstractmethod
    def state_summary(self) -> dict[str, Any]:
        """Return a compact, serializable view of the current state."""

    @abstractmethod
    def winner(self) -> int | None:
        """Return winner: 1, 2, 0 for draw, or None if ongoing."""


class BackendUnavailableError(RuntimeError):
    """Raised when an optional backend cannot be used in this environment."""
