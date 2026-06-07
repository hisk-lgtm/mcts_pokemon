from __future__ import annotations

from pathlib import Path
import argparse
import shutil
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = PROJECT_ROOT / "showdown_mod_template"


FILES_TO_COPY = [
    ("config/custom-formats.ts", "config/custom-formats.ts"),
    ("data/mods/pokemmo/scripts.ts", "data/mods/pokemmo/scripts.ts"),
    ("data/mods/pokemmo/typechart.ts", "data/mods/pokemmo/typechart.ts"),
    ("data/mods/pokemmo/pokedex.ts", "data/mods/pokemmo/pokedex.ts"),
    ("data/mods/pokemmo/moves.ts", "data/mods/pokemmo/moves.ts"),
    ("data/mods/pokemmo/abilities.ts", "data/mods/pokemmo/abilities.ts"),
    ("data/mods/pokemmo/items.ts", "data/mods/pokemmo/items.ts"),
    ("data/mods/pokemmo/rulesets.ts", "data/mods/pokemmo/rulesets.ts"),
    ("data/mods/pokemmo/learnsets.ts", "data/mods/pokemmo/learnsets.ts"),
]


def looks_like_showdown_root(path: Path) -> bool:
    return (
        (path / "package.json").exists()
        and (path / "sim").exists()
        and (path / "data").exists()
        and (path / "config").exists()
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Install the local PokeMMO Showdown mod template into a Pokémon Showdown checkout.")
    parser.add_argument("--showdown-root", required=True, help="Path to local Pokémon Showdown checkout.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Overwrite existing destination files.")
    args = parser.parse_args()

    showdown_root = Path(args.showdown_root).expanduser().resolve()
    if not looks_like_showdown_root(showdown_root):
        print(f"Not a Pokémon Showdown checkout: {showdown_root}", file=sys.stderr)
        print("Expected package.json plus sim/, data/, and config/ directories.", file=sys.stderr)
        return 2

    for src_rel, dst_rel in FILES_TO_COPY:
        src = TEMPLATE_ROOT / src_rel
        dst = showdown_root / dst_rel
        if not src.exists():
            print(f"Template file missing: {src}", file=sys.stderr)
            return 3

        if dst.exists() and not args.force:
            print(f"SKIP existing {dst_rel} (use --force to overwrite)")
            continue

        print(f"{'WOULD COPY' if args.dry_run else 'COPY'} {src_rel} -> {dst_rel}")
        if not args.dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
