from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from battle_engine import Action
from battle_engine.backends import PythonBattleBackend, ShowdownBattleBackend
from battle_engine.sample_sets import TEAM_BALANCE_A, TEAM_BALANCE_B


def main() -> None:
    py_backend = PythonBattleBackend(TEAM_BALANCE_A, TEAM_BALANCE_B, seed=1)
    print("Python backend state:")
    print(py_backend.state_summary())

    p1 = py_backend.legal_actions(1)[0]
    p2 = py_backend.legal_actions(2)[0]
    result = py_backend.step(p1, p2)
    print("\nPython backend turn:")
    print("\n".join(result.log_lines))

    showdown = ShowdownBattleBackend()
    print("\nShowdown backend check:")
    print(showdown.check_available())


if __name__ == "__main__":
    main()
