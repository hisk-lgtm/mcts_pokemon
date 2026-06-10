from __future__ import annotations

import random

from battle_engine.backend_agent import BackendLinearPolicyValueAgent
from examples.train_backend_agent import train_records


def _record_with_mcts_visit_targets() -> dict:
    return {
        "record_type": "decision",
        "player": 1,
        "state_summary": {
            "turn": 1,
            "weather": None,
            "p1": {
                "active": "Tyranitar",
                "hp": 176,
                "max_hp": 176,
                "alive": 1,
                "types": ["Rock", "Dark"],
                "hazards": {},
                "status": None,
            },
            "p2": {
                "active": "Dragonite",
                "hp": 167,
                "max_hp": 167,
                "alive": 1,
                "types": ["Dragon", "Flying"],
                "hazards": {},
                "status": None,
            },
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
        "chosen_action": {"kind": "move", "index": 0, "name": "Stone Edge"},
        "mcts": {
            "stats": [
                {"action": {"kind": "move", "index": 0}, "visits": 1},
                {"action": {"kind": "move", "index": 1}, "visits": 3},
            ]
        },
        "value_target": 1.0,
    }


def test_backend_agent_trains_policy_from_mcts_visit_distribution():
    agent = BackendLinearPolicyValueAgent(learning_rate=0.05)
    metrics = train_records(
        agent,
        [_record_with_mcts_visit_targets()],
        epochs=1,
        shuffle=False,
        rng=random.Random(1),
    )

    assert metrics["updates"] == 1
    assert metrics["mcts_visit_policy_updates"] == 1
    assert metrics["chosen_action_policy_updates"] == 0
    assert metrics["target_entropy_avg"] > 0.0
    assert metrics["policy_weight_count"] > 0


def test_backend_agent_falls_back_to_chosen_action_without_mcts_stats():
    record = _record_with_mcts_visit_targets()
    record.pop("mcts")
    agent = BackendLinearPolicyValueAgent(learning_rate=0.05)

    metrics = train_records(
        agent,
        [record],
        epochs=1,
        shuffle=False,
        rng=random.Random(1),
    )

    assert metrics["mcts_visit_policy_updates"] == 0
    assert metrics["chosen_action_policy_updates"] == 1
    assert metrics["target_entropy_avg"] == 0.0