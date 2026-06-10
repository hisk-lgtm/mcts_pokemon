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

def _normalize_action_targets(targets: dict[Action, float]) -> dict[Action, float]:
    positive = {action: max(0.0, float(weight)) for action, weight in targets.items() if weight and weight > 0}
    total = sum(positive.values())
    if total <= 0.0:
        return {}
    return {action: weight / total for action, weight in positive.items()}


def _policy_targets_from_mcts(record: dict[str, Any], legal: list[Action], chosen: Action) -> tuple[dict[Action, float], str]:
    """Extract a policy target distribution from root MCTS visit counts.

    Older records only have a single chosen action. Newer backend self-play
    records also include per-root-action MCTS stats. When available, those
    visits are a better target because they preserve MCTS uncertainty instead
    of collapsing the search result to one click.
    """
    mcts = record.get("mcts")
    stats = mcts.get("stats") if isinstance(mcts, dict) else None
    if not isinstance(stats, list):
        return {chosen: 1.0}, "chosen_action"

    targets: dict[Action, float] = {}
    for row in stats:
        if not isinstance(row, dict):
            continue
        action_payload = row.get("action")
        if not isinstance(action_payload, dict):
            continue
        try:
            visits = float(row.get("visits", 0.0))
        except (TypeError, ValueError):
            continue
        if visits <= 0.0:
            continue
        action = action_from_payload(action_payload)
        targets[action] = targets.get(action, 0.0) + visits

    normalized = _normalize_action_targets(targets)
    if not normalized:
        return {chosen: 1.0}, "chosen_action"

    for action in normalized:
        if action not in legal:
            legal.append(action)
    return normalized, "mcts_visits"

def action_to_payload(action: Action | dict[str, Any]) -> dict[str, Any]:
    parsed = action_from_payload(action)
    payload: dict[str, Any] = {"kind": parsed.kind, "index": parsed.index}
    if parsed.metadata:
        payload.update(parsed.metadata)
    return payload


def _top_contributions(
    weights: dict[str, float],
    features: dict[str, float],
    *,
    limit: int,
) -> list[dict[str, float | str]]:
    if limit <= 0:
        return []
    contributions: list[dict[str, float | str]] = []
    for name, value in features.items():
        weight = weights.get(name, 0.0)
        contribution = weight * value
        if contribution == 0.0:
            continue
        contributions.append(
            {
                "feature": name,
                "value": value,
                "weight": weight,
                "contribution": contribution,
            }
        )
    contributions.sort(key=lambda item: abs(float(item["contribution"])), reverse=True)
    return contributions[:limit]


def _top_weights(weights: dict[str, float], *, limit: int) -> list[dict[str, float | str]]:
    if limit <= 0:
        return []
    rows = [
        {"feature": name, "weight": weight}
        for name, weight in sorted(weights.items(), key=lambda item: abs(item[1]), reverse=True)
        if weight != 0.0
    ]
    return rows[:limit]


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

    def explain_action(
        self,
        summary: dict[str, Any],
        player: int,
        action: Action | dict[str, Any],
        *,
        top_contributions: int = 8,
    ) -> dict[str, Any]:
        parsed = action_from_payload(action)
        features = backend_action_features(summary, player, parsed)
        score = dot(self.policy_weights, features)
        return {
            "action": action_to_payload(parsed),
            "label": backend_action_label(parsed),
            "score": score,
            "top_contributions": _top_contributions(
                self.policy_weights,
                features,
                limit=top_contributions,
            ),
        }

    def rank_actions(
        self,
        summary: dict[str, Any],
        player: int,
        actions: list[Action | dict[str, Any]],
        *,
        top_contributions: int = 0,
    ) -> list[dict[str, Any]]:
        parsed = [action_from_payload(action) for action in actions]
        if not parsed:
            return []
        scores = [self.score_action(summary, player, action) for action in parsed]
        probabilities = softmax_scores(scores)
        rows: list[dict[str, Any]] = []
        for action, score, probability in zip(parsed, scores, probabilities):
            row = {
                "action": action_to_payload(action),
                "label": backend_action_label(action),
                "score": score,
                "probability": probability,
            }
            if top_contributions > 0:
                row["top_contributions"] = self.explain_action(
                    summary,
                    player,
                    action,
                    top_contributions=top_contributions,
                )["top_contributions"]
            rows.append(row)
        rows.sort(key=lambda row: float(row["score"]), reverse=True)
        return rows

    def top_weights(self, *, limit: int = 12) -> dict[str, list[dict[str, float | str]]]:
        return {
            "policy": _top_weights(self.policy_weights, limit=limit),
            "value": _top_weights(self.value_weights, limit=limit),
        }
    def update_policy_toward_distribution(
        self,
        summary: dict[str, Any],
        player: int,
        targets: dict[Action, float],
        legal: list[Action | dict[str, Any]],
    ) -> dict[str, float]:
        parsed_legal = [action_from_payload(action) for action in legal]
        normalized_targets = _normalize_action_targets(targets)
        for action in normalized_targets:
            if action not in parsed_legal:
                parsed_legal.append(action)
        if not parsed_legal or not normalized_targets:
            return {
                "policy_loss": 0.0,
                "chosen_probability": 0.0,
                "target_entropy": 0.0,
                "target_action_count": 0.0,
            }

        priors = self.action_priors(summary, player, parsed_legal)

        model_expected: dict[str, float] = {}
        for action, prob in priors.items():
            for key, value in backend_action_features(summary, player, action).items():
                model_expected[key] = model_expected.get(key, 0.0) + prob * value

        target_expected: dict[str, float] = {}
        policy_loss = 0.0
        target_entropy = 0.0
        for action, target_prob in normalized_targets.items():
            model_prob = max(1e-12, priors.get(action, 1e-12))
            policy_loss += -target_prob * math.log(model_prob)
            target_entropy += -target_prob * math.log(max(1e-12, target_prob))
            for key, value in backend_action_features(summary, player, action).items():
                target_expected[key] = target_expected.get(key, 0.0) + target_prob * value

        for key, target_value in target_expected.items():
            gradient = target_value - model_expected.get(key, 0.0)
            if gradient:
                self.policy_weights[key] = self.policy_weights.get(key, 0.0) + self.learning_rate * gradient

        chosen_action = max(normalized_targets.items(), key=lambda item: item[1])[0]
        return {
            "policy_loss": policy_loss,
            "chosen_probability": max(1e-12, priors.get(chosen_action, 1e-12)),
            "target_entropy": target_entropy,
            "target_action_count": float(len(normalized_targets)),
        }

    def update_policy_toward(
        self,
        summary: dict[str, Any],
        player: int,
        chosen: Action | dict[str, Any],
        legal: list[Action | dict[str, Any]],
    ) -> dict[str, float]:
        parsed_chosen = action_from_payload(chosen)
        return self.update_policy_toward_distribution(summary, player, {parsed_chosen: 1.0}, legal)

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
        policy_targets, target_source = _policy_targets_from_mcts(record, legal, chosen)
        metrics: dict[str, float | str | None] = {
            "action_label": backend_action_label(chosen),
            "policy_target_source": target_source,
            "policy_loss": None,
            "chosen_probability": None,
            "target_entropy": None,
            "target_action_count": None,
            "value_prediction": None,
            "value_error": None,
            "value_loss": None,
        }

        policy_metrics = self.update_policy_toward_distribution(summary, player, policy_targets, legal)
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
