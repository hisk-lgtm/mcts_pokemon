from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import json
import random
from dataclasses import dataclass
from typing import Any, Literal

from battle_engine.backend_agent import BackendLinearPolicyValueAgent
from battle_engine.backends import BackendUnavailableError, BattleBackend, create_backend
from battle_engine.mcts import MCTSAgent, MCTSConfig
from battle_engine.model import Action, PokemonSet
from battle_engine.sample_sets import TEAM_BALANCE_A, TEAM_BALANCE_B, TYRANITAR_CB, DRAGONITE_DD
from battle_engine.team_builder import default_compendium_path, load_set_pool, random_team

PolicyName = Literal["agent", "first", "random", "mcts"]


@dataclass(frozen=True)
class GameTeams:
    team1: list[PokemonSet]
    team2: list[PokemonSet]


@dataclass
class EvaluationConfig:
    backend_name: str
    agent: BackendLinearPolicyValueAgent
    opponent: PolicyName
    agent_player: int
    games: int
    turns: int
    seed: int
    teams: str
    mcts_sims: int
    mcts_depth: int
    agent_temperature: float
    showdown_root: str | None
    node_bin: str
    format_id: str
    timeout: int


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


def _policy_for_player(player: int, agent_player: int, opponent: PolicyName) -> PolicyName:
    return "agent" if player == agent_player else opponent


def _choose_action(
    *,
    backend: BattleBackend,
    player: int,
    policy: PolicyName,
    agent: BackendLinearPolicyValueAgent,
    rng: random.Random,
    mcts: MCTSAgent,
    temperature: float,
    legal_actions: list[Action] | None = None,
) -> Action:
    legal = list(legal_actions if legal_actions is not None else backend.legal_actions(player))
    if not legal:
        raise ValueError(f"No legal actions for player {player}.")

    if policy == "first":
        return legal[0]
    if policy == "random":
        return rng.choice(legal)
    if policy == "agent":
        return agent.choose_action(
            backend.state_summary(),
            player,
            legal,
            temperature=temperature,
            rng=rng,
        )
    if policy == "mcts":
        # MCTS is meaningful for ordinary simultaneous turns. During forced
        # replacement states, legal actions are usually only switches, so a
        # deterministic first switch is enough and avoids abusing step-based MCTS.
        if all(action.kind == "switch" for action in legal):
            return legal[0]
        return mcts.search_backend(backend, player).action
    raise ValueError(f"Unknown policy: {policy}")


def _handle_replacements(
    *,
    backend: BattleBackend,
    agent: BackendLinearPolicyValueAgent,
    opponent: PolicyName,
    agent_player: int,
    rng: random.Random,
    mcts: MCTSAgent,
    temperature: float,
) -> int:
    replacements = 0
    changed = True
    while changed and backend.winner() is None:
        changed = False
        for player in (1, 2):
            if not backend.needs_replacement(player):
                continue
            switches = [action for action in backend.legal_actions(player) if action.kind == "switch"]
            if not switches:
                continue
            policy = _policy_for_player(player, agent_player, opponent)
            action = _choose_action(
                backend=backend,
                player=player,
                policy=policy,
                agent=agent,
                rng=rng,
                mcts=mcts,
                temperature=temperature,
                legal_actions=switches,
            )
            backend.replace_fainted(player, action.index)
            replacements += 1
            changed = True
    return replacements


def _game_result_record(
    *,
    game_id: int,
    seed: int,
    winner: int | None,
    turns_played: int,
    agent_player: int,
    opponent: PolicyName,
    backend: BattleBackend,
    team1: list[PokemonSet],
    team2: list[PokemonSet],
    replacements: int,
) -> dict[str, Any]:
    agent_won = winner == agent_player
    opponent_won = winner in {1, 2} and winner != agent_player
    unresolved = winner is None or winner == 0
    return {
        "game_id": game_id,
        "seed": seed,
        "backend": backend.name,
        "opponent": opponent,
        "agent_player": agent_player,
        "winner": winner,
        "agent_won": agent_won,
        "opponent_won": opponent_won,
        "unresolved": unresolved,
        "turns_played": turns_played,
        "replacements": replacements,
        "team1_species": _team_species(team1),
        "team2_species": _team_species(team2),
        "final_summary": backend.state_summary(),
    }


def play_evaluation_game(config: EvaluationConfig, *, game_id: int, rng: random.Random) -> dict[str, Any]:
    game_seed = config.seed + game_id
    team_rng = random.Random(game_seed)
    teams = _build_teams(config.teams, team_rng)
    backend = create_backend(
        config.backend_name,  # type: ignore[arg-type]
        teams.team1,
        teams.team2,
        seed=game_seed,
        showdown_root=config.showdown_root,
        node_bin=config.node_bin,
        format_id=config.format_id,
        timeout_seconds=config.timeout,
    )
    mcts = MCTSAgent(MCTSConfig(simulations=config.mcts_sims, max_depth=config.mcts_depth), rng=rng)
    replacements = 0
    turns_played = 0

    for turn_index in range(1, config.turns + 1):
        replacements += _handle_replacements(
            backend=backend,
            agent=config.agent,
            opponent=config.opponent,
            agent_player=config.agent_player,
            rng=rng,
            mcts=mcts,
            temperature=config.agent_temperature,
        )
        if backend.winner() is not None:
            break

        p1_legal = backend.legal_actions(1)
        p2_legal = backend.legal_actions(2)
        if not p1_legal or not p2_legal:
            break

        p1_policy = _policy_for_player(1, config.agent_player, config.opponent)
        p2_policy = _policy_for_player(2, config.agent_player, config.opponent)
        p1_action = _choose_action(
            backend=backend,
            player=1,
            policy=p1_policy,
            agent=config.agent,
            rng=rng,
            mcts=mcts,
            temperature=config.agent_temperature,
            legal_actions=p1_legal,
        )
        p2_action = _choose_action(
            backend=backend,
            player=2,
            policy=p2_policy,
            agent=config.agent,
            rng=rng,
            mcts=mcts,
            temperature=config.agent_temperature,
            legal_actions=p2_legal,
        )
        backend.step(p1_action, p2_action)
        turns_played = turn_index
        if backend.winner() is not None:
            break

    replacements += _handle_replacements(
        backend=backend,
        agent=config.agent,
        opponent=config.opponent,
        agent_player=config.agent_player,
        rng=rng,
        mcts=mcts,
        temperature=config.agent_temperature,
    )

    return _game_result_record(
        game_id=game_id,
        seed=game_seed,
        winner=backend.winner(),
        turns_played=turns_played,
        agent_player=config.agent_player,
        opponent=config.opponent,
        backend=backend,
        team1=teams.team1,
        team2=teams.team2,
        replacements=replacements,
    )


def summarize_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    games = len(results)
    agent_wins = sum(1 for result in results if result["agent_won"])
    opponent_wins = sum(1 for result in results if result["opponent_won"])
    unresolved = sum(1 for result in results if result["unresolved"])
    p1_wins = sum(1 for result in results if result["winner"] == 1)
    p2_wins = sum(1 for result in results if result["winner"] == 2)
    total_turns = sum(int(result["turns_played"]) for result in results)
    return {
        "games": games,
        "agent_wins": agent_wins,
        "opponent_wins": opponent_wins,
        "unresolved": unresolved,
        "agent_win_rate": agent_wins / games if games else 0.0,
        "opponent_win_rate": opponent_wins / games if games else 0.0,
        "unresolved_rate": unresolved / games if games else 0.0,
        "p1_wins": p1_wins,
        "p2_wins": p2_wins,
        "average_turns": total_turns / games if games else 0.0,
    }


def run_evaluation(config: EvaluationConfig) -> dict[str, Any]:
    rng = random.Random(config.seed)
    results = [play_evaluation_game(config, game_id=game_id, rng=rng) for game_id in range(config.games)]
    summary = summarize_results(results)
    return {
        "summary": {
            **summary,
            "backend": config.backend_name,
            "opponent": config.opponent,
            "agent_player": config.agent_player,
            "agent_name": config.agent.name,
            "teams": config.teams,
            "turn_limit": config.turns,
            "seed": config.seed,
            "mcts_sims": config.mcts_sims,
            "mcts_depth": config.mcts_depth,
        },
        "games": results,
    }


def _print_report(report: dict[str, Any]) -> None:
    summary = report["summary"]
    print(
        "Backend agent evaluation: "
        f"backend={summary['backend']} opponent={summary['opponent']} "
        f"games={summary['games']} agent_player=P{summary['agent_player']}"
    )
    print(
        f"Agent wins: {summary['agent_wins']} | "
        f"Opponent wins: {summary['opponent_wins']} | "
        f"Unresolved/draw: {summary['unresolved']}"
    )
    print(
        f"Agent win rate: {summary['agent_win_rate']:.1%} | "
        f"Average turns: {summary['average_turns']:.2f}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate a saved backend policy/value agent against simple backend policies."
    )
    parser.add_argument("--agent", type=Path, required=True, help="Saved backend-agent JSON from train_backend_agent.py")
    parser.add_argument("--backend", choices=["python", "showdown"], default="python")
    parser.add_argument("--opponent", choices=["first", "random", "mcts", "agent"], default="random")
    parser.add_argument("--agent-player", type=int, choices=[1, 2], default=1)
    parser.add_argument("--games", type=int, default=20)
    parser.add_argument("--turns", type=int, default=30, help="Turn cap per game; unresolved at cap counts separately")
    parser.add_argument("--teams", choices=["single", "balance", "random"], default="single")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--mcts-sims", type=int, default=8, help="Simulations for --opponent mcts")
    parser.add_argument("--mcts-depth", type=int, default=4, help="Rollout depth for --opponent mcts")
    parser.add_argument("--agent-temperature", type=float, default=0.0, help="0 means greedy agent policy")
    parser.add_argument("--showdown-root", default=None, help="Local Pokemon Showdown checkout. Defaults to SHOWDOWN_ROOT")
    parser.add_argument("--node-bin", default="node")
    parser.add_argument("--format", default="gen5ou", help="Showdown format id for --backend showdown")
    parser.add_argument("--timeout", type=int, default=30, help="Seconds per Showdown bridge call")
    parser.add_argument("--out", type=Path, help="Optional JSON report output path")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.games < 1:
        parser.error("--games must be at least 1")
    if args.turns < 1:
        parser.error("--turns must be at least 1")

    agent = BackendLinearPolicyValueAgent.load(args.agent)
    config = EvaluationConfig(
        backend_name=args.backend,
        agent=agent,
        opponent=args.opponent,
        agent_player=args.agent_player,
        games=args.games,
        turns=args.turns,
        seed=args.seed,
        teams=args.teams,
        mcts_sims=args.mcts_sims,
        mcts_depth=args.mcts_depth,
        agent_temperature=args.agent_temperature,
        showdown_root=args.showdown_root,
        node_bin=args.node_bin,
        format_id=args.format,
        timeout=args.timeout,
    )
    report = run_evaluation(config)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    _print_report(report)
    if args.out:
        print(f"Wrote report to {args.out}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BackendUnavailableError as exc:
        raise SystemExit(f"Backend unavailable: {exc}") from exc
