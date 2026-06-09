from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json
from typing import Any, Iterable

from battle_engine.backend_features import FEATURE_SCHEMA_VERSION, backend_record_features


VALID_WINNERS = {None, 1, 2, "None", "null", "1", "2"}
VALID_ACTION_KINDS = {"move", "switch"}


@dataclass
class BackendJsonlValidationReport:
    paths: list[str]
    valid: bool = True
    records: int = 0
    decision_records: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    action_kind_counts: dict[str, int] = field(default_factory=dict)
    chosen_kind_counts: dict[str, int] = field(default_factory=dict)
    winner_counts: dict[str, int] = field(default_factory=dict)
    backend_counts: dict[str, int] = field(default_factory=dict)
    player_counts: dict[str, int] = field(default_factory=dict)
    move_actions: int = 0
    move_actions_with_metadata: int = 0
    switch_actions: int = 0
    switch_actions_with_metadata: int = 0
    feature_schema_version: int = FEATURE_SCHEMA_VERSION

    @property
    def move_metadata_rate(self) -> float:
        return self.move_actions_with_metadata / self.move_actions if self.move_actions else 0.0

    @property
    def switch_metadata_rate(self) -> float:
        return self.switch_actions_with_metadata / self.switch_actions if self.switch_actions else 0.0

    def add_error(self, message: str) -> None:
        self.valid = False
        self.errors.append(message)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "paths": self.paths,
            "valid": self.valid,
            "records": self.records,
            "decision_records": self.decision_records,
            "errors": self.errors,
            "warnings": self.warnings,
            "action_kind_counts": dict(sorted(self.action_kind_counts.items())),
            "chosen_kind_counts": dict(sorted(self.chosen_kind_counts.items())),
            "winner_counts": dict(sorted(self.winner_counts.items())),
            "backend_counts": dict(sorted(self.backend_counts.items())),
            "player_counts": dict(sorted(self.player_counts.items())),
            "move_actions": self.move_actions,
            "move_actions_with_metadata": self.move_actions_with_metadata,
            "move_metadata_rate": self.move_metadata_rate,
            "switch_actions": self.switch_actions,
            "switch_actions_with_metadata": self.switch_actions_with_metadata,
            "switch_metadata_rate": self.switch_metadata_rate,
            "feature_schema_version": self.feature_schema_version,
        }


def _count(counter: dict[str, int], key: Any) -> None:
    text = str(key)
    counter[text] = counter.get(text, 0) + 1


def _action_key(action: Any) -> tuple[str, int] | None:
    if not isinstance(action, dict):
        return None
    try:
        return str(action.get("kind")), int(action.get("index", 0))
    except (TypeError, ValueError):
        return None


def _hp_fraction_ok(side: Any) -> bool:
    if not isinstance(side, dict):
        return False
    value = side.get("hp_fraction")
    if value is None and isinstance(side.get("mons"), list):
        return True
    if value is None:
        hp = side.get("hp")
        max_hp = side.get("max_hp")
        if hp is None or max_hp is None:
            return True
        try:
            return float(max_hp) >= 0 and float(hp) >= 0
        except (TypeError, ValueError):
            return False
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return False
    return 0.0 <= numeric <= 1.0


def _move_has_metadata(action: dict[str, Any]) -> bool:
    return any(action.get(key) not in {None, ""} for key in ("id", "name", "type", "category", "base_power", "accuracy"))


def _switch_has_metadata(action: dict[str, Any]) -> bool:
    return any(action.get(key) not in {None, ""} for key in ("species", "hp", "max_hp", "hp_fraction", "types", "status"))


def iter_backend_jsonl(paths: Iterable[Path]) -> Iterable[tuple[Path, int, dict[str, Any]]]:
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    payload = json.loads(stripped)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
                if not isinstance(payload, dict):
                    raise ValueError(f"{path}:{line_number}: expected JSON object, got {type(payload).__name__}")
                yield path, line_number, payload


def validate_backend_jsonl(paths: list[Path], *, strict_metadata: bool = False) -> BackendJsonlValidationReport:
    report = BackendJsonlValidationReport(paths=[str(path) for path in paths])

    for path in paths:
        if not path.exists():
            report.add_error(f"{path}: file does not exist")

    existing = [path for path in paths if path.exists()]
    if not existing:
        return report

    try:
        iterator = iter_backend_jsonl(existing)
        for path, line_number, record in iterator:
            loc = f"{path}:{line_number}"
            report.records += 1
            if record.get("record_type") != "decision":
                report.add_warning(f"{loc}: skipping non-decision record_type={record.get('record_type')!r}")
                continue

            report.decision_records += 1
            _count(report.backend_counts, record.get("backend", "unknown"))
            _count(report.player_counts, record.get("player", "unknown"))
            _count(report.winner_counts, record.get("final_winner"))

            player = record.get("player")
            if player not in {1, 2, "1", "2"}:
                report.add_error(f"{loc}: player must be 1 or 2, got {player!r}")

            winner = record.get("final_winner")
            if winner not in VALID_WINNERS:
                report.add_error(f"{loc}: final_winner must be None/1/2, got {winner!r}")

            value_target = record.get("value_target")
            if value_target is not None:
                try:
                    numeric = float(value_target)
                except (TypeError, ValueError):
                    report.add_error(f"{loc}: value_target must be numeric or null, got {value_target!r}")
                else:
                    if numeric < -1.0 or numeric > 1.0:
                        report.add_error(f"{loc}: value_target should be in [-1, 1], got {numeric}")

            summary = record.get("state_summary")
            if not isinstance(summary, dict):
                report.add_error(f"{loc}: missing state_summary object")
                continue
            for side_name in ("p1", "p2"):
                side = summary.get(side_name)
                if not isinstance(side, dict):
                    report.add_error(f"{loc}: state_summary.{side_name} must be an object")
                elif not _hp_fraction_ok(side):
                    report.add_error(f"{loc}: state_summary.{side_name} has invalid HP fields")

            legal_actions = record.get("legal_actions")
            if not isinstance(legal_actions, list):
                report.add_error(f"{loc}: legal_actions must be a list")
                legal_actions = []
            elif not legal_actions:
                report.add_error(f"{loc}: legal_actions is empty")

            legal_keys: set[tuple[str, int]] = set()
            for action_index, action in enumerate(legal_actions):
                key = _action_key(action)
                if key is None:
                    report.add_error(f"{loc}: legal_actions[{action_index}] must have kind/index")
                    continue
                kind, _idx = key
                _count(report.action_kind_counts, kind)
                legal_keys.add(key)
                if kind not in VALID_ACTION_KINDS:
                    report.add_warning(f"{loc}: legal_actions[{action_index}] has unexpected kind {kind!r}")
                if kind == "move":
                    report.move_actions += 1
                    if _move_has_metadata(action):
                        report.move_actions_with_metadata += 1
                elif kind == "switch":
                    report.switch_actions += 1
                    if _switch_has_metadata(action):
                        report.switch_actions_with_metadata += 1

            chosen = record.get("chosen_action")
            chosen_key = _action_key(chosen)
            if chosen_key is None:
                report.add_error(f"{loc}: chosen_action must have kind/index")
            else:
                _count(report.chosen_kind_counts, chosen_key[0])
                if legal_keys and chosen_key not in legal_keys:
                    report.add_error(f"{loc}: chosen_action {chosen_key} is not present in legal_actions")

            try:
                backend_record_features(record)
            except Exception as exc:
                report.add_error(f"{loc}: feature extraction failed: {exc}")
    except ValueError as exc:
        report.add_error(str(exc))

    if report.decision_records == 0:
        report.add_error("no decision records found")

    if report.move_actions and report.move_metadata_rate < 0.5:
        msg = f"low move metadata coverage: {report.move_metadata_rate:.1%}"
        if strict_metadata:
            report.add_error(msg)
        else:
            report.add_warning(msg)

    if report.switch_actions and report.switch_metadata_rate < 0.5:
        msg = f"low switch metadata coverage: {report.switch_metadata_rate:.1%}"
        if strict_metadata:
            report.add_error(msg)
        else:
            report.add_warning(msg)

    return report
