from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
from dataclasses import dataclass
from typing import Any

from battle_engine.backends import BackendUnavailableError, BattleBackend, create_backend
from battle_engine.model import Action, PokemonSet
from battle_engine.sample_sets import TEAM_BALANCE_A, TEAM_BALANCE_B, TYRANITAR_CB, DRAGONITE_DD


@dataclass(frozen=True)
class ChosenActions:
    python_action: Action
    showdown_action: Action
    note: str | None = None


def _hp_fraction(hp: Any, max_hp: Any) -> float | None:
    try:
        hp_value = float(hp)
        max_value = float(max_hp)
    except (TypeError, ValueError):
        return None
    if max_value <= 0:
        return None
    return round(hp_value / max_value, 4)


def _active_showdown_mon(side: dict[str, Any]) -> dict[str, Any]:
    mons = side.get("mons") or []
    active_index = side.get("active_index")
    if isinstance(active_index, int) and 0 <= active_index < len(mons):
        return dict(mons[active_index])
    for mon in mons:
        if mon.get("active"):
            return dict(mon)
    return {}


def compact_summary(summary: dict[str, Any]) -> dict[str, Any]:
    """Normalize Python and Showdown summaries into a comparable shape.

    This deliberately keeps only high-signal fields. The two engines do not
    expose identical internals yet, so diagnostics should compare stable
    surface facts instead of pretending the raw payloads are equivalent.
    """

    def side_summary(player: str) -> dict[str, Any]:
        side = dict(summary.get(player) or {})
        if "mons" in side:
            active = _active_showdown_mon(side)
            hp = active.get("hp")
            max_hp = active.get("max_hp")
            return {
                "active": side.get("active") or active.get("species"),
                "active_index": side.get("active_index"),
                "hp": hp,
                "max_hp": max_hp,
                "hp_fraction": _hp_fraction(hp, max_hp),
                "status": active.get("status"),
                "alive": side.get("alive_count"),
                "conditions": side.get("side_conditions") or {},
                "needs_replacement": side.get("needs_replacement", False),
            }

        hp = side.get("hp")
        max_hp = side.get("max_hp")
        return {
            "active": side.get("active"),
            "active_index": side.get("active_index"),
            "hp": hp,
            "max_hp": max_hp,
            "hp_fraction": _hp_fraction(hp, max_hp),
            "status": side.get("status"),
            "alive": side.get("alive"),
            "conditions": side.get("hazards") or {},
            "needs_replacement": side.get("needs_replacement", False),
        }

    return {
        "turn": summary.get("turn"),
        "winner": summary.get("winner"),
        "weather": summary.get("weather"),
        "terrain": summary.get("terrain"),
        "p1": side_summary("p1"),
        "p2": side_summary("p2"),
    }


def diff_compact_summaries(
    python_summary: dict[str, Any],
    showdown_summary: dict[str, Any],
) -> list[str]:
    """Return short, user-facing notes for obvious summary differences."""
    notes: list[str] = []
    for key in ("turn", "winner", "weather", "terrain"):
        py_value = python_summary.get(key)
        sd_value = showdown_summary.get(key)
        if py_value != sd_value:
            notes.append(f"{key}: python={py_value!r}, showdown={sd_value!r}")

    for player in ("p1", "p2"):
        py_side = python_summary.get(player, {})
        sd_side = showdown_summary.get(player, {})
        for key in ("active", "alive", "status", "needs_replacement"):
            py_value = py_side.get(key)
            sd_value = sd_side.get(key)
            if py_value != sd_value:
                notes.append(f"{player}.{key}: python={py_value!r}, showdown={sd_value!r}")

        py_hp = py_side.get("hp_fraction")
        sd_hp = sd_side.get("hp_fraction")
        if py_hp is not None and sd_hp is not None and abs(py_hp - sd_hp) > 0.01:
            notes.append(
                f"{player}.hp_fraction: python={py_hp:.3f}, showdown={sd_hp:.3f}"
            )

        py_conditions = py_side.get("conditions") or {}
        sd_conditions = sd_side.get("conditions") or {}
        if bool(py_conditions) != bool(sd_conditions):
            notes.append(
                f"{player}.conditions: python={py_conditions!r}, showdown={sd_conditions!r}"
            )
    return notes


def _format_action(action: Action) -> str:
    return f"{action.kind}[{action.index}]"


def _choose_shared_action(
    python_backend: BattleBackend,
    showdown_backend: BattleBackend,
    player: int,
    preferred: Action,
) -> ChosenActions:
    py_legal = python_backend.legal_actions(player)
    sd_legal = showdown_backend.legal_actions(player)
    py_set = set(py_legal)
    sd_set = set(sd_legal)
    shared = py_set & sd_set

    if preferred in shared:
        return ChosenActions(preferred, preferred)

    move_candidates = sorted(
        (action for action in shared if action.kind == "move"),
        key=lambda action: action.index,
    )
    if move_candidates:
        action = move_candidates[0]
        return ChosenActions(
            action,
            action,
            f"P{player}: preferred {_format_action(preferred)} unavailable; using shared {_format_action(action)}",
        )

    switch_candidates = sorted(
        (action for action in shared if action.kind == "switch"),
        key=lambda action: action.index,
    )
    if switch_candidates:
        action = switch_candidates[0]
        return ChosenActions(
            action,
            action,
            f"P{player}: preferred {_format_action(preferred)} unavailable; using shared {_format_action(action)}",
        )

    if not py_legal or not sd_legal:
        raise RuntimeError(
            f"P{player} has no legal action in one backend: "
            f"python={py_legal}, showdown={sd_legal}"
        )

    py_action = py_legal[0]
    sd_action = sd_legal[0]
    return ChosenActions(
        py_action,
        sd_action,
        (
            f"P{player}: no shared legal action; "
            f"python uses {_format_action(py_action)}, showdown uses {_format_action(sd_action)}"
        ),
    )


def _handle_replacements(
    python_backend: BattleBackend,
    showdown_backend: BattleBackend,
) -> list[str]:
    notes: list[str] = []
    changed = True
    while changed and python_backend.winner() is None and showdown_backend.winner() is None:
        changed = False
        for player in (1, 2):
            py_needs = python_backend.needs_replacement(player)
            sd_needs = showdown_backend.needs_replacement(player)
            if py_needs != sd_needs:
                notes.append(
                    f"P{player}: replacement need diverged: "
                    f"python={py_needs}, showdown={sd_needs}"
                )
            if not (py_needs or sd_needs):
                continue

            preferred = Action("switch", 0)
            chosen = _choose_shared_action(python_backend, showdown_backend, player, preferred)
            if player == 1:
                python_backend.replace_fainted(1, chosen.python_action.index)
                showdown_backend.replace_fainted(1, chosen.showdown_action.index)
            else:
                python_backend.replace_fainted(2, chosen.python_action.index)
                showdown_backend.replace_fainted(2, chosen.showdown_action.index)
            if chosen.note:
                notes.append(chosen.note)
            changed = True
    return notes


def _print_summary_pair(
    turn_label: str,
    python_summary: dict[str, Any],
    showdown_summary: dict[str, Any],
) -> None:
    print(turn_label)
    print("  Python :", python_summary)
    print("  Showdown:", showdown_summary)
    diffs = diff_compact_summaries(python_summary, showdown_summary)
    if diffs:
        print("  Differences:")
        for diff in diffs:
            print(f"    - {diff}")
    else:
        print("  Differences: none in compact summary")


def _build_teams(mode: str) -> tuple[list[PokemonSet], list[PokemonSet]]:
    if mode == "single":
        return [TYRANITAR_CB], [DRAGONITE_DD]
    if mode == "balance":
        return list(TEAM_BALANCE_A), list(TEAM_BALANCE_B)
    raise ValueError(f"Unknown team mode: {mode}")


def run_comparison(args: argparse.Namespace) -> int:
    team1, team2 = _build_teams(args.teams)
    python_backend = create_backend("python", team1, team2, seed=args.seed)
    showdown_backend = create_backend(
        "showdown",
        team1,
        team2,
        seed=args.seed,
        showdown_root=args.showdown_root,
        node_bin=args.node_bin,
        format_id=args.format,
        timeout_seconds=args.timeout,
    )

    check_available = getattr(showdown_backend, "check_available", None)
    if callable(check_available):
        check = check_available()
        if not check.get("available"):
            raise BackendUnavailableError(
                f"Availability check failed: {check.get('reason')}. "
                "Set SHOWDOWN_ROOT or pass --showdown-root."
            )

    _print_summary_pair(
        "Initial state",
        compact_summary(python_backend.state_summary()),
        compact_summary(showdown_backend.state_summary()),
    )

    for turn in range(1, args.turns + 1):
        replacement_notes = _handle_replacements(python_backend, showdown_backend)
        if replacement_notes:
            print(f"Turn {turn} replacement notes:")
            for note in replacement_notes:
                print(f"  - {note}")

        if python_backend.winner() is not None or showdown_backend.winner() is not None:
            break

        p1 = _choose_shared_action(
            python_backend, showdown_backend, 1, Action("move", args.p1_move)
        )
        p2 = _choose_shared_action(
            python_backend, showdown_backend, 2, Action("move", args.p2_move)
        )
        for chosen in (p1, p2):
            if chosen.note:
                print(f"Turn {turn} action note: {chosen.note}")

        print(
            f"Turn {turn} actions: "
            f"P1 python={_format_action(p1.python_action)} showdown={_format_action(p1.showdown_action)}; "
            f"P2 python={_format_action(p2.python_action)} showdown={_format_action(p2.showdown_action)}"
        )
        py_result = python_backend.step(p1.python_action, p2.python_action)
        sd_result = showdown_backend.step(p1.showdown_action, p2.showdown_action)
        _print_summary_pair(
            f"After turn {turn}",
            compact_summary(py_result.state_summary),
            compact_summary(sd_result.state_summary),
        )
        print()

    print(
        "Final raw winners:",
        {"python": python_backend.winner(), "showdown": showdown_backend.winner()},
    )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare Python and Showdown backend summaries turn by turn."
    )
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--turns", type=int, default=3)
    parser.add_argument("--teams", choices=["single", "balance"], default="single")
    parser.add_argument("--p1-move", type=int, default=0, help="Preferred zero-based move index for P1.")
    parser.add_argument("--p2-move", type=int, default=0, help="Preferred zero-based move index for P2.")
    parser.add_argument(
        "--showdown-root",
        default=None,
        help="Local Pokemon Showdown checkout. Defaults to SHOWDOWN_ROOT.",
    )
    parser.add_argument("--node-bin", default="node")
    parser.add_argument("--format", default="gen5ou", help="Showdown format id.")
    parser.add_argument("--timeout", type=int, default=30, help="Seconds per Showdown bridge call.")
    args = parser.parse_args()

    try:
        raise SystemExit(run_comparison(args))
    except BackendUnavailableError as exc:
        raise SystemExit(f"Showdown backend unavailable: {exc}") from exc


if __name__ == "__main__":
    main()
