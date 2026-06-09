from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import json
import random
from typing import Iterable, Any

from battle_engine.backend_agent import MODEL_SCHEMA_VERSION, BackendLinearPolicyValueAgent
from battle_engine.backend_features import FEATURE_SCHEMA_VERSION


def iter_jsonl(paths: list[Path]) -> Iterable[dict[str, Any]]:
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    record = json.loads(stripped)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
                if isinstance(record, dict) and record.get("record_type") == "decision":
                    yield record


def _average(total: float, count: int) -> float:
    return total / count if count else 0.0


def train_records(
    agent: BackendLinearPolicyValueAgent,
    records: list[dict[str, Any]],
    *,
    epochs: int,
    shuffle: bool,
    rng: random.Random,
) -> dict[str, Any]:
    metrics = {
        "records": len(records),
        "epochs": epochs,
        "updates": 0,
        "policy_loss_total": 0.0,
        "value_loss_total": 0.0,
        "value_updates": 0,
    }

    for _epoch in range(epochs):
        if shuffle:
            rng.shuffle(records)
        for record in records:
            result = agent.update_from_record(record)
            metrics["updates"] += 1
            if result.get("policy_loss") is not None:
                metrics["policy_loss_total"] += float(result["policy_loss"])
            if result.get("value_loss") is not None:
                metrics["value_updates"] += 1
                metrics["value_loss_total"] += float(result["value_loss"])

    metrics["policy_loss_avg"] = _average(float(metrics["policy_loss_total"]), int(metrics["updates"]))
    metrics["value_loss_avg"] = _average(float(metrics["value_loss_total"]), int(metrics["value_updates"]))
    metrics["policy_weight_count"] = len(agent.policy_weights)
    metrics["value_weight_count"] = len(agent.value_weights)
    metrics["model_schema_version"] = MODEL_SCHEMA_VERSION
    metrics["feature_schema_version"] = FEATURE_SCHEMA_VERSION
    return metrics


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Train a lightweight backend policy/value agent from backend self-play JSONL records."
    )
    parser.add_argument("inputs", nargs="+", type=Path, help="Input JSONL files from examples/backend_selfplay.py")
    parser.add_argument("--out", type=Path, default=Path("training_logs/backend_agent.json"), help="Output model JSON path")
    parser.add_argument("--init", type=Path, help="Optional existing backend-agent JSON to continue training")
    parser.add_argument("--name", default="backend-linear-agent", help="Agent name stored in the model JSON")
    parser.add_argument("--epochs", type=int, default=1, help="Number of passes over the records")
    parser.add_argument("--learning-rate", type=float, default=0.05, help="Gradient step size")
    parser.add_argument("--limit", type=int, default=0, help="Maximum number of records to load; 0 means all")
    parser.add_argument("--seed", type=int, default=1, help="Shuffle seed")
    parser.add_argument("--no-shuffle", action="store_true", help="Keep records in file order each epoch")
    parser.add_argument("--metrics-out", type=Path, help="Optional metrics JSON output path")
    parser.add_argument("--top-weights", type=int, default=12, help="Number of largest learned weights to print/store")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    records = list(iter_jsonl(args.inputs))
    if args.limit and args.limit > 0:
        records = records[: args.limit]
    if not records:
        parser.error("no decision records found in input JSONL")

    if args.init:
        agent = BackendLinearPolicyValueAgent.load(args.init)
        agent.learning_rate = args.learning_rate
        if args.name:
            agent.name = args.name
    else:
        agent = BackendLinearPolicyValueAgent(learning_rate=args.learning_rate, name=args.name)

    metrics = train_records(
        agent,
        records,
        epochs=max(1, args.epochs),
        shuffle=not args.no_shuffle,
        rng=random.Random(args.seed),
    )
    metrics["input_files"] = [str(path) for path in args.inputs]
    metrics["output_model"] = str(args.out)
    metrics["agent_name"] = agent.name
    metrics["learning_rate"] = agent.learning_rate
    metrics["top_weights"] = agent.top_weights(limit=max(0, args.top_weights))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    agent.save(args.out)

    if args.metrics_out:
        args.metrics_out.parent.mkdir(parents=True, exist_ok=True)
        args.metrics_out.write_text(json.dumps(metrics, indent=2, sort_keys=True), encoding="utf-8")

    print(
        "Trained backend agent: "
        f"records={metrics['records']} epochs={metrics['epochs']} updates={metrics['updates']} "
        f"policy_loss={metrics['policy_loss_avg']:.4f} value_loss={metrics['value_loss_avg']:.4f} "
        f"policy_weights={metrics['policy_weight_count']} value_weights={metrics['value_weight_count']} "
        f"feature_schema=v{metrics['feature_schema_version']}"
    )
    if args.top_weights > 0:
        policy_top = metrics["top_weights"]["policy"][: min(5, args.top_weights)]
        value_top = metrics["top_weights"]["value"][: min(5, args.top_weights)]
        if policy_top:
            print("Top policy weights: " + ", ".join(f"{row['feature']}={row['weight']:.4f}" for row in policy_top))
        if value_top:
            print("Top value weights: " + ", ".join(f"{row['feature']}={row['weight']:.4f}" for row in value_top))
    print(f"Wrote model to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
