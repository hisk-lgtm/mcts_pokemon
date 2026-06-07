from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


from battle_engine.data import MOVES, SPECIES
from battle_engine.import_sets import parse_showdown_sets_file, split_showdown_blocks
from battle_engine.team_builder import default_compendium_path


def main() -> None:
    path = default_compendium_path()
    text = path.read_text(encoding="utf-8")
    sets = parse_showdown_sets_file(str(path), expand_variants=True)

    species = sorted({s.species for s in sets})
    moves = sorted({m for s in sets for m in s.moves})
    missing_species = [s for s in species if s not in SPECIES]
    missing_moves = [m for m in moves if m not in MOVES]

    print(f"Source: {path.relative_to(Path.cwd()) if path.is_relative_to(Path.cwd()) else path}")
    print(f"Set blocks: {len(split_showdown_blocks(text))}")
    print(f"Expanded variants: {len(sets)}")
    print(f"Unique species: {len(species)}")
    print(f"Unique moves: {len(moves)}")
    print(f"Missing species: {len(missing_species)}")
    for name in missing_species:
        print(f"  - {name}")
    print(f"Missing moves: {len(missing_moves)}")
    for name in missing_moves:
        print(f"  - {name}")


if __name__ == "__main__":
    main()
