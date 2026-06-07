from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


from battle_engine.import_sets import parse_showdown_sets_file
from battle_engine import make_battle

sets_path = Path(__file__).resolve().parents[1] / "data" / "ou_sets_to_import.txt"
sets = parse_showdown_sets_file(str(sets_path))

print(f"Imported {len(sets)} sets:")
for s in sets:
    print(f"- {s.species} @ {s.item}: {', '.join(s.moves)}")

# Example: first 6 vs next 6 if you eventually add enough sets.
if len(sets) >= 12:
    battle = make_battle(sets[:6], sets[6:12], seed=1)
    print("Battle created.")
else:
    print("Add at least 12 sets to create two full teams from this file.")
