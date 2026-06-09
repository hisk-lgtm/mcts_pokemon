from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import json

from battle_engine.backend_jsonl_validation import validate_backend_jsonl


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate backend self-play JSONL before training."
    )
    parser.add_argument("inputs", nargs="+", type=Path, help="Input backend self-play JSONL file(s)")
    parser.add_argument("--out", type=Path, help="Optional JSON validation report path")
    parser.add_argument("--strict-metadata", action="store_true", help="Treat low metadata coverage as an error")
    parser.add_argument("--json", action="store_true", help="Print the full report as JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    report = validate_backend_jsonl(args.inputs, strict_metadata=args.strict_metadata)
    payload = report.to_dict()

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        status = "valid" if report.valid else "invalid"
        print(
            f"Backend JSONL validation: {status} | records={report.records} "
            f"decisions={report.decision_records} errors={len(report.errors)} warnings={len(report.warnings)}"
        )
        print(f"Move metadata coverage: {report.move_metadata_rate:.1%} ({report.move_actions_with_metadata}/{report.move_actions})")
        print(f"Switch metadata coverage: {report.switch_metadata_rate:.1%} ({report.switch_actions_with_metadata}/{report.switch_actions})")
        if report.errors:
            print("Errors:")
            for message in report.errors[:25]:
                print(f"  - {message}")
            if len(report.errors) > 25:
                print(f"  ... {len(report.errors) - 25} more")
        if report.warnings:
            print("Warnings:")
            for message in report.warnings[:25]:
                print(f"  - {message}")
            if len(report.warnings) > 25:
                print(f"  ... {len(report.warnings) - 25} more")

    return 0 if report.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
