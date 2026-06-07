from __future__ import annotations

import argparse
import random
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from battle_engine import Action, legal_actions, make_battle, needs_replacement, replace_fainted, step, evaluate_material
from battle_engine.team_builder import default_compendium_path, load_set_pool, random_team


def format_mon(mon) -> str:
    status = f" {mon.status}" if mon.status else ""
    return f"{mon.species} @ {mon.item or 'No Item'} HP {mon.hp}/{mon.max_hp}{status}"


def print_team(label: str, team_sets) -> None:
    print(f"\n{label}")
    for i, s in enumerate(team_sets, 1):
        print(f"  {i}. {s.species} @ {s.item} | {s.ability} | {s.nature}")
        print(f"     {', '.join(s.moves)}")


def print_state(state) -> None:
    print("\n" + "=" * 72)
    print(f"Turn {state.field.turn} | Weather: {state.field.weather or 'none'} | Eval P1: {evaluate_material(state, 1):+.3f}")
    print(f"P1 active: {format_mon(state.p1.active_mon())}")
    print(f"P2 active: {format_mon(state.p2.active_mon())}")
    print(f"P1 hazards: SR={state.p1.side.stealth_rock} Spikes={state.p1.side.spikes} TSpikes={state.p1.side.toxic_spikes}")
    print(f"P2 hazards: SR={state.p2.side.stealth_rock} Spikes={state.p2.side.spikes} TSpikes={state.p2.side.toxic_spikes}")


def describe_action(state, player: int, action: Action) -> str:
    team = state.p1 if player == 1 else state.p2
    if action.kind == "move":
        return f"move: {team.active_mon().moves[action.index]}"
    return f"switch: {team.mons[action.index].species} ({team.mons[action.index].hp}/{team.mons[action.index].max_hp})"


def choose_action(state, player: int) -> Action:
    actions = legal_actions(state, player)
    print(f"\nPlayer {player} choose action:")
    for i, action in enumerate(actions, 1):
        print(f"  {i}. {describe_action(state, player, action)}")

    while True:
        raw = input(f"P{player}> ").strip().lower()
        if raw in {"q", "quit", "exit"}:
            raise KeyboardInterrupt
        try:
            index = int(raw) - 1
        except ValueError:
            print("Enter a number, or q to quit.")
            continue
        if 0 <= index < len(actions):
            return actions[index]
        print("Choice out of range.")



def handle_replacements(state):
    while state.winner is None and any(needs_replacement(state, player) for player in (1, 2)):
        for player in (1, 2):
            while state.winner is None and needs_replacement(state, player):
                print_state(state)
                print(f"Player {player} must choose a free replacement.")
                action = choose_action(state, player)
                if action.kind != "switch":
                    print("Replacement must be a switch.")
                    continue
                state, log = replace_fainted(state, player, action.index)
                print("\nReplacement log:")
                print(log)
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description="Manual two-player battle tester for the local PokeMMO engine.")
    parser.add_argument("--sets", type=Path, default=default_compendium_path(), help="Path to Showdown-style set file.")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducible teams.")
    parser.add_argument("--no-expand", action="store_true", help="Use only leftmost concrete set from each block.")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    pool = load_set_pool(args.sets, expand_variants=not args.no_expand, supported_only=True)
    if len(pool) < 12:
        raise SystemExit(f"Need at least 12 supported sets, found {len(pool)}.")

    p1_sets = random_team(pool, rng=rng, size=6, unique_species=True)
    p2_sets = random_team(pool, rng=rng, size=6, unique_species=True)

    print_team("Player 1 random team", p1_sets)
    print_team("Player 2 random team", p2_sets)

    state = make_battle(p1_sets, p2_sets, seed=args.seed or 1)
    try:
        state = handle_replacements(state)
        while state.winner is None:
            print_state(state)
            p1_action = choose_action(state, 1)
            p2_action = choose_action(state, 2)
            state, log = step(state, p1_action, p2_action)
            print("\nTurn log:")
            print(log)
            state = handle_replacements(state)
    except KeyboardInterrupt:
        print("\nBattle tester closed.")
        return

    print_state(state)
    print(f"Winner: Player {state.winner}" if state.winner else "Draw.")


if __name__ == "__main__":
    main()
