from __future__ import annotations

import json
from pathlib import Path

from battle_engine.backend_jsonl_validation import validate_backend_jsonl


def _decision_record(*, with_mcts: bool = True, visits: int = 3) -> dict:
    record = {
        "record_type": "decision",
        "backend": "python",
        "player": 1,
        "final_winner": 1,
        "value_target": 1.0,
        "state_summary": {
            "turn": 1,
            "weather": None,
            "p1": {"hp": 10, "max_hp": 10},
            "p2": {"hp": 10, "max_hp": 10},
        },
        "legal_actions": [
            {
                "kind": "move",
                "index": 0,
                "name": "Stone Edge",
                "type": "Rock",
                "category": "Physical",
                "base_power": 100,
                "accuracy": 80,
            },
            {
                "kind": "move",
                "index": 1,
                "name": "Crunch",
                "type": "Dark",
                "category": "Physical",
                "base_power": 80,
                "accuracy": 100,
            },
        ],
        "chosen_action": {"kind": "move", "index": 0},
    }

    if with_mcts:
        record["mcts"] = {
            "stats": [
                {"action": {"kind": "move", "index": 0}, "visits": visits},
                {"action": {"kind": "move", "index": 1}, "visits": visits},
            ]
        }

    return record


def test_backend_jsonl_validation_reports_mcts_visit_target_coverage(tmp_path: Path):
    path = tmp_path / "records.jsonl"
    records = [
        _decision_record(with_mcts=True, visits=4),
        _decision_record(with_mcts=False),
    ]
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")

    report = validate_backend_jsonl([path])
    payload = report.to_dict()

    assert report.valid
    assert payload["decision_records"] == 2
    assert payload["mcts_records"] == 1
    assert payload["mcts_records_with_visit_stats"] == 1
    assert payload["mcts_visit_target_rate"] == 0.5
    assert payload["mcts_actions_with_visits"] == 2
    assert payload["mcts_total_visits"] == 8.0


def test_backend_jsonl_validation_warns_for_unusable_mcts_visit_stats(tmp_path: Path):
    path = tmp_path / "records.jsonl"
    path.write_text(json.dumps(_decision_record(with_mcts=True, visits=0)) + "\n", encoding="utf-8")

    report = validate_backend_jsonl([path])

    assert report.valid
    assert report.mcts_records == 1
    assert report.mcts_records_with_visit_stats == 0
    assert any("mcts.stats has no usable positive visit counts" in warning for warning in report.warnings)