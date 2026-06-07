from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
import random
from pathlib import Path
from typing import Any

from .backend_features import (
    FEATURE_SCHEMA_VERSION,
    backend_action_features,
    backend_action_label,
    backend_state_features,
    action_from_payload,
)
from .model import Action

MODEL_SCHEMA_VERSION = 1


def dot(weights: dict[str, float], features: dict[str, float]) -> float:
    return sum(weights.get(key, 0.0) * value for key, value in features.items())


def stable_sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1 / (1 + z)
    z = math.exp(x)
    return z / (1 + z)


def softmax_scores(scores: list[float]) -> list[float]:
    if not scores:
        return []
    max_score = max(scores)
    exps = [math.exp(max(-40.0, min(40.0, score - max_score))) for score in scores]
    total = sum(exps) or 1.0
    return [value / total for value in exps]


def _target_value(record: dict[str, Any]) -> float | None:
    value = record.get("value_target")
    if value is None:
        return None
    try:
        return max(-1.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return None


def _record_context(record: dict[str, Any]) -> tuple[dict[str, Any], int, list[Action], Action]:
    summary = record.get("state_summary")
    if not isinstance(summary, dict):
        raise ValueError("record is missing a state_summary object")

    player = int(record.get("player", 1))
    legal_payloads = record.get("legal_actions") or []
    if not isinstance(legal_payloads, list):
        raise ValueError("record legal_actions must be a list")
    legal = [action_from_payload(action) for action in legal_payloads]

    chosen_payload = record.get("chosen_action")
    if not isinstance(chosen_payload, dict):
        raise ValueError("record is missing a chosen_action object")
    chosen = action_from_payload(chosen_payload)

    if chosen not in legal:
        legal.append(chosen)
    return summary, player, legal, chosen


@dataclass
class BackendLinearPolicyValueAgent:
    """Linear policy/value model trained from backend self-play JSONL records.

    This deliberately consumes backend summaries instead of Python BattleState
    objects. It is the first training path that can learn from Showdown-backed
    self-play records.
    """

    policy_weights: dict[str, float] = field(default_factory=dict)
    value_weights: dict[str, float] = field(default_factory=dict)
    learning_rate: float = 0.05
    name: str = "backend-linear-agent"
    model_schema_version: int = MODEL_SCHEMA_VERSION
    feature_schema_version: int = FEATURE_SCHEMA_VERSION

    def score_action(self, summary: dict[str, Any], player: int, action: Action | dict[str, Any]) -> float:
        return dot(self.policy_weights, backend_action_features(summary, player, action))

    def action_priors(
        self,
        summary: dict[str, Any],
        player: int,
        actions: list[Action | dict[str, Any]],
    ) -> dict[Action, float]:
        parsed = [action_from_payload(action) for action in actions]
        if not parsed:
            return {}
        scores = [self.score_action(summary, player, action) for action in parsed]
        probs = softmax_scores(scores)
        return {action: probs[index] for index, action in enumerate(parsed)}

    def evaluate(self, summary: dict[str, Any], player: int) -> float:
        raw = dot(self.value_weights, backend_state_features(summary, player))
        return 2 * stable_sigmoid(raw) - 1

    def choose_action(
        self,
        summary: dict[str, Any],
        player: int,
        actions: list[Action | dict[str, Any]],
        *,
        temperature: float = 0.0,
        rng: random.Random | None = None,
    ) -> Action:
        parsed = [action_from_payload(action) for action in actions]
        if not parsed:
            raise ValueError("No legal actions to choose from.")
        rng = rng or random.Random()
        scores = [self.score_action(summary, player, action) for action in parsed]
        if temperature <= 0:
            return parsed[max(range(len(parsed)), key=lambda i: scores[i])]

        scaled = [score / max(temperature, 1e-6) for score in scores]
        probs = softmax_scores(scaled)
        r = rng.random()
        c = 0.0
        for action, prob in zip(parsed, probs):
            c += prob
            if c >= r:
                return action
        return parsed[-1]

    def update_policy_toward(
        self,
        summary: dict[str, Any],
        player: int,
        chosen: Action | dict[str, Any],
        legal: list[Action | dict[str, Any]],
    ) -> dict[str, float]:
        parsed_chosen = action_from_payload(chosen)
        parsed_legal = [action_from_payload(action) for action in legal]
        if parsed_chosen not in parsed_legal:
            parsed_legal.append(parsed_chosen)
        if not parsed_legal:
            return {"policy_loss": 0.0, "chosen_probability": 0.0}

        priors = self.action_priors(summary, player, parsed_legal)
        chosen_prob = max(1e-12, priors.get(parsed_chosen, 1e-12))
        chosen_features = backend_action_features(summary, player, parsed_chosen)

        expected: dict[str, float] = {}
        for action, prob in priors.items():
            for key, value in backend_action_features(summary, player, action).items():
                expected[key] = expected.get(key, 0.0) + prob * value

        for key, value in chosen_features.items():
            gradient = value - expected.get(key, 0.0)
            if gradient:
                self.policy_weights[key] = self.policy_weights.get(key, 0.0) + self.learning_rate * gradient

        return {
            "policy_loss": -math.log(chosen_prob),
            "chosen_probability": chosen_prob,
        }

    def update_value(self, summary: dict[str, Any], player: int, target_value: float) -> dict[str, float]:
        target = max(-1.0, min(1.0, float(target_value)))
        prediction = self.evaluate(summary, player)
        error = target - prediction
        for key, value in backend_state_features(summary, player).items():
            if value:
                self.value_weights[key] = self.value_weights.get(key, 0.0) + self.learning_rate * error * value
        return {
            "value_prediction": prediction,
            "value_error": error,
            "value_loss": error * error,
        }

    def update_from_record(self, record: dict[str, Any]) -> dict[str, float | str | None]:
        summary, player, legal, chosen = _record_context(record)
        metrics: dict[str, float | str | None] = {
            "action_label": backend_action_label(chosen),
            "policy_loss": None,
            "chosen_probability": None,
            "value_prediction": None,
            "value_error": None,
            "value_loss": None,
        }

        policy_metrics = self.update_policy_toward(summary, player, chosen, legal)
        metrics.update(policy_metrics)

        target = _target_value(record)
        if target is not None:
            metrics.update(self.update_value(summary, player, target))
        return metrics

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_type": "BackendLinearPolicyValueAgent",
            "model_schema_version": self.model_schema_version,
            "feature_schema_version": self.feature_schema_version,
            "name": self.name,
            "learning_rate": self.learning_rate,
            "policy_weights": self.policy_weights,
            "value_weights": self.value_weights,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BackendLinearPolicyValueAgent":
        return cls(
            policy_weights=dict(data.get("policy_weights", {})),
            value_weights=dict(data.get("value_weights", {})),
            learning_rate=float(data.get("learning_rate", 0.05)),
            name=str(data.get("name", "backend-linear-agent")),
            model_schema_version=int(data.get("model_schema_version", MODEL_SCHEMA_VERSION)),
            feature_schema_version=int(data.get("feature_schema_version", FEATURE_SCHEMA_VERSION)),
        )

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "BackendLinearPolicyValueAgent":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
