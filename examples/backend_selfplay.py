from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import json
import random
from dataclasses import dataclass
from typing import Any, TextIO

from battle_engine.backends import BackendUnavailableError, BattleBackend, create_backend
from battle_engine.mcts import MCTSAgent, MCTSConfig, MCTSResult
from battle_engine.model import Action, PokemonSet
from battle_engine.sample_sets import TEAM_BALANCE_A, TEAM_BALANCE_B, TYRANITAR_CB, DRAGONITE_DD
from battle_engine.team_builder import default_compendium_path, load_set_pool, random_team

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class GameTeams:
    team1: list[PokemonSet]
    team2: list[PokemonSet]


def action_to_payload(action: Action) -> dict[str, Any]:
    payload: dict[str, Any] = {"kind": action.kind, "index": action.index}
    if action.metadata:
        payload.update(action.metadata)
    return payload


def mcts_result_to_payload(result: MCTSResult) -> dict[str, Any]:
    payload = result.as_log_dict()
    payload["chosen"] = action_to_payload(result.action)
    payload["stats"] = [
        {
            **stat,
            "action": action_to_payload(root_stat.action),
        }
        for stat, root_stat in zip(payload.get("stats", []), sorted(result.stats, key=lambda x: x.visits, reverse=True))
    ]
    return payload


def value_target(final_winner: int | None, player: int) -> float:
    if final_winner is None or final_winner == 0:
        return 0.0
    return 1.0 if final_winner == player else -1.0


def _team_species(team: list[PokemonSet]) -> list[str]:
    return [mon.species for mon in team]


def _build_teams(mode: str, rng: random.Random) -> GameTeams:
    if mode == "single":
        return GameTeams([TYRANITAR_CB], [DRAGONITE_DD])
    if mode == "balance":
        return GameTeams(list(TEAM_BALANCE_A), list(TEAM_BALANCE_B))
    if mode == "random":
        pool = load_set_pool(default_compendium_path(), expand_variants=True, supported_only=True)
        return GameTeams(random_team(pool, rng=rng), random_team(pool, rng=rng))
    raise ValueError(f"Unknown team mode: {mode}")


def _handle_replacements(backend: BattleBackend, rng: random.Random) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    changed = True
    while changed and backend.winner() is None:
        changed = False
        for player in (1, 2):
            if not backend.needs_replacement(player):
                continue
            switches = [action for action in backend.legal_actions(player) if action.kind == "switch"]
            if not switches:
                continue
            action = rng.choice(switches)
            result = backend.replace_fainted(player, action.index)
            events.append(
                {
                    "player": player,
                    "action": action_to_payload(action),
                    "winner_after": result.winner,
                    "log_lines": result.log_lines,
                }
            )
            changed = True
    return events


def _decision_record(
    *,
    backend_name: str,
    game_id: int,
    seed: int,
    turn_index: int,
    player: int,
    state_summary: dict[str, Any],
    legal_actions: list[Action],
    result: MCTSResult,
    team1: list[PokemonSet],
    team2: list[PokemonSet],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "decision",
        "backend": backend_name,
        "game_id": game_id,
        "seed": seed,
        "turn_index": turn_index,
        "simulator_turn": state_summary.get("turn"),
        "player": player,
        "team1_species": _team_species(team1),
        "team2_species": _team_species(team2),
        "state_summary": state_summary,
        "legal_actions": [action_to_payload(action) for action in legal_actions],
        "chosen_action": action_to_payload(result.action),
        "mcts": mcts_result_to_payload(result),
        "final_winner": None,
        "value_target": None,
    }


def play_backend_game(
    *,
    backend_name: str,
    team1: list[PokemonSet],
    team2: list[PokemonSet],
    game_id: int,
    seed: int,
    turns: int,
    sims: int,
    depth: int,
    rng: random.Random,
    showdown_root: str | None = None,
    node_bin: str = "node",
    format_id: str = "gen5ou",
    timeout: int = 30,
) -> list[dict[str, Any]]:
    backend = create_backend(
        backend_name,  # type: ignore[arg-type]
        team1,
        team2,
        seed=seed,
        showdown_root=showdown_root,
        node_bin=node_bin,
        format_id=format_id,
        timeout_seconds=timeout,
    )
    agent = MCTSAgent(MCTSConfig(simulations=sims, max_depth=depth), rng=rng)
    records: list[dict[str, Any]] = []

    for turn_index in range(1, turns + 1):
        replacement_events = _handle_replacements(backend, rng)
        if replacement_events and records:
            records[-1].setdefault("replacement_events_after_turn", []).extend(replacement_events)

        if backend.winner() is not None:
            break

        state_summary = backend.state_summary()
        p1_legal = backend.legal_actions(1)
        p2_legal = backend.legal_actions(2)
        if not p1_legal or not p2_legal:
            break

        p1_result = agent.search_backend(backend, 1)
        p2_result = agent.search_backend(backend, 2)

        records.append(
            _decision_record(
                backend_name=backend_name,
                game_id=game_id,
                seed=seed,
                turn_index=turn_index,
                player=1,
                state_summary=state_summary,
                legal_actions=p1_legal,
                result=p1_result,
                team1=team1,
                team2=team2,
            )
        )
        records.append(
            _decision_record(
                backend_name=backend_name,
                game_id=game_id,
                seed=seed,
                turn_index=turn_index,
                player=2,
                state_summary=state_summary,
                legal_actions=p2_legal,
                result=p2_result,
                team1=team1,
                team2=team2,
            )
        )

        turn_result = backend.step(p1_result.action, p2_result.action)
        records[-2]["turn_result"] = {
            "winner_after": turn_result.winner,
            "log_lines": turn_result.log_lines,
        }
        records[-1]["turn_result"] = {
            "winner_after": turn_result.winner,
            "log_lines": turn_result.log_lines,
        }

        if backend.winner() is not None:
            break

    final_winner = backend.winner()
    for record in records:
        player = int(record["player"])
        record["final_winner"] = final_winner
        record["value_target"] = value_target(final_winner, player)
    return records


def write_jsonl(records: list[dict[str, Any]], handle: TextIO) -> None:
    for record in records:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def run_selfplay(args: argparse.Namespace) -> int:
    rng = random.Random(args.seed)
    all_records: list[dict[str, Any]] = []

    for game_id in range(args.games):
        game_seed = args.seed + game_id
        game_rng = random.Random(game_seed)
        teams = _build_teams(args.teams, game_rng)
        records = play_backend_game(
            backend_name=args.backend,
            team1=teams.team1,
            team2=teams.team2,
            game_id=game_id,
            seed=game_seed,
            turns=args.turns,
            sims=args.sims,
            depth=args.depth,
            rng=rng,
            showdown_root=args.showdown_root,
            node_bin=args.node_bin,
            format_id=args.format,
            timeout=args.timeout,
        )
        all_records.extend(records)

    if args.out == "-":
        write_jsonl(all_records, sys.stdout)
    else:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as handle:
            write_jsonl(all_records, handle)
        print(f"Wrote {len(all_records)} decision records to {out_path}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run backend self-play and write training-shaped decision records as JSONL."
    )
    parser.add_argument("--backend", choices=["python", "showdown"], default="python")
    parser.add_argument("--teams", choices=["random", "single", "balance"], default="random")
    parser.add_argument("--games", type=int, default=1)
    parser.add_argument("--turns", type=int, default=20)
    parser.add_argument("--sims", type=int, default=16)
    parser.add_argument("--depth", type=int, default=10)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--out", default="data/backend_selfplay.jsonl", help="Output JSONL path, or '-' for stdout.")
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
        raise SystemExit(run_selfplay(args))
    except BackendUnavailableError as exc:
        raise SystemExit(f"Backend unavailable: {exc}") from exc


if __name__ == "__main__":
    main()
