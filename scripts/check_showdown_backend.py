from __future__ import annotations

from pathlib import Path
import argparse
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from battle_engine.backends import ShowdownBattleBackend


def main() -> None:
    parser = argparse.ArgumentParser(description="Check whether a local Showdown backend can be reached.")
    parser.add_argument("--showdown-root", help="Path to local Pokemon Showdown or PokeMMO-aware fork checkout.")
    parser.add_argument("--node-bin", default="node")
    args = parser.parse_args()

    backend = ShowdownBattleBackend(showdown_root=args.showdown_root, node_bin=args.node_bin)
    print(json.dumps(backend.check_available(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
