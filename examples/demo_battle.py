from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from battle_engine import Action, make_battle, step, evaluate_material, legal_actions
from battle_engine.sample_sets import TEAM_BALANCE_A, TEAM_BALANCE_B

state = make_battle(TEAM_BALANCE_A, TEAM_BALANCE_B, seed=7)

print("Initial active:")
print("P1:", state.p1.active_mon().species)
print("P2:", state.p2.active_mon().species)
print()

state, log = step(state, Action("move", 1), Action("move", 0))
print(log)
print("Eval P1:", round(evaluate_material(state, 1), 3))
print()

print("P1 legal actions:", state.p1.active_mon().species, [(a.kind, a.index) for a in legal_actions(state, 1)])
