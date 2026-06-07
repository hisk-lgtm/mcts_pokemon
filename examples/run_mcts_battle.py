from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import random

from battle_engine import legal_actions, make_battle, needs_replacement, replace_fainted, step
from battle_engine.backends import BackendUnavailableError, BattleBackend, create_backend
from battle_engine.features import action_label, state_summary
from battle_engine.mcts import MCTSAgent, MCTSConfig, MCTSResult
from battle_engine.team_builder import default_compendium_path, load_set_pool, random_team


def _chosen_label(result: MCTSResult) -> str:
    for stat in result.stats:
        if stat.action == result.action:
            return stat.label
    return f"{result.action.kind}[{result.action.index}]"


def _handle_state_replacements(state, rng: random.Random):
    changed = True
    while changed and state.winner is None:
        changed = False
        for player in (1, 2):
            if not needs_replacement(state, player):
                continue
            switches = [a for a in legal_actions(state, player) if a.kind == "switch"]
            if not switches:
                continue
            action = rng.choice(switches)
            state, log = replace_fainted(state, player, action.index)
            print(f"P{player} replacement: {action_label(state, player, action)}")
            if log.all_lines():
                print(log)
            changed = True
    return state


def _handle_backend_replacements(backend: BattleBackend, rng: random.Random) -> None:
    changed = True
    while changed and backend.winner() is None:
        changed = False
        for player in (1, 2):
            if not backend.needs_replacement(player):
                continue
            switches = [a for a in backend.legal_actions(player) if a.kind == "switch"]
            if not switches:
                continue
            action = rng.choice(switches)
            result = backend.replace_fainted(player, action.index)
            print(f"P{player} replacement: switch[{action.index}]")
            if result.log_lines:
                print("\n".join(result.log_lines))
            changed = True


def _run_state_battle(args: argparse.Namespace, team1, team2, rng: random.Random) -> None:
    state = make_battle(team1, team2, seed=args.seed)
    mcts = MCTSAgent(MCTSConfig(simulations=args.sims, max_depth=args.depth), rng=rng)

    for _ in range(args.turns):
        state = _handle_state_replacements(state, rng)
        if state.winner is not None:
            break

        print("STATE", state_summary(state))
        p1_result = mcts.search(state, 1)
        p1 = p1_result.action
        p2_result = mcts.search(state, 2)
        p2 = p2_result.action
        print("P1:", action_label(state, 1, p1))
        print("P2:", action_label(state, 2, p2))

        state, log = step(state, p1, p2, debug_damage=args.debug_damage)
        print(log)
        print()

    print("Final:", state_summary(state))


def _run_backend_battle(args: argparse.Namespace, team1, team2, rng: random.Random) -> None:
    backend = create_backend(
        args.backend,
        team1,
        team2,
        seed=args.seed,
        showdown_root=args.showdown_root,
        node_bin=args.node_bin,
        format_id=args.format,
        timeout_seconds=args.timeout,
    )
    mcts = MCTSAgent(MCTSConfig(simulations=args.sims, max_depth=args.depth), rng=rng)

    for _ in range(args.turns):
        _handle_backend_replacements(backend, rng)
        if backend.winner() is not None:
            break

        print("STATE", backend.state_summary())
        p1_result = mcts.search_backend(backend, 1)
        p1 = p1_result.action
        p2_result = mcts.search_backend(backend, 2)
        p2 = p2_result.action
        print("P1:", _chosen_label(p1_result))
        print("P2:", _chosen_label(p2_result))

        result = backend.step(p1, p2, debug_damage=args.debug_damage)
        if result.log_lines:
            print("\n".join(result.log_lines))
        print()

    print("Final:", backend.state_summary())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--turns", type=int, default=20)
    parser.add_argument("--sims", type=int, default=64)
    parser.add_argument("--depth", type=int, default=20)
    parser.add_argument(
        "--backend",
        choices=["state", "python", "showdown"],
        default="state",
        help="state keeps the old direct BattleState path; python/showdown use BattleBackend.",
    )
    parser.add_argument("--showdown-root", default=None, help="Local Pokemon Showdown checkout. Defaults to SHOWDOWN_ROOT.")
    parser.add_argument("--node-bin", default="node")
    parser.add_argument("--format", default="gen5ou", help="Showdown format id for --backend showdown.")
    parser.add_argument("--timeout", type=int, default=30, help="Seconds per Showdown bridge call.")
    parser.add_argument("--debug-damage", action="store_true")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    pool = load_set_pool(default_compendium_path(), expand_variants=True, supported_only=True)
    team1 = random_team(pool, rng=rng)
    team2 = random_team(pool, rng=rng)

    try:
        if args.backend == "state":
            _run_state_battle(args, team1, team2, rng)
        else:
            _run_backend_battle(args, team1, team2, rng)
    except BackendUnavailableError as exc:
        raise SystemExit(f"Backend unavailable: {exc}") from exc


if __name__ == "__main__":
    main()
