from __future__ import annotations

from pathlib import Path
import argparse
import json
import sys


REQUIRED_FILES = [
    "config/custom-formats.ts",
    "data/mods/pokemmo/scripts.ts",
    "data/mods/pokemmo/typechart.ts",
    "data/mods/pokemmo/pokedex.ts",
    "data/mods/pokemmo/moves.ts",
    "data/mods/pokemmo/abilities.ts",
    "data/mods/pokemmo/items.ts",
    "data/mods/pokemmo/rulesets.ts",
    "data/mods/pokemmo/learnsets.ts",
]


REQUIRED_SNIPPETS = {
    "config/custom-formats.ts": ["[PokeMMO] OU", 'mod: "pokemmo"'],
    "data/mods/pokemmo/scripts.ts": ["inherit: 'gen8'"],
    "data/mods/pokemmo/typechart.ts": ["fairy", 'isNonstandard: "Past"', "damageTaken", "steel"],
    "data/mods/pokemmo/pokedex.ts": ["togekiss", 'types: ["Normal", "Flying"]'],
    "data/mods/pokemmo/rulesets.ts": ["PokeMMO Standard"],
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Check that the PokeMMO Showdown mod template is installed.")
    parser.add_argument("--showdown-root", required=True)
    args = parser.parse_args()

    root = Path(args.showdown_root).expanduser().resolve()
    results = []
    ok = True

    for rel in REQUIRED_FILES:
        path = root / rel
        entry = {"path": rel, "exists": path.exists(), "snippets": {}}
        if not path.exists():
            ok = False
            results.append(entry)
            continue

        text = path.read_text(encoding="utf-8")
        for snippet in REQUIRED_SNIPPETS.get(rel, []):
            found = snippet in text
            entry["snippets"][snippet] = found
            ok = ok and found
        results.append(entry)

    print(json.dumps({"ok": ok, "showdown_root": str(root), "files": results}, indent=2, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
