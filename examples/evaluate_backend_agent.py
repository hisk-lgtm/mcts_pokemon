from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import json
import random
from dataclasses import dataclass
from typing import Any, Literal

from battle_engine.backend_agent import BackendLinearPolicyValueAgent, action_to_payload
from battle_engine.backend_features import (
    FEATURE_SCHEMA_VERSION,
    backend_action_features,
    backend_action_label,
)
from battle_engine.backends import BackendUnavailableError, BattleBackend, create_backend
from battle_engine.replay_logs import new_replay_capture, update_replay_capture, write_replay_files
from battle_engine.mcts import MCTSAgent, MCTSConfig
from battle_engine.model import Action, PokemonSet
from battle_engine.sample_sets import TEAM_BALANCE_A, TEAM_BALANCE_B, TYRANITAR_CB, DRAGONITE_DD
from battle_engine.team_builder import default_compendium_path, load_set_pool, random_team

PolicyName = Literal["agent", "first", "random", "mcts", "damage"]


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
    trace_actions: int
    explain_top: int
    save_replay_logs: str | None


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


def _damage_policy_score(summary: dict[str, Any], player: int, action: Action) -> float:
    """Score an action for the deterministic damage-greedy baseline.

    This is not meant to be a good Pokémon policy. It is a transparent baseline
    that uses the same backend feature layer as the trained agent and mostly asks:
    "which legal action appears to do the most direct damage right now?"
    """
    features = backend_action_features(summary, player, action)
    if action.kind == "move":
        return (
            10.0 * features["move_expected_damage"]
            + 6.0 * features["move_expected_can_ko"]
            + 4.0 * features["move_can_ko"]
            + 1.5 * features["move_2hko"]
            + 0.5 * features["move_3hko"]
            + 0.3 * features["move_priority"]
            + 0.2 * features["move_stab"]
            - 1.0 * features["move_damage_accuracy_discount"]
            - 2.0 * features["move_immune"]
        )
    if action.kind == "switch":
        return (
            1.0 * features["switch_hp_after_hazards"]
            + 0.6 * features["switch_resists_opp_stab"]
            + 0.6 * features["switch_immune_to_opp_stab"]
            - 1.0 * features["switch_weak_to_opp_stab"]
            - 2.0 * features["switch_hazard_damage"]
            - 4.0 * features["switch_likely_faints_to_hazards"]
        )
    return 0.0


def _choose_damage_policy_action(summary: dict[str, Any], player: int, legal: list[Action]) -> Action:
    if not legal:
        raise ValueError(f"No legal actions for player {player}.")

    # During ordinary turns, this baseline should behave like a damage policy, not
    # a pivot policy. Only consider switches when there are no move actions.
    candidates = [action for action in legal if action.kind == "move"] or legal
    return max(
        candidates,
        key=lambda action: (
            _damage_policy_score(summary, player, action),
            -action.index,
            backend_action_label(action),
        ),
    )


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
    if policy == "damage":
        return _choose_damage_policy_action(backend.state_summary(), player, legal)
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
    replay_capture: dict[str, list[str]] | None = None,
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
            result = backend.replace_fainted(player, action.index)
            update_replay_capture(replay_capture, result)
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
    action_trace: list[dict[str, Any]] | None = None,
    replay_files: dict[str, Any] | None = None,
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
        "action_trace": action_trace or [],
        "replay_files": replay_files or {},
    }


def _append_action_trace(
    trace: list[dict[str, Any]],
    *,
    config: EvaluationConfig,
    turn_index: int,
    player: int,
    policy: PolicyName,
    summary: dict[str, Any],
    legal: list[Action],
    chosen: Action,
) -> None:
    if config.trace_actions <= 0 or len(trace) >= config.trace_actions:
        return
    entry: dict[str, Any] = {
        "turn_index": turn_index,
        "player": player,
        "policy": policy,
        "chosen_action": action_to_payload(chosen),
        "chosen_label": backend_action_label(chosen),
        "legal_count": len(legal),
    }
    if policy == "agent":
        ranking = config.agent.rank_actions(
            summary,
            player,
            legal,
            top_contributions=max(0, config.explain_top),
        )
        entry["agent_value"] = config.agent.evaluate(summary, player)
        entry["ranked_actions"] = ranking
        for rank, row in enumerate(ranking, start=1):
            if row["action"] == action_to_payload(chosen):
                entry["chosen_rank"] = rank
                entry["chosen_score"] = row["score"]
                entry["chosen_probability"] = row["probability"]
                break
    trace.append(entry)


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
    action_trace: list[dict[str, Any]] = []
    replay_capture = new_replay_capture() if config.save_replay_logs else None

    for turn_index in range(1, config.turns + 1):
        replacements += _handle_replacements(
            backend=backend,
            agent=config.agent,
            opponent=config.opponent,
            agent_player=config.agent_player,
            rng=rng,
            mcts=mcts,
            temperature=config.agent_temperature,
            replay_capture=replay_capture,
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
        _append_action_trace(
            action_trace,
            config=config,
            turn_index=turn_index,
            player=1,
            policy=p1_policy,
            summary=backend.state_summary(),
            legal=p1_legal,
            chosen=p1_action,
        )
        _append_action_trace(
            action_trace,
            config=config,
            turn_index=turn_index,
            player=2,
            policy=p2_policy,
            summary=backend.state_summary(),
            legal=p2_legal,
            chosen=p2_action,
        )
        turn_result = backend.step(p1_action, p2_action)
        update_replay_capture(replay_capture, turn_result)
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
        replay_capture=replay_capture,
    )

    replay_files = None
    if config.save_replay_logs:
        replay_files = write_replay_files(
            config.save_replay_logs,
            game_id=game_id,
            log_lines=replay_capture["log_lines"] if replay_capture else [],
            input_log=replay_capture["input_log"] if replay_capture else [],
            metadata={
                "source": "evaluate_backend_agent",
                "backend": backend.name,
                "game_id": game_id,
                "seed": game_seed,
                "format": config.format_id,
                "teams_mode": config.teams,
                "agent_name": config.agent.name,
                "agent_player": config.agent_player,
                "opponent": config.opponent,
                "turn_limit": config.turns,
                "winner": backend.winner(),
                "team1_species": _team_species(teams.team1),
                "team2_species": _team_species(teams.team2),
                "final_summary": backend.state_summary(),
            },
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
        action_trace=action_trace,
        replay_files=replay_files,
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
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "agent_feature_schema_version": config.agent.feature_schema_version,
            "trace_actions": config.trace_actions,
            "explain_top": config.explain_top,
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
    print(
        f"Feature schema: current=v{summary['feature_schema_version']} | "
        f"agent=v{summary['agent_feature_schema_version']}"
    )
    if summary.get("trace_actions"):
        print(f"Stored action trace entries per report: up to {summary['trace_actions']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate a saved backend policy/value agent against simple backend policies."
    )
    parser.add_argument("--agent", type=Path, required=True, help="Saved backend-agent JSON from train_backend_agent.py")
    parser.add_argument("--backend", choices=["python", "showdown"], default="python")
    parser.add_argument("--opponent", choices=["first", "random", "damage", "mcts", "agent"], default="random")
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
    parser.add_argument("--trace-actions", type=int, default=0, help="Store up to N chosen-action trace entries in the JSON report")
    parser.add_argument("--explain-top", type=int, default=0, help="For traced agent actions, include top N feature contributions")
    parser.add_argument(
        "--save-replay-logs",
        default=None,
        help="Optional directory for one raw battle .log plus metadata .json per evaluated game.",
    )
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
        trace_actions=max(0, args.trace_actions),
        explain_top=max(0, args.explain_top),
        save_replay_logs=args.save_replay_logs,
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
