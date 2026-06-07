from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import json
from typing import Any, Iterable

from battle_engine.backend_features import (
    STATE_FEATURE_NAMES,
    backend_action_label,
    backend_record_features,
)


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{line_number}: invalid JSON: {exc}") from exc
            if isinstance(payload, dict):
                yield payload


def _format_feature_block(title: str, features: dict[str, float], *, top: int | None = None) -> list[str]:
    nonzero = [(key, value) for key, value in features.items() if value != 0.0]
    if title == "action":
        state_names = set(STATE_FEATURE_NAMES)
        nonzero.sort(key=lambda item: (item[0] in state_names, item[0]))
    shown = nonzero if top is None else nonzero[:top]
    lines = [f"  {title} ({len(nonzero)} nonzero / {len(features)} total):"]
    if not shown:
        lines.append("    <all zero>")
        return lines
    for key, value in shown:
        lines.append(f"    {key}={value:.4g}")
    hidden = len(nonzero) - len(shown)
    if hidden > 0:
        lines.append(f"    ... {hidden} more nonzero features")
    return lines


def inspect_records(args: argparse.Namespace) -> int:
    path = Path(args.path)
    count = 0
    for record in _iter_jsonl(path):
        if record.get("record_type") != "decision":
            continue
        count += 1
        features = backend_record_features(record)
        chosen = record.get("chosen_action") or {}
        print(
            f"Record {count}: backend={record.get('backend')} "
            f"game={record.get('game_id')} turn={record.get('turn_index')} "
            f"player={record.get('player')} chosen={backend_action_label(chosen)} "
            f"value={record.get('value_target')}"
        )
        for line in _format_feature_block("state", features["state"], top=args.top):
            print(line)
        for line in _format_feature_block("action", features["action"], top=args.top):
            print(line)
        if count >= args.limit:
            break
    if count == 0:
        print(f"No decision records found in {path}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect backend self-play JSONL records as feature vectors."
    )
    parser.add_argument("path", help="Path to backend_selfplay.py JSONL output.")
    parser.add_argument("--limit", type=int, default=3, help="Decision records to inspect.")
    parser.add_argument("--top", type=int, default=20, help="Max nonzero features to print per block.")
    args = parser.parse_args()
    raise SystemExit(inspect_records(args))


if __name__ == "__main__":
    main()
