from __future__ import annotations

from .data import MOVES, SPECIES, effectiveness
from .engine import effective_speed
from .model import Action, BattleState, PokemonState


def _team(state: BattleState, player: int):
    return state.p1 if player == 1 else state.p2


def _hp_fraction(mon: PokemonState) -> float:
    return 0.0 if mon.max_hp <= 0 else mon.hp / mon.max_hp


def state_features(state: BattleState, player: int) -> dict[str, float]:
    own = _team(state, player)
    opp = _team(state, 3 - player)
    a = own.active_mon()
    b = opp.active_mon()

    own_hp = sum(_hp_fraction(m) for m in own.mons if not m.fainted)
    opp_hp = sum(_hp_fraction(m) for m in opp.mons if not m.fainted)

    return {
        "bias": 1.0,
        "own_alive": own.alive_count() / 6,
        "opp_alive": opp.alive_count() / 6,
        "alive_diff": (own.alive_count() - opp.alive_count()) / 6,
        "own_total_hp": own_hp / 6,
        "opp_total_hp": opp_hp / 6,
        "total_hp_diff": (own_hp - opp_hp) / 6,
        "active_hp": _hp_fraction(a),
        "opp_active_hp": _hp_fraction(b),
        "active_hp_diff": _hp_fraction(a) - _hp_fraction(b),
        "faster": 1.0 if effective_speed(a, state) > effective_speed(b, state) else 0.0,
        "has_status": 1.0 if a.status else 0.0,
        "opp_has_status": 1.0 if b.status else 0.0,
        "own_hazards": float(own.side.stealth_rock) + own.side.spikes + own.side.toxic_spikes,
        "opp_hazards": float(opp.side.stealth_rock) + opp.side.spikes + opp.side.toxic_spikes,
        "weather": 1.0 if state.field.weather else 0.0,
        "trick_room": 1.0 if state.field.trick_room_turns > 0 else 0.0,
    }


def action_features(state: BattleState, player: int, action: Action) -> dict[str, float]:
    own = _team(state, player)
    opp = _team(state, 3 - player)
    actor = own.active_mon()
    target = opp.active_mon()
    features = state_features(state, player)

    features.update({
        "action_is_move": 1.0 if action.kind == "move" else 0.0,
        "action_is_switch": 1.0 if action.kind == "switch" else 0.0,
        "move_power": 0.0,
        "move_accuracy": 0.0,
        "move_priority": 0.0,
        "move_stab": 0.0,
        "move_effectiveness": 1.0,
        "move_super_effective": 0.0,
        "move_resisted": 0.0,
        "move_immune": 0.0,
        "move_status": 0.0,
        "move_recovery": 0.0,
        "move_hazard": 0.0,
        "move_boost": 0.0,
    })

    if action.kind == "move" and action.index < len(actor.moves):
        move_name = actor.moves[action.index]
        move = MOVES[move_name]
        eff = effectiveness(move.type, SPECIES[target.species].types, target.ability)
        features.update({
            "move_power": min(move.power, 150) / 150,
            "move_accuracy": move.accuracy / 100,
            "move_priority": move.priority / 7,
            "move_stab": 1.0 if move.type in SPECIES[actor.species].types else 0.0,
            "move_effectiveness": eff,
            "move_super_effective": 1.0 if eff > 1 else 0.0,
            "move_resisted": 1.0 if 0 < eff < 1 else 0.0,
            "move_immune": 1.0 if eff == 0 else 0.0,
            "move_status": 1.0 if move.category == "status" else 0.0,
            "move_recovery": 1.0 if move.heal_fraction or move.effect in {"recover", "rest"} else 0.0,
            "move_hazard": 1.0 if move.effect in {"stealth_rock", "spikes", "toxic_spikes"} else 0.0,
            "move_boost": 1.0 if move.boost_self else 0.0,
        })

    if action.kind == "switch" and action.index < len(own.mons):
        switch_target = own.mons[action.index]
        features["switch_hp"] = _hp_fraction(switch_target)
        features["switch_has_status"] = 1.0 if switch_target.status else 0.0
    else:
        features["switch_hp"] = 0.0
        features["switch_has_status"] = 0.0

    return features


def dot(weights: dict[str, float], features: dict[str, float]) -> float:
    return sum(weights.get(k, 0.0) * v for k, v in features.items())


def action_label(state: BattleState, player: int, action: Action) -> str:
    mon = _team(state, player).active_mon()
    if action.kind == "move":
        move_name = mon.moves[action.index] if action.index < len(mon.moves) else f"move[{action.index}]"
        return f"move:{move_name}"
    team = _team(state, player)
    species = team.mons[action.index].species if action.index < len(team.mons) else f"slot[{action.index}]"
    return f"switch:{species}"


def state_summary(state: BattleState) -> dict:
    from .data import SPECIES

    def side_summary(team):
        active = team.active_mon()
        species_data = SPECIES.get(active.species)
        return {
            "active": active.species,
            "types": list(species_data.types) if species_data is not None else [],
            "level": active.set.level,
            "stats": dict(active.stats),
            "boosts": dict(active.boosts),
            "ability": active.ability,
            "item": active.item,
            "hp": active.hp,
            "max_hp": active.max_hp,
            "status": active.status,
            "alive": team.alive_count(),
            "hazards": {
                "sr": team.side.stealth_rock,
                "spikes": team.side.spikes,
                "toxic_spikes": team.side.toxic_spikes,
            },
        }

    return {
        "turn": state.field.turn,
        "weather": state.field.weather,
        "trick_room_turns": state.field.trick_room_turns,
        "winner": state.winner,
        "p1": side_summary(state.p1),
        "p2": side_summary(state.p2),
    }
