from __future__ import annotations

from collections import Counter
import math

from .data import MOVES, SPECIES, effectiveness
from .model import PokemonSet


HAZARD_MOVES = {"Stealth Rock", "Spikes", "Toxic Spikes"}
REMOVAL_MOVES = {"Rapid Spin", "Defog"}
PIVOT_MOVES = {"U-turn", "Volt Switch", "Teleport", "Baton Pass"}
RECOVERY_MOVES = {"Recover", "Roost", "Soft-Boiled", "Slack Off", "Synthesis", "Moonlight", "Morning Sun", "Rest", "Giga Drain", "Drain Punch"}
SETUP_MOVES = {"Swords Dance", "Dragon Dance", "Calm Mind", "Nasty Plot", "Bulk Up", "Curse", "Quiver Dance", "Shell Smash"}
STATUS_MOVES = {"Toxic", "Will-O-Wisp", "Thunder Wave", "Spore", "Sleep Powder", "Stun Spore", "Leech Seed"}
PHASING_MOVES = {"Roar", "Whirlwind", "Dragon Tail"}
CLERIC_MOVES = {"Heal Bell", "Aromatherapy", "Wish"}
SCREEN_MOVES = {"Reflect", "Light Screen", "Safeguard"}
PRIORITY_MOVES = {"Bullet Punch", "Mach Punch", "Ice Shard", "Extreme Speed", "Vacuum Wave", "Aqua Jet", "Shadow Sneak", "Sucker Punch"}
TRICK_ROOM_MOVES = {"Trick Room"}
CHOICE_ITEMS = {"Choice Band", "Choice Specs", "Choice Scarf"}
WEATHER_SETTERS = {"Sand Stream", "Drizzle", "Drought"}
WEATHER_ABUSERS = {"Sand Rush", "Swift Swim", "Chlorophyll"}

ATTACKING_ROLE_THRESHOLD = 110
SPEED_ROLE_THRESHOLD = 100


def _types(pokeset: PokemonSet) -> tuple[str, ...]:
    return SPECIES[pokeset.species].types if pokeset.species in SPECIES else ()


def _stats(pokeset: PokemonSet) -> dict[str, int]:
    return SPECIES[pokeset.species].base_stats if pokeset.species in SPECIES else {}


def infer_set_tags(pokeset: PokemonSet) -> set[str]:
    """Infer broad team-building roles from a set.

    These are heuristics, not truth. The point is to give the learner stable
    composition features that roughly match competitive language.
    """
    tags: set[str] = set()
    moves = set(pokeset.moves)
    stats = _stats(pokeset)
    types = set(_types(pokeset))

    if moves & HAZARD_MOVES:
        tags.add("hazard_setter")
    if moves & REMOVAL_MOVES:
        tags.add("hazard_removal")
    if moves & PIVOT_MOVES:
        tags.add("pivot")
    if moves & RECOVERY_MOVES:
        tags.add("recovery")
    if moves & SETUP_MOVES:
        tags.add("setup")
    if moves & STATUS_MOVES:
        tags.add("status_spreader")
    if moves & PHASING_MOVES:
        tags.add("phazer")
    if moves & CLERIC_MOVES:
        tags.add("cleric")
    if moves & SCREEN_MOVES:
        tags.add("screen_support")
    if moves & PRIORITY_MOVES:
        tags.add("priority")
    if moves & TRICK_ROOM_MOVES:
        tags.add("trick_room_setter")

    if pokeset.item in CHOICE_ITEMS:
        tags.add("choice_user")
    if pokeset.item == "Choice Scarf":
        tags.add("revenge_killer")
        tags.add("speed_control")
    if pokeset.item in {"Choice Band", "Choice Specs", "Life Orb"}:
        tags.add("wallbreaker")

    if pokeset.ability in WEATHER_SETTERS:
        tags.add("weather_setter")
    if pokeset.ability in WEATHER_ABUSERS:
        tags.add("weather_abuser")
        tags.add("speed_control")

    if stats:
        if stats.get("atk", 0) >= ATTACKING_ROLE_THRESHOLD:
            tags.add("physical_attacker")
        if stats.get("spa", 0) >= ATTACKING_ROLE_THRESHOLD:
            tags.add("special_attacker")
        if stats.get("spe", 0) >= SPEED_ROLE_THRESHOLD:
            tags.add("fast")
            tags.add("speed_control")
        if stats.get("hp", 0) + stats.get("def", 0) >= 190:
            tags.add("physical_wall")
        if stats.get("hp", 0) + stats.get("spd", 0) >= 190:
            tags.add("special_wall")
        if tags & {"physical_wall", "special_wall"}:
            tags.add("defensive_backbone")

    for t in types:
        tags.add(f"type:{t}")

    if "Flying" in types or pokeset.ability == "Levitate":
        tags.add("ground_immune")
    if "Ground" in types or pokeset.ability in {"Volt Absorb", "Lightning Rod"}:
        tags.add("electric_immune")
    if pokeset.ability in {"Water Absorb", "Storm Drain"}:
        tags.add("water_immune")
    if pokeset.ability == "Flash Fire":
        tags.add("fire_immune")
    if "Ghost" in types:
        tags.add("spinblocker")
        tags.add("normal_immune")
        tags.add("fighting_immune")
    if "Steel" in types:
        tags.add("dragon_resist")
        tags.add("steel_type")
    if "Dark" in types:
        tags.add("psychic_immune")

    damaging_moves = [MOVES[m] for m in pokeset.moves if m in MOVES and MOVES[m].category != "status" and MOVES[m].power > 0]
    for move in damaging_moves:
        tags.add(f"coverage:{move.type}")

    if not damaging_moves:
        tags.add("passive")

    return tags


def set_role_summary(pokeset: PokemonSet) -> dict:
    tags = sorted(infer_set_tags(pokeset))
    return {
        "species": pokeset.species,
        "item": pokeset.item,
        "ability": pokeset.ability,
        "moves": list(pokeset.moves),
        "tags": tags,
    }


def team_tag_counts(team: list[PokemonSet]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for pokeset in team:
        counts.update(infer_set_tags(pokeset))
    return counts


def _team_weakness_resist_counts(team: list[PokemonSet]) -> tuple[Counter[str], Counter[str], Counter[str]]:
    weaknesses: Counter[str] = Counter()
    resists: Counter[str] = Counter()
    immunities: Counter[str] = Counter()
    attacking_types = sorted(MOVES.keys())  # only used for canonical move list below

    all_types = {
        "Normal", "Fire", "Water", "Electric", "Grass", "Ice", "Fighting", "Poison",
        "Ground", "Flying", "Psychic", "Bug", "Rock", "Ghost", "Dragon", "Dark", "Steel",
    }

    for pokeset in team:
        types = _types(pokeset)
        for attack_type in all_types:
            eff = effectiveness(attack_type, types, pokeset.ability)
            if eff == 0:
                immunities[attack_type] += 1
            elif eff > 1:
                weaknesses[attack_type] += 1
            elif eff < 1:
                resists[attack_type] += 1
    return weaknesses, resists, immunities


def team_features(team: list[PokemonSet]) -> dict[str, float]:
    size = max(1, len(team))
    counts = team_tag_counts(team)
    weaknesses, resists, immunities = _team_weakness_resist_counts(team)

    features: dict[str, float] = {"team_bias": 1.0}

    # Role counts normalized to team size.
    for tag, count in counts.items():
        safe_tag = tag.replace(":", "_")
        features[f"team_tag_{safe_tag}"] = count / size

    # Explicit role sufficiency / gaps. These are deliberately opinionated.
    required = {
        "hazard_setter": 1,
        "hazard_removal": 1,
        "pivot": 1,
        "speed_control": 1,
        "physical_attacker": 1,
        "special_attacker": 1,
        "defensive_backbone": 2,
        "status_spreader": 1,
    }
    for role, target in required.items():
        count = counts.get(role, 0)
        features[f"team_has_{role}"] = 1.0 if count >= target else 0.0
        features[f"team_missing_{role}"] = 1.0 if count < target else 0.0
        features[f"team_count_{role}"] = count / size

    features["team_role_diversity"] = len([tag for tag, count in counts.items() if count > 0 and not tag.startswith("type:")]) / 30
    features["team_unique_species"] = len({p.species for p in team}) / size
    features["team_choice_users"] = counts.get("choice_user", 0) / size
    features["team_setup_users"] = counts.get("setup", 0) / size
    features["team_priority_users"] = counts.get("priority", 0) / size
    features["team_recovery_users"] = counts.get("recovery", 0) / size

    # Penalize obvious structural stack-ups.
    features["team_many_steels"] = 1.0 if counts.get("type:Steel", 0) >= 3 else 0.0
    features["team_many_grounds"] = 1.0 if counts.get("type:Ground", 0) >= 3 else 0.0
    features["team_no_ground_immunity"] = 1.0 if counts.get("ground_immune", 0) == 0 else 0.0
    features["team_no_electric_immunity"] = 1.0 if counts.get("electric_immune", 0) == 0 else 0.0

    for attack_type in sorted(weaknesses):
        features[f"weak_to_{attack_type}"] = weaknesses[attack_type] / size
        features[f"resists_{attack_type}"] = resists[attack_type] / size
        features[f"immune_to_{attack_type}"] = immunities[attack_type] / size
        features[f"bad_{attack_type}_weakness_stack"] = 1.0 if weaknesses[attack_type] >= 3 and resists[attack_type] + immunities[attack_type] == 0 else 0.0

    return features


def team_summary(team: list[PokemonSet]) -> dict:
    counts = team_tag_counts(team)
    core_roles = [
        "hazard_setter",
        "hazard_removal",
        "pivot",
        "speed_control",
        "physical_attacker",
        "special_attacker",
        "defensive_backbone",
        "status_spreader",
        "setup",
        "priority",
        "recovery",
    ]
    return {
        "members": [set_role_summary(p) for p in team],
        "role_counts": {role: counts.get(role, 0) for role in core_roles},
        "top_tags": dict(counts.most_common(20)),
        "features": team_features(team),
    }


def short_team_label(team: list[PokemonSet]) -> str:
    return " / ".join(p.species for p in team)
