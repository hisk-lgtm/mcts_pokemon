from __future__ import annotations

import json
from pathlib import Path

from examples.compare_experiments import compare_experiments, render_text_report


def test_compare_experiments_reports_policy_target_metrics(tmp_path: Path):
    exp_dir = tmp_path / "exp"
    exp_dir.mkdir()

    summary = {
        "config": {
            "backend": "python",
            "teams": "single",
            "seed": 1,
            "games": 2,
            "turns": 3,
            "sims": 4,
            "depth": 1,
            "feature_schema_version": 5,
        },
        "selfplay": {
            "records": 8,
        },
        "validation": {
            "valid": True,
            "errors": [],
            "warnings": [],
            "move_metadata_rate": 1.0,
            "switch_metadata_rate": 0.5,
        },
        "training": {
            "updates": 8,
            "policy_loss_avg": 1.25,
            "target_entropy_avg": 0.75,
            "mcts_visit_policy_updates": 8,
            "chosen_action_policy_updates": 0,
            "value_loss_avg": 0.5,
            "feature_schema_version": 5,
        },
        "evaluation": {},
    }

    (exp_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")

    payload = compare_experiments([exp_dir])
    row = payload["experiments"][0]

    assert row["mcts_visit_policy_updates"] == 8
    assert row["chosen_action_policy_updates"] == 0
    assert row["target_entropy_avg"] == 0.75

    text = render_text_report(payload)
    assert "mcts_tgt" in text
    assert "chosen_tgt" in text
    assert "tgt_entropy" in text
    assert "8" in text
    assert "0.7500" in text