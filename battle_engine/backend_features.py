from __future__ import annotations

from typing import Any

from .model import Action

FEATURE_SCHEMA_VERSION = 1
TEAM_SIZE = 6

_STATUS_KEYS = {
    "brn": "burn",
    "burn": "burn",
    "psn": "poison",
    "poison": "poison",
    "tox": "toxic",
    "toxic": "toxic",
    "par": "paralysis",
    "paralysis": "paralysis",
    "slp": "sleep",
    "sleep": "sleep",
    "frz": "freeze",
    "freeze": "freeze",
}

_WEATHER_ALIASES = {
    "sand": "sandstorm",
    "sandstorm": "sandstorm",
    "raindance": "rain",
    "rain": "rain",
    "rainy": "rain",
    "sunnyday": "sun",
    "sun": "sun",
    "harshsunshine": "sun",
    "hail": "hail_or_snow",
    "snow": "hail_or_snow",
}

_TERRAIN_ALIASES = {
    "electricterrain": "electric",
    "electric": "electric",
    "grassyterrain": "grassy",
    "grassy": "grassy",
    "mistyterrain": "misty",
    "misty": "misty",
    "psychicterrain": "psychic",
    "psychic": "psychic",
}

STATE_FEATURE_NAMES = (
    "bias",
    "own_active_hp",
    "opp_active_hp",
    "active_hp_diff",
    "own_alive",
    "opp_alive",
    "alive_diff",
    "own_needs_replacement",
    "opp_needs_replacement",
    "weather_sandstorm",
    "weather_rain",
    "weather_sun",
    "weather_hail_or_snow",
    "weather_other",
    "terrain_any",
    "own_hazards_any",
    "opp_hazards_any",
    "own_stealth_rock",
    "opp_stealth_rock",
    "own_spikes",
    "opp_spikes",
    "own_toxic_spikes",
    "opp_toxic_spikes",
    "own_status_any",
    "opp_status_any",
    "own_status_burn",
    "opp_status_burn",
    "own_status_poison",
    "opp_status_poison",
    "own_status_toxic",
    "opp_status_toxic",
    "own_status_paralysis",
    "opp_status_paralysis",
    "own_status_sleep",
    "opp_status_sleep",
    "own_status_freeze",
    "opp_status_freeze",
)

ACTION_FEATURE_NAMES = STATE_FEATURE_NAMES + (
    "action_is_move",
    "action_is_switch",
    "action_index_norm",
    "action_index_0",
    "action_index_1",
    "action_index_2",
    "action_index_3",
    "action_index_4",
    "action_index_5",
    "move_when_opp_low_hp",
    "move_when_own_low_hp",
    "switch_when_own_low_hp",
    "switch_when_opp_low_hp",
    "switch_with_own_hazards",
    "switch_when_own_statused",
)


def _number(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _flag(value: Any) -> float:
    return 1.0 if bool(value) else 0.0


def _safe_fraction(numerator: Any, denominator: Any) -> float:
    den = _number(denominator)
    if den <= 0:
        return 0.0
    return max(0.0, min(1.0, _number(numerator) / den))


def _normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text or text in {"none", "null", "0"}:
        return None
    return "".join(ch for ch in text if ch.isalnum() or ch == "_")


def _normalize_status(value: Any) -> str | None:
    text = _normalize_text(value)
    if text is None:
        return None
    return _STATUS_KEYS.get(text, text)


def _normalize_weather(value: Any) -> str | None:
    text = _normalize_text(value)
    if text is None:
        return None
    return _WEATHER_ALIASES.get(text, text)


def _normalize_terrain(value: Any) -> str | None:
    text = _normalize_text(value)
    if text is None:
        return None
    return _TERRAIN_ALIASES.get(text, text)


def _side(summary: dict[str, Any], player: int) -> dict[str, Any]:
    if player not in {1, 2}:
        raise ValueError(f"player must be 1 or 2, got {player!r}")
    side = summary.get(f"p{player}") or {}
    return side if isinstance(side, dict) else {}


def _active_showdown_mon(side: dict[str, Any]) -> dict[str, Any]:
    mons = side.get("mons") or []
    if not isinstance(mons, list):
        return {}

    active_index = side.get("active_index")
    if isinstance(active_index, int) and 0 <= active_index < len(mons):
        mon = mons[active_index]
        return mon if isinstance(mon, dict) else {}

    for mon in mons:
        if isinstance(mon, dict) and mon.get("active"):
            return mon
    return {}


def _active_mon(side: dict[str, Any]) -> dict[str, Any]:
    # Showdown summaries expose a mons list. Python summaries expose active fields
    # directly on the side summary.
    if "mons" in side:
        return _active_showdown_mon(side)
    return side


def _active_hp_fraction(side: dict[str, Any]) -> float:
    mon = _active_mon(side)
    if "hp_fraction" in mon:
        return max(0.0, min(1.0, _number(mon.get("hp_fraction"))))
    return _safe_fraction(mon.get("hp"), mon.get("max_hp"))


def _alive_fraction(side: dict[str, Any]) -> float:
    alive = side.get("alive", side.get("alive_count"))
    if alive is None and isinstance(side.get("mons"), list):
        alive = sum(
            1
            for mon in side["mons"]
            if isinstance(mon, dict) and _number(mon.get("hp"), 0.0) > 0
        )
    return max(0.0, min(1.0, _number(alive) / TEAM_SIZE))


def _conditions(side: dict[str, Any]) -> dict[str, Any]:
    raw = side.get("hazards", side.get("side_conditions", side.get("conditions", {})))
    return raw if isinstance(raw, dict) else {}


def _condition_truthy(conditions: dict[str, Any], *names: str) -> bool:
    for name in names:
        value = conditions.get(name)
        if isinstance(value, bool):
            if value:
                return True
        elif _number(value) > 0:
            return True
    return False


def _condition_layers(conditions: dict[str, Any], *names: str) -> float:
    for name in names:
        if name in conditions:
            value = conditions[name]
            if isinstance(value, bool):
                return 1.0 if value else 0.0
            return max(0.0, _number(value))
    return 0.0


def _hazards(conditions: dict[str, Any]) -> dict[str, float]:
    stealth_rock = _flag(_condition_truthy(conditions, "sr", "stealth_rock", "Stealth Rock"))
    spikes = min(3.0, _condition_layers(conditions, "spikes", "Spikes")) / 3.0
    toxic_spikes = min(2.0, _condition_layers(conditions, "toxic_spikes", "toxicspikes", "Toxic Spikes")) / 2.0
    return {
        "stealth_rock": stealth_rock,
        "spikes": spikes,
        "toxic_spikes": toxic_spikes,
        "any": 1.0 if stealth_rock or spikes or toxic_spikes else 0.0,
    }


def _status_features(status: Any) -> dict[str, float]:
    normalized = _normalize_status(status)
    return {
        "any": 1.0 if normalized else 0.0,
        "burn": 1.0 if normalized == "burn" else 0.0,
        "poison": 1.0 if normalized == "poison" else 0.0,
        "toxic": 1.0 if normalized == "toxic" else 0.0,
        "paralysis": 1.0 if normalized == "paralysis" else 0.0,
        "sleep": 1.0 if normalized == "sleep" else 0.0,
        "freeze": 1.0 if normalized == "freeze" else 0.0,
    }


def _active_status(side: dict[str, Any]) -> Any:
    return _active_mon(side).get("status")


def _needs_replacement(side: dict[str, Any]) -> float:
    return _flag(side.get("needs_replacement", False))


def backend_state_features(summary: dict[str, Any], player: int) -> dict[str, float]:
    """Return backend-neutral value features from a backend state summary.

    The input may be either a PythonBattleBackend summary or a
    ShowdownBattleBackend summary. This intentionally uses only stable surface
    facts available in both paths so backend training can start before Python
    reconstructs full Showdown internals.
    """
    own = _side(summary, player)
    opp = _side(summary, 3 - player)

    own_hp = _active_hp_fraction(own)
    opp_hp = _active_hp_fraction(opp)
    own_alive = _alive_fraction(own)
    opp_alive = _alive_fraction(opp)
    own_hazards = _hazards(_conditions(own))
    opp_hazards = _hazards(_conditions(opp))
    own_status = _status_features(_active_status(own))
    opp_status = _status_features(_active_status(opp))
    weather = _normalize_weather(summary.get("weather"))
    terrain = _normalize_terrain(summary.get("terrain"))

    values = {
        "bias": 1.0,
        "own_active_hp": own_hp,
        "opp_active_hp": opp_hp,
        "active_hp_diff": own_hp - opp_hp,
        "own_alive": own_alive,
        "opp_alive": opp_alive,
        "alive_diff": own_alive - opp_alive,
        "own_needs_replacement": _needs_replacement(own),
        "opp_needs_replacement": _needs_replacement(opp),
        "weather_sandstorm": 1.0 if weather == "sandstorm" else 0.0,
        "weather_rain": 1.0 if weather == "rain" else 0.0,
        "weather_sun": 1.0 if weather == "sun" else 0.0,
        "weather_hail_or_snow": 1.0 if weather == "hail_or_snow" else 0.0,
        "weather_other": 1.0 if weather and weather not in {"sandstorm", "rain", "sun", "hail_or_snow"} else 0.0,
        "terrain_any": 1.0 if terrain else 0.0,
        "own_hazards_any": own_hazards["any"],
        "opp_hazards_any": opp_hazards["any"],
        "own_stealth_rock": own_hazards["stealth_rock"],
        "opp_stealth_rock": opp_hazards["stealth_rock"],
        "own_spikes": own_hazards["spikes"],
        "opp_spikes": opp_hazards["spikes"],
        "own_toxic_spikes": own_hazards["toxic_spikes"],
        "opp_toxic_spikes": opp_hazards["toxic_spikes"],
        "own_status_any": own_status["any"],
        "opp_status_any": opp_status["any"],
        "own_status_burn": own_status["burn"],
        "opp_status_burn": opp_status["burn"],
        "own_status_poison": own_status["poison"],
        "opp_status_poison": opp_status["poison"],
        "own_status_toxic": own_status["toxic"],
        "opp_status_toxic": opp_status["toxic"],
        "own_status_paralysis": own_status["paralysis"],
        "opp_status_paralysis": opp_status["paralysis"],
        "own_status_sleep": own_status["sleep"],
        "opp_status_sleep": opp_status["sleep"],
        "own_status_freeze": own_status["freeze"],
        "opp_status_freeze": opp_status["freeze"],
    }
    return {name: float(values[name]) for name in STATE_FEATURE_NAMES}


def action_from_payload(action: Action | dict[str, Any]) -> Action:
    if isinstance(action, Action):
        return action
    if not isinstance(action, dict):
        raise TypeError(f"action must be Action or dict, got {type(action).__name__}")
    return Action(str(action.get("kind")), int(action.get("index", 0)))


def backend_action_features(summary: dict[str, Any], player: int, action: Action | dict[str, Any]) -> dict[str, float]:
    """Return backend-neutral policy features for one legal action."""
    parsed = action_from_payload(action)
    features = backend_state_features(summary, player)

    action_index = max(0, int(parsed.index))
    own_hp = features["own_active_hp"]
    opp_hp = features["opp_active_hp"]
    own_hazards_any = features["own_hazards_any"]
    own_status_any = features["own_status_any"]

    values = {
        "action_is_move": 1.0 if parsed.kind == "move" else 0.0,
        "action_is_switch": 1.0 if parsed.kind == "switch" else 0.0,
        "action_index_norm": min(action_index, 5) / 5,
        "move_when_opp_low_hp": 1.0 if parsed.kind == "move" and opp_hp <= 0.25 else 0.0,
        "move_when_own_low_hp": 1.0 if parsed.kind == "move" and own_hp <= 0.25 else 0.0,
        "switch_when_own_low_hp": 1.0 if parsed.kind == "switch" and own_hp <= 0.25 else 0.0,
        "switch_when_opp_low_hp": 1.0 if parsed.kind == "switch" and opp_hp <= 0.25 else 0.0,
        "switch_with_own_hazards": 1.0 if parsed.kind == "switch" and own_hazards_any else 0.0,
        "switch_when_own_statused": 1.0 if parsed.kind == "switch" and own_status_any else 0.0,
    }
    for index in range(6):
        values[f"action_index_{index}"] = 1.0 if action_index == index else 0.0

    features.update(values)
    return {name: float(features[name]) for name in ACTION_FEATURE_NAMES}


def backend_action_label(action: Action | dict[str, Any]) -> str:
    parsed = action_from_payload(action)
    return f"{parsed.kind}:{parsed.index}"


def backend_record_features(record: dict[str, Any]) -> dict[str, dict[str, float]]:
    """Return state and chosen-action feature dicts for a self-play JSONL record."""
    summary = record.get("state_summary")
    chosen = record.get("chosen_action")
    player = int(record.get("player", 1))
    if not isinstance(summary, dict):
        raise ValueError("record is missing a state_summary object")
    if not isinstance(chosen, dict):
        raise ValueError("record is missing a chosen_action object")
    return {
        "state": backend_state_features(summary, player),
        "action": backend_action_features(summary, player, chosen),
    }


def dense_values(features: dict[str, float], names: tuple[str, ...]) -> list[float]:
    return [float(features.get(name, 0.0)) for name in names]
