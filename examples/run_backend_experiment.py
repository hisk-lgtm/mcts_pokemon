from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import json
import random
from datetime import datetime, timezone
from typing import Any

from battle_engine.backend_agent import BackendLinearPolicyValueAgent
from battle_engine.backend_features import FEATURE_SCHEMA_VERSION
from battle_engine.backends import BackendUnavailableError
from battle_engine.backend_jsonl_validation import validate_backend_jsonl

from examples.backend_selfplay import play_backend_game, write_jsonl
from examples.evaluate_backend_agent import EvaluationConfig, run_evaluation
from examples.team_scenarios import TEAM_MODE_CHOICES, build_teams
from examples.train_backend_agent import iter_jsonl, train_records


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _load_config(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _config_from_args(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "created_at_utc": _utc_now(),
        "backend": args.backend,
        "teams": args.teams,
        "games": args.games,
        "turns": args.turns,
        "sims": args.sims,
        "depth": args.depth,
        "seed": args.seed,
        "format": args.format,
        "showdown_root": args.showdown_root,
        "node_bin": args.node_bin,
        "timeout": args.timeout,
        "epochs": args.epochs,
        "learning_rate": args.learning_rate,
        "agent_name": args.agent_name,
        "eval_opponents": list(args.eval_opponents),
        "eval_games": args.eval_games,
        "eval_turns": args.eval_turns,
        "eval_mcts_sims": args.eval_mcts_sims,
        "eval_mcts_depth": args.eval_mcts_depth,
        "agent_player": args.agent_player,
        "agent_temperature": args.agent_temperature,
        "trace_actions": args.trace_actions,
        "explain_top": args.explain_top,
        "save_replay_logs": bool(args.save_replay_logs),
        "strict_validation": bool(args.strict_validation),
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
    }

def _count_metadata_values(rows: list[dict[str, object]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = row.get(key)
        if value in {None, ""}:
            label = "unknown"
        else:
            label = str(value)
        counts[label] = counts.get(label, 0) + 1
    return dict(sorted(counts.items()))


def _team_pair_id(row: dict[str, object]) -> str:
    team1 = row.get("team1_id") or "unknown"
    team2 = row.get("team2_id") or "unknown"
    return f"{team1}_vs_{team2}"


def _summarize_team_metadata(rows: list[dict[str, object]]) -> dict[str, object]:
    pair_rows = [{"team_pair_id": _team_pair_id(row)} for row in rows]
    matchup_counts = _count_metadata_values(rows, "matchup_id")
    return {
        "games_with_metadata": len(rows),
        "unique_matchups": len(matchup_counts),
        "matchup_counts": matchup_counts,
        "mode_counts": _count_metadata_values(rows, "mode"),
        "team1_counts": _count_metadata_values(rows, "team1_id"),
        "team2_counts": _count_metadata_values(rows, "team2_id"),
        "team_pair_counts": _count_metadata_values(pair_rows, "team_pair_id"),
    }

def _count_metadata_values(rows: list[dict[str, object]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = row.get(key)
        if value in {None, ""}:
            label = "unknown"
        else:
            label = str(value)
        counts[label] = counts.get(label, 0) + 1
    return dict(sorted(counts.items()))


def _team_pair_id(row: dict[str, object]) -> str:
    team1 = row.get("team1_id") or "unknown"
    team2 = row.get("team2_id") or "unknown"
    return f"{team1}_vs_{team2}"


def _summarize_team_metadata(rows: list[dict[str, object]]) -> dict[str, object]:
    pair_rows = [{"team_pair_id": _team_pair_id(row)} for row in rows]
    matchup_counts = _count_metadata_values(rows, "matchup_id")
    return {
        "games_with_metadata": len(rows),
        "unique_matchups": len(matchup_counts),
        "matchup_counts": matchup_counts,
        "mode_counts": _count_metadata_values(rows, "mode"),
        "team1_counts": _count_metadata_values(rows, "team1_id"),
        "team2_counts": _count_metadata_values(rows, "team2_id"),
        "team_pair_counts": _count_metadata_values(pair_rows, "team_pair_id"),
    }


def _run_selfplay(args: argparse.Namespace, out_dir: Path) -> tuple[Path, dict[str, Any]]:
    records: list[dict[str, Any]] = []
    team_metadata_rows: list[dict[str, object]] = []
    rng = random.Random(args.seed)
    replay_dir = out_dir / "replays" / "selfplay" if args.save_replay_logs else None

    for game_id in range(args.games):
        game_seed = args.seed + game_id
        team_rng = random.Random(game_seed)
        teams = build_teams(args.teams, team_rng, game_id=game_id)
        team_metadata = teams.metadata()
        teams = build_teams(args.teams, team_rng, game_id=game_id)
        team_metadata = teams.metadata()
        team_metadata_rows.append(team_metadata)
        records.extend(
            play_backend_game(
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
                replay_log_dir=replay_dir,
                teams_mode=args.teams,
                team_metadata=team_metadata,
            )
        )

    selfplay_path = out_dir / "selfplay.jsonl"
    with selfplay_path.open("w", encoding="utf-8") as handle:
        write_jsonl(records, handle)

    winners: dict[str, int] = {}
    for record in records:
        winner_key = str(record.get("final_winner"))
        winners[winner_key] = winners.get(winner_key, 0) + 1

    summary = {
        "path": str(selfplay_path),
        "records": len(records),
        "games": args.games,
        "backend": args.backend,
        "teams": args.teams,
        "team_metadata": _summarize_team_metadata(team_metadata_rows),
        "winner_record_counts": winners,
        "replay_dir": str(replay_dir) if replay_dir else None,
    }
    return selfplay_path, summary


def _train_agent(args: argparse.Namespace, out_dir: Path, selfplay_path: Path) -> tuple[BackendLinearPolicyValueAgent, dict[str, Any]]:
    records = list(iter_jsonl([selfplay_path]))
    if not records:
        raise ValueError(f"No decision records found in {selfplay_path}")

    agent = BackendLinearPolicyValueAgent(
        learning_rate=args.learning_rate,
        name=args.agent_name or f"backend-experiment-{out_dir.name}",
    )
    metrics = train_records(
        agent,
        records,
        epochs=max(1, args.epochs),
        shuffle=not args.no_shuffle,
        rng=random.Random(args.seed),
    )
    metrics.update(
        {
            "input_files": [str(selfplay_path)],
            "output_model": str(out_dir / "agent.json"),
            "agent_name": agent.name,
            "learning_rate": agent.learning_rate,
            "top_weights": agent.top_weights(limit=max(0, args.top_weights)),
        }
    )

    agent_path = out_dir / "agent.json"
    metrics_path = out_dir / "train_metrics.json"
    agent.save(agent_path)
    _write_json(metrics_path, metrics)
    return agent, metrics


def _run_evaluations(
    args: argparse.Namespace,
    out_dir: Path,
    agent: BackendLinearPolicyValueAgent,
) -> dict[str, dict[str, Any]]:
    reports: dict[str, dict[str, Any]] = {}
    for opponent in args.eval_opponents:
        replay_dir = out_dir / "replays" / f"eval_{opponent}" if args.save_replay_logs else None
        config = EvaluationConfig(
            backend_name=args.backend,
            agent=agent,
            opponent=opponent,
            agent_player=args.agent_player,
            games=args.eval_games,
            turns=args.eval_turns,
            seed=args.seed + 10_000,
            teams=args.teams,
            mcts_sims=args.eval_mcts_sims,
            mcts_depth=args.eval_mcts_depth,
            agent_temperature=args.agent_temperature,
            showdown_root=args.showdown_root,
            node_bin=args.node_bin,
            format_id=args.format,
            timeout=args.timeout,
            trace_actions=max(0, args.trace_actions),
            explain_top=max(0, args.explain_top),
            save_replay_logs=str(replay_dir) if replay_dir else None,
        )
        report = run_evaluation(config)
        report["summary"]["report_path"] = str(out_dir / f"eval_{opponent}.json")
        report["summary"]["replay_dir"] = str(replay_dir) if replay_dir else None
        _write_json(out_dir / f"eval_{opponent}.json", report)
        reports[opponent] = report
    return reports


def _write_summary_text(
    out_dir: Path,
    *,
    config: dict[str, Any],
    selfplay_summary: dict[str, Any],
    train_metrics: dict[str, Any],
    eval_reports: dict[str, dict[str, Any]],
) -> str:
    lines = [
        "Backend experiment summary",
        "==========================",
        "",
        f"backend: {config['backend']}",
        f"teams: {config['teams']}",
        f"seed: {config['seed']}",
        f"self-play: games={config['games']} turns={config['turns']} sims={config['sims']} depth={config['depth']}",
        f"records: {selfplay_summary['records']}",
        (
            "matchups: "
            f"unique={selfplay_summary.get('team_metadata', {}).get('unique_matchups', 0)} "
            f"counts={selfplay_summary.get('team_metadata', {}).get('matchup_counts', {})}"
        ),
        "validation: see validation_report.json",
        f"training: epochs={config['epochs']} learning_rate={config['learning_rate']} updates={train_metrics.get('updates')}",
        f"policy_loss_avg: {float(train_metrics.get('policy_loss_avg', 0.0)):.4f}",
        f"value_loss_avg: {float(train_metrics.get('value_loss_avg', 0.0)):.4f}",
        "",
        "Evaluation",
        "----------",
    ]
    for opponent, report in eval_reports.items():
        summary = report["summary"]
        lines.append(
            f"{opponent}: agent_wins={summary['agent_wins']} "
            f"opponent_wins={summary['opponent_wins']} unresolved={summary['unresolved']} "
            f"agent_win_rate={summary['agent_win_rate']:.1%} avg_turns={summary['average_turns']:.2f}"
        )
    lines.extend(
        [
            "",
            "Artifacts",
            "---------",
            "config.json",
            "selfplay.jsonl",
            "agent.json",
            "train_metrics.json",
            "eval_<opponent>.json",
        ]
    )
    if config.get("save_replay_logs"):
        lines.append("replays/")
    text = "\n".join(lines) + "\n"
    (out_dir / "summary.txt").write_text(text, encoding="utf-8")
    return text


def run_experiment(args: argparse.Namespace) -> dict[str, Any]:
    out_dir = Path(args.out_dir)
    if out_dir.exists() and any(out_dir.iterdir()) and not args.force:
        raise FileExistsError(f"Output directory is not empty: {out_dir}. Use --force to reuse it.")
    out_dir.mkdir(parents=True, exist_ok=True)

    config = _config_from_args(args)
    _write_json(out_dir / "config.json", config)

    selfplay_path, selfplay_summary = _run_selfplay(args, out_dir)
    _write_json(out_dir / "selfplay_summary.json", selfplay_summary)

    validation_report = validate_backend_jsonl([selfplay_path], strict_metadata=args.strict_validation)
    validation_payload = validation_report.to_dict()
    _write_json(out_dir / "validation_report.json", validation_payload)
    if not validation_report.valid:
        first_error = validation_report.errors[0] if validation_report.errors else "unknown validation error"
        raise ValueError(f"Generated self-play JSONL failed validation: {first_error}")

    agent, train_metrics = _train_agent(args, out_dir, selfplay_path)
    eval_reports = _run_evaluations(args, out_dir, agent)

    summary_payload = {
        "config": config,
        "selfplay": selfplay_summary,
        "training": {
            key: value
            for key, value in train_metrics.items()
            if key not in {"top_weights"}
        },
        "validation": validation_payload,
        "evaluation": {opponent: report["summary"] for opponent, report in eval_reports.items()},
        "artifacts": {
            "config": str(out_dir / "config.json"),
            "selfplay": str(out_dir / "selfplay.jsonl"),
            "selfplay_summary": str(out_dir / "selfplay_summary.json"),
            "validation_report": str(out_dir / "validation_report.json"),
            "agent": str(out_dir / "agent.json"),
            "train_metrics": str(out_dir / "train_metrics.json"),
            "summary_text": str(out_dir / "summary.txt"),
        },
    }
    _write_json(out_dir / "summary.json", summary_payload)
    summary_text = _write_summary_text(
        out_dir,
        config=config,
        selfplay_summary=selfplay_summary,
        train_metrics=train_metrics,
        eval_reports=eval_reports,
    )
    print(summary_text.rstrip())
    print(f"\nWrote experiment artifacts to {out_dir}")
    return summary_payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run a complete backend learning experiment: self-play JSONL, training, "
            "evaluation reports, and optional replay logs."
        )
    )
    parser.add_argument("--out-dir", type=Path, default=Path("experiments/backend_experiment"))
    parser.add_argument("--force", action="store_true", help="Allow writing into a non-empty output directory")
    parser.add_argument("--backend", choices=["python", "showdown"], default="python")
    parser.add_argument("--teams", choices=TEAM_MODE_CHOICES, default="single")
    parser.add_argument("--games", type=int, default=5, help="Self-play games to generate")
    parser.add_argument("--turns", type=int, default=20, help="Turn cap for self-play games")
    parser.add_argument("--sims", type=int, default=8, help="MCTS simulations per self-play decision")
    parser.add_argument("--depth", type=int, default=4, help="MCTS rollout depth for self-play")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--format", default="gen5ou", help="Showdown format id")
    parser.add_argument("--showdown-root", default=None, help="Local Pokemon Showdown checkout. Defaults to SHOWDOWN_ROOT")
    parser.add_argument("--node-bin", default="node")
    parser.add_argument("--timeout", type=int, default=30, help="Seconds per Showdown bridge call")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--learning-rate", type=float, default=0.05)
    parser.add_argument("--agent-name", default="", help="Name stored in the trained backend agent")
    parser.add_argument("--no-shuffle", action="store_true", help="Keep self-play records in file order during training")
    parser.add_argument("--top-weights", type=int, default=12, help="Top learned weights stored in train_metrics.json")
    parser.add_argument(
        "--eval-opponents",
        nargs="+",
        choices=["first", "random", "damage", "mcts", "agent"],
        default=["first", "random", "damage"],
    )
    parser.add_argument("--eval-games", type=int, default=5)
    parser.add_argument("--eval-turns", type=int, default=20)
    parser.add_argument("--eval-mcts-sims", type=int, default=8)
    parser.add_argument("--eval-mcts-depth", type=int, default=4)
    parser.add_argument("--agent-player", type=int, choices=[1, 2], default=1)
    parser.add_argument("--agent-temperature", type=float, default=0.0)
    parser.add_argument("--trace-actions", type=int, default=0)
    parser.add_argument("--explain-top", type=int, default=0)
    parser.add_argument("--save-replay-logs", action="store_true", help="Save raw backend battle logs under out-dir/replays")
    parser.add_argument("--strict-validation", action="store_true", help="Treat low self-play metadata coverage as an experiment failure")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.games < 1:
        parser.error("--games must be at least 1")
    if args.turns < 1:
        parser.error("--turns must be at least 1")
    if args.sims < 1:
        parser.error("--sims must be at least 1")
    if args.eval_games < 1:
        parser.error("--eval-games must be at least 1")
    if args.eval_turns < 1:
        parser.error("--eval-turns must be at least 1")

    try:
        run_experiment(args)
    except BackendUnavailableError as exc:
        raise SystemExit(f"Backend unavailable: {exc}") from exc
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
