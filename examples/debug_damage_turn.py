from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from battle_engine import Action, make_battle, step
from battle_engine.sample_sets import TYRANITAR_CB, DRAGONITE_DD

state = make_battle([TYRANITAR_CB], [DRAGONITE_DD], seed=1)
state, log = step(state, Action("move", 1), Action("move", 0), debug_damage=True)

print(log)
