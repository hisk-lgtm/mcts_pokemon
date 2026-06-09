from __future__ import annotations

from pathlib import Path
import argparse
import json
import math
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


NUMERIC_NA = "-"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _experiment_name(path: Path) -> str:
    return path.name or str(path)


def _load_experiment(path: Path) -> dict[str, Any]:
    summary_path = path / "summary.json" if path.is_dir() else path
    if not summary_path.exists():
        raise FileNotFoundError(f"Experiment summary not found: {summary_path}")
    summary = _read_json(summary_path)
    root = summary_path.parent
    return {
        "path": str(root),
        "name": _experiment_name(root),
        "summary_path": str(summary_path),
        "summary": summary,
    }


def _as_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        if isinstance(value, bool):
            return 1.0 if value else 0.0
        number = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(number) or math.isinf(number):
        return default
    return number


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _pct(value: Any) -> str:
    number = _as_float(value)
    if number is None:
        return NUMERIC_NA
    return f"{number * 100:.1f}%"


def _float_text(value: Any, digits: int = 4) -> str:
    number = _as_float(value)
    if number is None:
        return NUMERIC_NA
    return f"{number:.{digits}f}"


def _signed_delta(value: Any, baseline: Any, *, pct: bool = False, digits: int = 1) -> str:
    current = _as_float(value)
    base = _as_float(baseline)
    if current is None or base is None:
        return NUMERIC_NA
    delta = current - base
    if pct:
        return f"{delta * 100:+.{digits}f}pp"
    return f"{delta:+.{digits}f}"


def _all_opponents(experiments: list[dict[str, Any]]) -> list[str]:
    opponents: set[str] = set()
    for exp in experiments:
        evaluation = exp["summary"].get("evaluation", {})
        if isinstance(evaluation, dict):
            opponents.update(str(key) for key in evaluation.keys())
    return sorted(opponents)


def _validation_status(validation: dict[str, Any]) -> bool | None:
    if "valid" in validation:
        return bool(validation["valid"])
    if "ok" in validation:
        return bool(validation["ok"])
    return None


def _validation_count(validation: dict[str, Any], legacy_key: str, current_key: str) -> int | None:
    if legacy_key in validation:
        return _as_int(validation.get(legacy_key))
    current = validation.get(current_key)
    if isinstance(current, list):
        return len(current)
    if current is None:
        return None
    return _as_int(current)


def summarize_experiment(exp: dict[str, Any]) -> dict[str, Any]:
    summary = exp["summary"]
    config = summary.get("config", {}) if isinstance(summary.get("config"), dict) else {}
    selfplay = summary.get("selfplay", {}) if isinstance(summary.get("selfplay"), dict) else {}
    validation = summary.get("validation", {}) if isinstance(summary.get("validation"), dict) else {}
    training = summary.get("training", {}) if isinstance(summary.get("training"), dict) else {}
    evaluation = summary.get("evaluation", {}) if isinstance(summary.get("evaluation"), dict) else {}
    return {
        "name": exp["name"],
        "path": exp["path"],
        "backend": config.get("backend"),
        "teams": config.get("teams"),
        "seed": config.get("seed"),
        "selfplay_games": config.get("games"),
        "selfplay_turns": config.get("turns"),
        "selfplay_sims": config.get("sims"),
        "selfplay_depth": config.get("depth"),
        "records": selfplay.get("records"),
        "validation_ok": _validation_status(validation),
        "validation_errors": _validation_count(validation, "error_count", "errors"),
        "validation_warnings": _validation_count(validation, "warning_count", "warnings"),
        "move_metadata_rate": validation.get("move_metadata_rate"),
        "switch_metadata_rate": validation.get("switch_metadata_rate"),
        "policy_loss_avg": training.get("policy_loss_avg"),
        "value_loss_avg": training.get("value_loss_avg"),
        "updates": training.get("updates"),
        "feature_schema_version": config.get("feature_schema_version") or training.get("feature_schema_version"),
        "evaluation": evaluation,
    }


def _comparison_payload(experiments: list[dict[str, Any]]) -> dict[str, Any]:
    summaries = [summarize_experiment(exp) for exp in experiments]
    opponents = _all_opponents(experiments)
    baseline = summaries[0] if summaries else None
    rows: list[dict[str, Any]] = []
    for row in summaries:
        output: dict[str, Any] = {
            key: value for key, value in row.items() if key != "evaluation"
        }
        output["opponents"] = {}
        for opponent in opponents:
            eval_summary = row["evaluation"].get(opponent, {}) if isinstance(row["evaluation"], dict) else {}
            base_eval = (
                baseline["evaluation"].get(opponent, {})
                if baseline and isinstance(baseline.get("evaluation"), dict)
                else {}
            )
            output["opponents"][opponent] = {
                "games": eval_summary.get("games"),
                "agent_win_rate": eval_summary.get("agent_win_rate"),
                "agent_win_rate_delta_vs_first": (
                    _as_float(eval_summary.get("agent_win_rate"), 0.0)
                    - _as_float(base_eval.get("agent_win_rate"), 0.0)
                    if eval_summary and base_eval
                    else None
                ),
                "opponent_win_rate": eval_summary.get("opponent_win_rate"),
                "unresolved_rate": eval_summary.get("unresolved_rate"),
                "average_turns": eval_summary.get("average_turns"),
            }
        rows.append(output)
    return {
        "baseline": summaries[0]["name"] if summaries else None,
        "opponents": opponents,
        "experiments": rows,
    }


def _table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(str(cell)))

    def fmt_row(row: list[str]) -> str:
        return "  ".join(str(cell).ljust(widths[index]) for index, cell in enumerate(row)).rstrip()

    lines = [fmt_row(headers), fmt_row(["-" * width for width in widths])]
    lines.extend(fmt_row(row) for row in rows)
    return "\n".join(lines)


def render_text_report(payload: dict[str, Any]) -> str:
    experiments = payload["experiments"]
    opponents = payload["opponents"]
    lines = ["Backend experiment comparison", "=============================", ""]
    if not experiments:
        return "\n".join(lines + ["No experiments.", ""])

    overview_rows: list[list[str]] = []
    baseline = experiments[0]
    for exp in experiments:
        overview_rows.append(
            [
                str(exp.get("name")),
                str(exp.get("backend") or NUMERIC_NA),
                str(exp.get("teams") or NUMERIC_NA),
                str(exp.get("records") if exp.get("records") is not None else NUMERIC_NA),
                str(exp.get("validation_ok") if exp.get("validation_ok") is not None else NUMERIC_NA),
                str(exp.get("validation_errors") if exp.get("validation_errors") is not None else NUMERIC_NA),
                str(exp.get("validation_warnings") if exp.get("validation_warnings") is not None else NUMERIC_NA),
                _pct(exp.get("move_metadata_rate")),
                _pct(exp.get("switch_metadata_rate")),
                _float_text(exp.get("policy_loss_avg")),
                _signed_delta(exp.get("policy_loss_avg"), baseline.get("policy_loss_avg"), digits=4),
                _float_text(exp.get("value_loss_avg")),
                _signed_delta(exp.get("value_loss_avg"), baseline.get("value_loss_avg"), digits=4),
            ]
        )
    lines.append(
        _table(
            [
                "experiment",
                "backend",
                "teams",
                "records",
                "valid",
                "errors",
                "warn",
                "move_meta",
                "switch_meta",
                "policy_loss",
                "Δpolicy",
                "value_loss",
                "Δvalue",
            ],
            overview_rows,
        )
    )

    for opponent in opponents:
        lines.extend(["", f"Evaluation vs {opponent}", "-" * (14 + len(opponent))])
        rows: list[list[str]] = []
        baseline_opp = baseline.get("opponents", {}).get(opponent, {})
        for exp in experiments:
            opp = exp.get("opponents", {}).get(opponent, {})
            rows.append(
                [
                    str(exp.get("name")),
                    str(opp.get("games") if opp.get("games") is not None else NUMERIC_NA),
                    _pct(opp.get("agent_win_rate")),
                    _signed_delta(opp.get("agent_win_rate"), baseline_opp.get("agent_win_rate"), pct=True),
                    _pct(opp.get("opponent_win_rate")),
                    _pct(opp.get("unresolved_rate")),
                    _float_text(opp.get("average_turns"), digits=2),
                ]
            )
        lines.append(
            _table(
                ["experiment", "games", "agent_wr", "Δagent_wr", "opp_wr", "unresolved", "avg_turns"],
                rows,
            )
        )

    lines.extend(
        [
            "",
            f"Baseline for deltas: {payload.get('baseline')}",
        ]
    )
    return "\n".join(lines) + "\n"


def compare_experiments(paths: list[Path]) -> dict[str, Any]:
    if not paths:
        raise ValueError("At least one experiment directory or summary.json path is required")
    experiments = [_load_experiment(path) for path in paths]
    return _comparison_payload(experiments)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare backend experiment folders produced by run_backend_experiment.py."
    )
    parser.add_argument("experiments", nargs="+", type=Path, help="Experiment directories or summary.json files")
    parser.add_argument("--out", type=Path, help="Optional JSON comparison report path")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of a text table")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    payload = compare_experiments(args.experiments)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_text_report(payload), end="")
    if args.out:
        print(f"Wrote comparison report to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
