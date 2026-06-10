from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_run_backend_experiment_summarizes_round_robin_matchup_coverage(tmp_path):
    root = Path(__file__).resolve().parents[1]
    out_dir = tmp_path / "round_robin_experiment"

    result = subprocess.run(
        [
            sys.executable,
            str(root / "examples/run_backend_experiment.py"),
            "--backend",
            "python",
            "--teams",
            "round-robin",
            "--games",
            "5",
            "--turns",
            "1",
            "--sims",
            "1",
            "--depth",
            "0",
            "--epochs",
            "1",
            "--eval-games",
            "1",
            "--eval-turns",
            "1",
            "--eval-opponents",
            "first",
            "--out-dir",
            str(out_dir),
        ],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stdout

    selfplay_summary = json.loads((out_dir / "selfplay_summary.json").read_text(encoding="utf-8"))
    team_metadata = selfplay_summary["team_metadata"]

    assert team_metadata["games_with_metadata"] == 5
    assert team_metadata["unique_matchups"] == 5
    assert team_metadata["matchup_counts"] == {
        "balance_a_vs_b": 1,
        "balance_b_vs_a": 1,
        "mirror_balance_a": 1,
        "mirror_balance_b": 1,
        "single_tyranitar_vs_dragonite": 1,
    }
    assert team_metadata["team_pair_counts"] == {
        "balance_a_vs_balance_a": 1,
        "balance_a_vs_balance_b": 1,
        "balance_b_vs_balance_a": 1,
        "balance_b_vs_balance_b": 1,
        "tyranitar_cb_vs_dragonite_dd": 1,
    }

    summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["selfplay"]["team_metadata"] == team_metadata

    summary_text = (out_dir / "summary.txt").read_text(encoding="utf-8")
    assert "matchups: unique=5" in summary_text
    assert "single_tyranitar_vs_dragonite" in summary_text