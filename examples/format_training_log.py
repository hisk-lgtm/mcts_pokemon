from __future__ import annotations

from pathlib import Path
import argparse
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from battle_engine.log_formatter import format_training_log_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert training JSONL into a readable battle-log style text file.")
    parser.add_argument("input", help="Path to training JSONL file.")
    parser.add_argument("--output", "-o", help="Output .log path. If omitted, prints to stdout.")
    parser.add_argument("--top", type=int, default=5, help="How many MCTS root candidates to show per side.")
    args = parser.parse_args()

    text = format_training_log_file(args.input, output_path=args.output, top_n=args.top)
    if args.output:
        print(f"Wrote readable log to {args.output}")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
