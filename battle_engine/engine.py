from __future__ import annotations

import random
from typing import List

from .model import Action, BattleState, PokemonState, TeamState, TurnLog
from .data import MOVES, SPECIES, effectiveness


CHOICE_ITEMS = {"Choice Band", "Choice Specs", "Choice Scarf"}

PUNCHING_MOVES = {
    "Bullet Punch",
    "Drain Punch",
    "Fire Punch",
    "Ice Punch",
    "Mach Punch",
    "Meteor Mash",
    "Thunder Punch",
    "Vacuum Wave",
}

SLICING_MOVES = {
    "Air Slash",
    "Leaf Blade",
    "Night Slash",
    "Psycho Cut",
    "Razor Shell",
    "Sacred Sword",
}

REFLECTABLE_EFFECTS = {
    "leech_seed",
    "spikes",
    "stealth_rock",
    "taunt",
    "toxic_spikes",
}

PARTIAL_OR_PASSIVE_ABILITIES = {
    "Cursed Body",
    "Flame Body",
    "Inner Focus",
    "Pickpocket",
    "Pressure",
    "Steadfast",
}


def is_choice_item(item: str) -> bool:
    return item in CHOICE_ITEMS


def has_sheer_force_bonus(move) -> bool:
    return bool(move.ailment_chance or move.boost_target)


def attacker_ignores_defender_ability(attacker: PokemonState) -> bool:
    return attacker.ability == "Mold Breaker"


def effective_defender_ability(attacker: PokemonState, defender: PokemonState) -> str:
    return "" if attacker_ignores_defender_ability(attacker) else defender.ability


def is_reflectable_move(move) -> bool:
    return bool(move.ailment or move.effect in REFLECTABLE_EFFECTS)


def legal_actions(state: BattleState, player: int) -> List[Action]:
    team = state.p1 if player == 1 else state.p2
    active = team.active_mon()

    if active.fainted or active.hp <= 0:
        return [Action("switch", i) for i, m in enumerate(team.mons) if i != team.active and not m.fainted and m.hp > 0]

    actions: List[Action] = []
    if active.choice_locked_move and is_choice_item(active.item):
        for i, move in enumerate(active.moves):
            if move == active.choice_locked_move and move != active.disabled_move:
                actions.append(Action("move", i))
                break
    else:
        actions.extend(Action("move", i) for i, move in enumerate(active.moves) if move != active.disabled_move)

    if not is_trapped_by_ability(state, player):
        actions.extend(Action("switch", i) for i, m in enumerate(team.mons) if i != team.active and not m.fainted and m.hp > 0)
    return actions


def is_trapped_by_ability(state: BattleState, player: int) -> bool:
    mon = _team(state, player).active_mon()
    opponent = _team(state, 3 - player).active_mon()
    if mon.fainted or opponent.fainted:
        return False
    return opponent.ability == "Magnet Pull" and "Steel" in SPECIES[mon.species].types


def needs_replacement(state: BattleState, player: int) -> bool:
    team = _team(state, player)
    active = team.active_mon()
    return (active.fainted or active.hp <= 0) and team.alive_count() > 0


def replace_fainted(state: BattleState, player: int, new_index: int) -> tuple[BattleState, TurnLog]:
    """Choose the free replacement after the active Pokémon has fainted.

    This is not a hard switch and does not consume the next turn's action.
    Hazards and switch-in abilities still apply to the incoming Pokémon.
    """
    new = state.clone()
    log = TurnLog()

    if not needs_replacement(new, player):
        log.add(f"Player {player} does not need a replacement.")
        return new, log

    team = _team(new, player)
    if new_index < 0 or new_index >= len(team.mons):
        log.add(f"Invalid replacement index {new_index}.")
        return new, log

    incoming = team.mons[new_index]
    if new_index == team.active or incoming.fainted or incoming.hp <= 0:
        log.add(f"Cannot replace with {incoming.species}.")
        return new, log

    outgoing = team.active_mon()
    outgoing.boosts = {k: 0 for k in outgoing.boosts}
    outgoing.choice_locked_move = None

    team.active = new_index
    log.add(f"Player {player} sent out {incoming.species}.")
    apply_on_switch_in(new, player, log)
    check_winner(new, log)
    return new, log


def step(
    state: BattleState,
    p1_action: Action,
    p2_action: Action,
    *,
    debug_damage: bool = False,
) -> tuple[BattleState, TurnLog]:
    new = state.clone()
    log = TurnLog(debug_enabled=debug_damage)
    if new.winner is not None:
        log.add("Battle is already over.")
        return new, log

    waiting = [player for player in (1, 2) if needs_replacement(new, player)]
    if waiting:
        log.add(
            "Replacement required before the next turn: "
            + ", ".join(f"Player {player}" for player in waiting)
            + "."
        )
        return new, log

    for player in (1, 2):
        mon = _team(new, player).active_mon()
        mon.protected = False
        mon.last_damage_taken = 0
        mon.last_damage_category = None
        mon.last_damage_source_player = None

    action_pairs = [(1, p1_action), (2, p2_action)]
    action_by_player = dict(action_pairs)
    pre_turn_choice_locks = {
        1: _team(new, 1).active_mon().choice_locked_move,
        2: _team(new, 2).active_mon().choice_locked_move,
    }

    for player, action in action_pairs:
        if action.kind == "switch":
            do_switch(new, player, action.index, log)

    move_actions = [(player, action) for player, action in action_pairs if action.kind == "move"]
    move_actions.sort(key=lambda pa: _move_order_key(new, pa[0], pa[1]), reverse=True)

    if len(move_actions) == 2:
        k1 = _move_order_key(new, move_actions[0][0], move_actions[0][1])
        k2 = _move_order_key(new, move_actions[1][0], move_actions[1][1])
        if k1 == k2:
            rng = _rng(new)
            if rng.random() < 0.5:
                move_actions.reverse()

    moved_this_turn: set[int] = set()
    for player, action in move_actions:
        actor = _team(new, player).active_mon()
        target = _team(new, 3 - player).active_mon()
        if actor.fainted or actor.hp <= 0:
            continue
        if target.fainted or target.hp <= 0:
            log.add(f"{actor.species}'s move failed because there was no target.")
            continue
        if action.index >= len(actor.moves):
            log.add(f"{actor.species} has no move at index {action.index}.")
            continue
        opponent_action = action_by_player[3 - player]
        use_move(
            new,
            player,
            actor.moves[action.index],
            log,
            target_hard_switched=opponent_action.kind == "switch",
            pre_turn_choice_lock=pre_turn_choice_locks[player],
            target_already_moved=(3 - player) in moved_this_turn,
        )
        moved_this_turn.add(player)

    end_of_turn(new, log)
    check_winner(new, log)
    for player in (1, 2):
        if needs_replacement(new, player):
            log.add(f"Player {player} must choose a replacement.")
    new.field.turn += 1
    return new, log


def _team(state: BattleState, player: int) -> TeamState:
    return state.p1 if player == 1 else state.p2


def _rng(state: BattleState) -> random.Random:
    rng = random.Random(state.rng_seed)
    state.rng_seed = rng.randint(1, 2**31 - 1)
    return rng


def turn_order_speed_key(mon: PokemonState, state: BattleState) -> int:
    """Return the sortable speed key for move order.

    Higher keys act first because move actions are sorted with reverse=True.
    Under Trick Room, lower effective Speed should move first inside the same
    priority bracket, so the key is negated. Priority still beats Speed.
    """
    speed = effective_speed(mon, state)
    return -speed if state.field.trick_room_turns > 0 else speed


def _move_order_key(state: BattleState, player: int, action: Action) -> tuple[int, int]:
    mon = _team(state, player).active_mon()
    move_name = mon.moves[action.index]
    move = MOVES[move_name]
    return (move.priority, turn_order_speed_key(mon, state))


def effective_speed(mon: PokemonState, state: BattleState | None = None) -> int:
    spe = modified_stat(mon, "spe")
    if mon.status == "par":
        spe = max(1, spe // 4)
    if mon.item == "Choice Scarf":
        spe = int(spe * 1.5)
    if state is not None:
        if mon.ability == "Swift Swim" and state.field.weather == "rain":
            spe *= 2
        if mon.ability == "Sand Rush" and state.field.weather == "sand":
            spe *= 2
    return spe


def modified_stat(mon: PokemonState, stat: str) -> int:
    base = mon.stats[stat]
    stage = mon.boosts.get(stat, 0)
    if stage >= 0:
        value = base * (2 + stage) // 2
    else:
        value = base * 2 // (2 - stage)

    if stat == "atk":
        if mon.item == "Choice Band":
            value = int(value * 1.5)
        if mon.status == "brn" and mon.ability != "Guts":
            value = max(1, value // 2)
        if mon.ability == "Guts" and mon.status is not None:
            value = int(value * 1.5)

    if stat == "spa" and mon.item == "Choice Specs":
        value = int(value * 1.5)

    return max(1, value)


def defender_stat(
    mon: PokemonState,
    stat: str,
    state: BattleState,
    defender_player: int | None = None,
    *,
    ignore_screens: bool = False,
) -> int:
    value = modified_stat(mon, stat)
    if stat == "spd" and state.field.weather == "sand" and "Rock" in SPECIES[mon.species].types:
        value = int(value * 1.5)
    if defender_player is not None and not ignore_screens:
        side = _team(state, defender_player).side
        if stat == "def" and side.reflect_turns > 0:
            value = int(value * 2)
        if stat == "spd" and side.light_screen_turns > 0:
            value = int(value * 2)
    return max(1, value)


def protect_blocks_move(move) -> bool:
    if move.category != "status":
        return True
    if move.ailment:
        return True
    return move.effect in {
        "counter",
        "trick",
        "skill_swap",
        "taunt",
        "leech_seed",
        "pain_split",
        "force_switch",
        "unimplemented",
    }


def substitute_blocks_move(move, attacker: PokemonState | None = None) -> bool:
    if attacker is not None and attacker.ability == "Infiltrator":
        return False
    if move.category != "status":
        return False
    if move.ailment:
        return True
    return move.effect in {"trick", "skill_swap", "taunt", "leech_seed", "pain_split", "force_switch", "unimplemented"}


def use_move(
    state: BattleState,
    player: int,
    move_name: str,
    log: TurnLog,
    *,
    target_hard_switched: bool = False,
    pre_turn_choice_lock: str | None = None,
    bypass_sleep: bool = False,
    can_choice_lock: bool = True,
    target_already_moved: bool = False,
) -> None:
    actor = _team(state, player).active_mon()
    target = _team(state, 3 - player).active_mon()
    move = MOVES[move_name]
    rng = _rng(state)

    if is_choice_item(actor.item) and pre_turn_choice_lock and move_name != pre_turn_choice_lock:
        log.add(f"{actor.species} is locked into {pre_turn_choice_lock}.")
        return

    choice_item_at_move_start = actor.item if is_choice_item(actor.item) else ""
    should_choice_lock_after_use = bool(choice_item_at_move_start and can_choice_lock)

    if not bypass_sleep and actor.status == "slp":
        can_act = resolve_sleep_attempt(actor, move_name, log, rng)
        if not can_act:
            return

    if actor.taunt_turns > 0 and move.category == "status" and move.effect not in {"sleep_talk"}:
        log.add(f"{actor.species} cannot use {move_name} after the Taunt.")
        return

    if target.protected and protect_blocks_move(move):
        log.add(f"{actor.species} used {move_name}, but {target.species} protected itself.")
        return

    if target.substitute_hp > 0 and substitute_blocks_move(move, actor):
        log.add(f"{actor.species} used {move_name}, but {target.species}'s substitute blocked it.")
        return

    if move.accuracy < 100 and rng.randint(1, 100) > move.accuracy:
        log.add(f"{actor.species} used {move_name} and missed.")
        return

    if try_ability_absorb(state, player, actor, target, move, move_name, log):
        apply_life_orb_recoil(actor, move, log)
        commit_choice_lock(actor, move_name, should_choice_lock_after_use)
        return

    if try_magic_bounce(state, player, actor, target, move, move_name, log, rng):
        commit_choice_lock(actor, move_name, should_choice_lock_after_use)
        return

    if move.effect == "sleep_talk":
        log.add(f"{actor.species} used {move_name}.")
        if actor.status != "slp":
            log.add("But it failed because the user is not asleep.")
            commit_choice_lock(actor, move_name, should_choice_lock_after_use)
            return
        callable_moves = [name for name in actor.moves if name != move_name]
        if not callable_moves:
            log.add("But there was no move to call.")
            commit_choice_lock(actor, move_name, should_choice_lock_after_use)
            return
        called_move = rng.choice(callable_moves)
        log.add(f"Sleep Talk called {called_move}.")
        commit_choice_lock(actor, move_name, should_choice_lock_after_use)
        use_move(
            state,
            player,
            called_move,
            log,
            target_hard_switched=target_hard_switched,
            pre_turn_choice_lock=None,
            bypass_sleep=True,
            can_choice_lock=False,
            target_already_moved=target_already_moved,
        )
        return

    log.add(f"{actor.species} used {move_name}.")

    if move.effect == "protect":
        if target_hard_switched:
            log.add(f"{actor.species}'s Protect failed.")
        else:
            actor.protected = True
            log.add(f"{actor.species} protected itself.")
            commit_choice_lock(actor, move_name, should_choice_lock_after_use)
        return

    if move.effect == "stealth_rock":
        _team(state, 3 - player).side.stealth_rock = True
        log.add("Pointed stones float around the opposing team.")
        commit_choice_lock(actor, move_name, should_choice_lock_after_use)
        return

    if move.effect == "spikes":
        side = _team(state, 3 - player).side
        side.spikes = min(3, side.spikes + 1)
        log.add(f"Spikes were scattered. Layers: {side.spikes}.")
        commit_choice_lock(actor, move_name, should_choice_lock_after_use)
        return

    if move.effect == "toxic_spikes":
        side = _team(state, 3 - player).side
        side.toxic_spikes = min(2, side.toxic_spikes + 1)
        log.add(f"Toxic Spikes were scattered. Layers: {side.toxic_spikes}.")
        commit_choice_lock(actor, move_name, should_choice_lock_after_use)
        return

    if move.effect == "defog":
        state.p1.side.stealth_rock = state.p2.side.stealth_rock = False
        state.p1.side.spikes = state.p2.side.spikes = 0
        state.p1.side.toxic_spikes = state.p2.side.toxic_spikes = 0
        log.add("Hazards were cleared from the field.")
        commit_choice_lock(actor, move_name, should_choice_lock_after_use)
        return

    if move.effect == "heal_bell":
        for mon in _team(state, player).mons:
            clear_status(mon)
        log.add(f"{actor.species}'s team was cured of status.")
        commit_choice_lock(actor, move_name, should_choice_lock_after_use)
        return

    if move.effect == "rest":
        actor.hp = actor.max_hp
        actor.status = "slp"
        actor.toxic_counter = 0
        actor.sleep_counter = 0
        actor.sleep_duration = 3
        log.add(f"{actor.species} slept and restored its HP.")
        if actor.item == "Lum Berry":
            clear_status(actor)
            actor.item_removed = True
            log.add(f"{actor.species}'s Lum Berry cured its sleep.")
        commit_choice_lock(actor, move_name, should_choice_lock_after_use)
        return

    if move.effect == "wish":
        heal(actor, actor.max_hp // 2, log)
        log.add("Wish is simplified as immediate healing in this engine.")
        return

    if move.effect == "pain_split":
        average = (actor.hp + target.hp) // 2
        actor.hp = max(1, min(actor.max_hp, average))
        target.hp = max(1, min(target.max_hp, average))
        log.add(f"Pain Split set both active Pokémon near {average} HP.")
        return

    if move.effect == "force_switch":
        bench = _team(state, 3 - player).first_healthy_bench()
        if bench is not None:
            do_switch(state, 3 - player, bench, log)
        else:
            log.add("But there was no Pokémon to force in.")
        return

    if move.effect == "counter":
        if actor.last_damage_category == "physical" and actor.last_damage_taken > 0 and actor.last_damage_source_player == 3 - player:
            apply_damage(target, min(target.hp, actor.last_damage_taken * 2), log, source=target.species)
            commit_choice_lock(actor, move_name, should_choice_lock_after_use)
        else:
            log.add("Counter failed.")
        return

    if move.effect == "leech_seed":
        if "Grass" in SPECIES[target.species].types:
            log.add(f"{target.species} is immune to Leech Seed.")
        elif target.leech_seeded_by is not None:
            log.add(f"{target.species} is already seeded.")
        else:
            target.leech_seeded_by = player
            log.add(f"{target.species} was seeded.")
            commit_choice_lock(actor, move_name, should_choice_lock_after_use)
        return

    if move.effect == "light_screen":
        turns = 8 if actor.item == "Light Clay" else 5
        _team(state, player).side.light_screen_turns = turns
        log.add(f"Light Screen protected Player {player}'s team.")
        commit_choice_lock(actor, move_name, should_choice_lock_after_use)
        return

    if move.effect == "reflect":
        turns = 8 if actor.item == "Light Clay" else 5
        _team(state, player).side.reflect_turns = turns
        log.add(f"Reflect protected Player {player}'s team.")
        commit_choice_lock(actor, move_name, should_choice_lock_after_use)
        return

    if move.effect == "safeguard":
        turns = 8 if actor.item == "Light Clay" else 5
        _team(state, player).side.safeguard_turns = turns
        log.add(f"Safeguard protected Player {player}'s team.")
        commit_choice_lock(actor, move_name, should_choice_lock_after_use)
        return

    if move.effect == "skill_swap":
        actor_ability = actor.ability
        target_ability = target.ability
        actor.ability = target_ability
        target.ability = actor_ability
        log.add(f"{actor.species} swapped abilities with {target.species}.")
        commit_choice_lock(actor, move_name, should_choice_lock_after_use)
        return

    if move.effect == "substitute":
        if actor.substitute_hp > 0:
            log.add(f"{actor.species} already has a substitute.")
            return
        cost = actor.max_hp // 4
        if actor.hp <= cost:
            log.add(f"{actor.species} does not have enough HP to make a substitute.")
            return
        actor.hp -= cost
        actor.substitute_hp = cost
        log.add(f"{actor.species} made a substitute.")
        commit_choice_lock(actor, move_name, should_choice_lock_after_use)
        return

    if move.effect == "taunt":
        if target.taunt_turns > 0:
            log.add(f"{target.species} is already taunted.")
            return
        target.taunt_turns = 3
        log.add(f"{target.species} fell for the taunt.")
        commit_choice_lock(actor, move_name, should_choice_lock_after_use)
        return

    if move.effect == "trick_room":
        if state.field.trick_room_turns > 0:
            state.field.trick_room_turns = 0
            log.add("The twisted dimensions returned to normal.")
        else:
            state.field.trick_room_turns = 5
            log.add("The dimensions were twisted.")
        commit_choice_lock(actor, move_name, should_choice_lock_after_use)
        return

    if move.effect == "unimplemented":
        log.add(f"{move_name}'s detailed effect is not implemented yet.")
        commit_choice_lock(actor, move_name, should_choice_lock_after_use)
        return

    if move.heal_fraction:
        heal(actor, int(actor.max_hp * move.heal_fraction), log)
        commit_choice_lock(actor, move_name, should_choice_lock_after_use)
        return

    if move.boost_self:
        apply_boosts(actor, move.boost_self, log)

    if move.effect == "trick":
        actor_item = actor.item
        target_item = target.item
        actor.item = target_item
        target.item = actor_item
        actor.choice_locked_move = None
        # Do not retroactively lock the target if it already moved this turn.
        # It will lock only when it next successfully uses a move while holding a Choice item.
        log.add(f"{actor.species} swapped items with {target.species}.")
        log.add(f"{actor.species} received {actor.item or 'nothing'}.")
        log.add(f"{target.species} received {target.item or 'nothing'}.")
        commit_choice_lock(actor, move_name, should_choice_lock_after_use)
        return

    if move.effect == "pivot" and move.category == "status":
        bench = _team(state, player).first_healthy_bench()
        if bench is not None:
            do_switch(state, player, bench, log)
        else:
            log.add("But there was no Pokémon to switch to.")
        commit_choice_lock(actor, move_name, should_choice_lock_after_use)
        return

    if move.category == "status":
        if move.ailment:
            try_apply_status(
                target,
                move.ailment,
                move.type,
                log,
                rng=rng,
                safeguarded=_team(state, 3 - player).side.safeguard_turns > 0,
            )
        commit_choice_lock(actor, move_name, should_choice_lock_after_use)
        return

    if move.effect == "endeavor":
        if actor.hp < target.hp:
            apply_damage(target, target.hp - actor.hp, log, source=target.species)
            apply_life_orb_recoil(actor, move, log)
            commit_choice_lock(actor, move_name, should_choice_lock_after_use)
        else:
            log.add("Endeavor failed.")
        return

    total_damage = 0
    last_eff = 1.0
    for _ in range(max(1, move.hits)):
        if target.fainted:
            break
        damage, eff = calculate_damage(
            state,
            actor,
            target,
            move_name,
            rng,
            target_already_moved=target_already_moved,
            log=log,
        )
        last_eff = eff
        if damage <= 0:
            continue
        total_damage += damage
        if target.substitute_hp > 0 and actor.ability != "Infiltrator":
            apply_substitute_damage(target, damage, log)
        else:
            apply_damage(target, damage, log, source=target.species, damage_category=move.category, source_player=player)

    if total_damage <= 0:
        log.add("It had no effect.")
        apply_life_orb_recoil(actor, move, log)
        commit_choice_lock(actor, move_name, should_choice_lock_after_use)
        return

    if move.hits > 1:
        log.add(f"Hit {move.hits} times.")

    if last_eff > 1:
        log.add("It's super effective.")
    elif 0 < last_eff < 1:
        log.add("It's not very effective.")

    if move.effect == "clear_boosts" and not target.fainted:
        target.boosts = {k: 0 for k in target.boosts}
        log.add(f"{target.species}'s stat changes were cleared.")

    if move.drain_fraction and not actor.fainted:
        heal(actor, int(total_damage * move.drain_fraction), log)

    if move.recoil_fraction and not actor.fainted:
        recoil = max(1, int(total_damage * move.recoil_fraction))
        apply_damage(actor, recoil, log, source=actor.species)
        log.add(f"{actor.species} was hurt by recoil.")

    if move.effect == "self_faint" and not actor.fainted:
        apply_damage(actor, actor.hp, log, source=actor.species)
        log.add(f"{actor.species} fainted from using {move_name}.")

    apply_life_orb_recoil(actor, move, log)

    if move.contact:
        if target.item == "Rocky Helmet" and not actor.fainted:
            apply_damage(actor, max(1, actor.max_hp // 6), log, source=actor.species)
            log.add(f"{actor.species} was hurt by Rocky Helmet.")
        if target.ability in {"Iron Barbs", "Rough Skin"} and not actor.fainted:
            apply_damage(actor, max(1, actor.max_hp // 8), log, source=actor.species)
            log.add(f"{actor.species} was hurt by {target.ability}.")
        if target.ability == "Flame Body" and actor.status is None and not actor.fainted and rng.random() < 0.30:
            try_apply_status(actor, "brn", "Fire", log, rng=rng)
        if target.ability == "Pickpocket" and not target.item and actor.item and not target.fainted:
            target.item = actor.item
            actor.item = ""
            log.add(f"{target.species} pickpocketed {actor.species}'s item.")

    if move.effect == "knock_off" and not target.fainted and target.item:
        log.add(f"{target.species} lost its {target.item}.")
        target.item_removed = True

    if move.effect == "rapid_spin":
        own_side = _team(state, player).side
        own_side.stealth_rock = False
        own_side.spikes = 0
        own_side.toxic_spikes = 0
        log.add(f"{actor.species} cleared hazards from its side.")

    if move.ailment and not target.fainted and target.substitute_hp <= 0:
        if rng.random() < secondary_chance(actor, move):
            try_apply_status(
                target,
                move.ailment,
                move.type,
                log,
                rng=rng,
                safeguarded=_team(state, 3 - player).side.safeguard_turns > 0,
            )

    if target.ability == "Cursed Body" and total_damage > 0 and not target.fainted and rng.random() < 0.30:
        actor.disabled_move = move_name
        actor.disabled_turns = 4
        log.add(f"{actor.species}'s {move_name} was disabled by Cursed Body.")

    if target.fainted and actor.ability == "Moxie" and not actor.fainted:
        apply_boosts(actor, {"atk": 1}, log)

    commit_choice_lock(actor, move_name, should_choice_lock_after_use)

    if move.effect == "pivot" and not actor.fainted:
        bench = _team(state, player).first_healthy_bench()
        if bench is not None:
            do_switch(state, player, bench, log)




def try_ability_absorb(
    state: BattleState,
    player: int,
    actor: PokemonState,
    target: PokemonState,
    move,
    move_name: str,
    log: TurnLog,
) -> bool:
    if move.category == "status" or attacker_ignores_defender_ability(actor):
        return False
    if target.ability == "Flash Fire" and move.type == "Fire":
        target.flash_fire_active = True
        log.add(f"{target.species}'s Flash Fire absorbed {move_name}.")
        return True
    if target.ability == "Storm Drain" and move.type == "Water":
        apply_boosts(target, {"spa": 1}, log)
        log.add(f"{target.species}'s Storm Drain absorbed {move_name}.")
        return True
    return False


def try_magic_bounce(
    state: BattleState,
    player: int,
    actor: PokemonState,
    target: PokemonState,
    move,
    move_name: str,
    log: TurnLog,
    rng: random.Random,
) -> bool:
    if target.ability != "Magic Bounce" or attacker_ignores_defender_ability(actor) or not is_reflectable_move(move):
        return False
    log.add(f"{target.species}'s Magic Bounce reflected {move_name}.")
    if move.ailment:
        try_apply_status(actor, move.ailment, move.type, log, rng=rng, safeguarded=_team(state, player).side.safeguard_turns > 0)
        return True
    if move.effect == "taunt":
        if actor.taunt_turns > 0:
            log.add(f"{actor.species} is already taunted.")
        else:
            actor.taunt_turns = 3
            log.add(f"{actor.species} fell for the taunt.")
        return True
    if move.effect == "leech_seed":
        if "Grass" in SPECIES[actor.species].types:
            log.add(f"{actor.species} is immune to Leech Seed.")
        else:
            actor.leech_seeded_by = 3 - player
            log.add(f"{actor.species} was seeded.")
        return True
    if move.effect == "stealth_rock":
        _team(state, player).side.stealth_rock = True
        log.add("Pointed stones were bounced back.")
        return True
    if move.effect == "spikes":
        side = _team(state, player).side
        side.spikes = min(3, side.spikes + 1)
        log.add("Spikes were bounced back.")
        return True
    if move.effect == "toxic_spikes":
        side = _team(state, player).side
        side.toxic_spikes = min(2, side.toxic_spikes + 1)
        log.add("Toxic Spikes were bounced back.")
        return True
    return False


def clear_status(mon: PokemonState) -> None:
    mon.status = None
    mon.toxic_counter = 0
    mon.sleep_counter = 0
    mon.sleep_duration = 0


def resolve_sleep_attempt(actor: PokemonState, move_name: str, log: TurnLog, rng: random.Random) -> bool:
    """Return True when a sleeping Pokémon may execute its selected move.

    Sleep advances only when the Pokémon attempts to act. Normal sleep receives
    a 1-3 attempt duration when the status is applied. Rest sets duration to 3.
    Sleep Talk is allowed to execute while the user remains asleep.
    """
    if actor.status != "slp":
        return True
    if actor.sleep_duration <= 0:
        actor.sleep_duration = rng.randint(1, 3)
    actor.sleep_counter += 1
    if actor.sleep_counter >= actor.sleep_duration:
        clear_status(actor)
        log.add(f"{actor.species} woke up.")
        return True
    if MOVES[move_name].effect == "sleep_talk":
        return True
    log.add(f"{actor.species} is fast asleep.")
    return False


def weight_power(weight_kg: float) -> int:
    if weight_kg < 10:
        return 20
    if weight_kg < 25:
        return 40
    if weight_kg < 50:
        return 60
    if weight_kg < 100:
        return 80
    if weight_kg < 200:
        return 100
    return 120


def heavy_slam_power(attacker_weight_kg: float, defender_weight_kg: float) -> int:
    if defender_weight_kg <= 0:
        return 40
    ratio = attacker_weight_kg / defender_weight_kg
    if ratio >= 5:
        return 120
    if ratio >= 4:
        return 100
    if ratio >= 3:
        return 80
    if ratio >= 2:
        return 60
    return 40


def gyro_ball_power(attacker: PokemonState, defender: PokemonState) -> int:
    return min(150, max(1, int(25 * effective_speed(defender) / max(1, effective_speed(attacker)))))


def variable_base_power(move, attacker: PokemonState, defender: PokemonState) -> int:
    if move.effect == "weight_power":
        return weight_power(SPECIES[defender.species].weight_kg)
    if move.effect == "heavy_slam":
        return heavy_slam_power(SPECIES[attacker.species].weight_kg, SPECIES[defender.species].weight_kg)
    if move.effect == "gyro_ball":
        return gyro_ball_power(attacker, defender)
    return move.power


def commit_choice_lock(actor: PokemonState, move_name: str, should_lock: bool) -> None:
    if should_lock and actor.choice_locked_move is None and is_choice_item(actor.item):
        actor.choice_locked_move = move_name


def secondary_chance(actor: PokemonState, move) -> float:
    if actor.ability == "Sheer Force" and has_sheer_force_bonus(move):
        return 0.0
    chance = move.ailment_chance
    if actor.ability == "Serene Grace":
        chance *= 2
    return min(1.0, chance)


def apply_life_orb_recoil(actor: PokemonState, move, log: TurnLog) -> None:
    """Apply Life Orb after a damaging move resolves.

    Misses, Protect blocks, and no-target failures do not call this helper.
    Immunity/no-effect outcomes do call it, because the move was still used
    into a valid target in this engine's current rules.
    """
    if move.category == "status":
        return
    if actor.item != "Life Orb" or actor.ability == "Magic Guard" or actor.fainted:
        return
    if actor.ability == "Sheer Force" and has_sheer_force_bonus(move):
        return
    recoil = max(1, actor.max_hp // 10)
    apply_damage(actor, recoil, log, source=actor.species)
    log.add(f"{actor.species} lost some HP from Life Orb.")



def calculate_damage(
    state: BattleState,
    attacker: PokemonState,
    defender: PokemonState,
    move_name: str,
    rng: random.Random,
    *,
    target_already_moved: bool = False,
    log: TurnLog | None = None,
) -> tuple[int, float]:
    move = MOVES[move_name]
    species_att = SPECIES[attacker.species]
    species_def = SPECIES[defender.species]
    debug_parts: list[str] = []

    defender_ability = effective_defender_ability(attacker, defender)
    eff = effectiveness(move.type, species_def.types, defender_ability)
    debug_parts.append(f"move={move_name}")
    debug_parts.append(f"type={move.type}")
    debug_parts.append(f"category={move.category}")
    debug_parts.append(f"attacker={attacker.species}")
    debug_parts.append(f"defender={defender.species}")
    debug_parts.append(f"attacker_ability={attacker.ability}")
    debug_parts.append(f"defender_ability={defender.ability}")
    debug_parts.append(f"effective_defender_ability={defender_ability or 'ignored'}")
    debug_parts.append(f"type_effectiveness={eff}")

    if move.effect == "fixed_level":
        damage = min(defender.hp, attacker.set.level) if eff > 0 else 0
        debug_parts.append(f"fixed_damage={damage}")
        if log:
            log.debug("damage_calc | " + " | ".join(debug_parts))
        return damage, eff

    if move.effect == "psywave":
        damage = min(defender.hp, max(1, int(attacker.set.level * rng.uniform(0.5, 1.5)))) if eff > 0 else 0
        debug_parts.append(f"psywave_damage={damage}")
        if log:
            log.debug("damage_calc | " + " | ".join(debug_parts))
        return damage, eff

    if move.power <= 0:
        debug_parts.append("non_damaging_or_zero_power=True")
        if log:
            log.debug("damage_calc | " + " | ".join(debug_parts))
        return 0, eff

    base_power = variable_base_power(move, attacker, defender)
    power = base_power
    power_mods: list[str] = []

    if move.effect == "facade" and attacker.status in {"brn", "psn", "tox", "par"}:
        power *= 2
        power_mods.append("facade_status=2.0")
    if move.effect == "stored_power":
        power = 20 + 20 * sum(max(0, stage) for stage in attacker.boosts.values())
        power_mods.append(f"stored_power={power}")
    if attacker.ability == "Technician" and power <= 60:
        power = int(power * 1.5)
        power_mods.append("Technician=1.5")
    if attacker.ability == "Iron Fist" and move_name in PUNCHING_MOVES:
        power = int(power * 1.2)
        power_mods.append("Iron Fist=1.2")
    if attacker.ability == "Sharpness" and move_name in SLICING_MOVES:
        power = int(power * 1.5)
        power_mods.append("Sharpness=1.5")
    if attacker.ability == "Sheer Force" and has_sheer_force_bonus(move):
        power = int(power * 1.3)
        power_mods.append("Sheer Force power=1.3")

    attack_stat = "atk" if move.category == "physical" else "spa"
    defense_stat = "def" if move.category == "physical" else "spd"
    if move.effect == "psyshock":
        defense_stat = "def"

    atk = modified_stat(defender, "atk") if move.effect == "foul_play" else modified_stat(attacker, attack_stat)
    defender_player = 1 if state.p1.active_mon() is defender else 2
    defense_before_multiscale = defender_stat(
        defender,
        defense_stat,
        state,
        defender_player,
        ignore_screens=attacker.ability == "Infiltrator",
    )
    defense = defense_before_multiscale

    if defender_ability == "Multiscale" and defender.hp == defender.max_hp:
        defense = int(defense * 2)
        power_mods.append("defender Multiscale defense=2.0")

    level = attacker.set.level
    base = (((((2 * level) // 5 + 2) * power * atk) // defense) // 50) + 2
    modifier = 1.0
    damage_mods: list[str] = []

    if state.field.weather == "rain":
        if move.type == "Water":
            modifier *= 1.5
            damage_mods.append("rain_water=1.5")
        if move.type == "Fire":
            modifier *= 0.5
            damage_mods.append("rain_fire=0.5")
    elif state.field.weather == "sun":
        if move.type == "Fire":
            modifier *= 1.5
            damage_mods.append("sun_fire=1.5")
        if move.type == "Water":
            modifier *= 0.5
            damage_mods.append("sun_water=0.5")

    if defender_ability == "Thick Fat" and move.type in {"Fire", "Ice"}:
        modifier *= 0.5
        damage_mods.append("Thick Fat=0.5")
    if attacker.ability == "Blaze" and move.type == "Fire" and attacker.hp <= attacker.max_hp // 3:
        modifier *= 1.5
        damage_mods.append("Blaze=1.5")
    if attacker.ability == "Flash Fire" and attacker.flash_fire_active and move.type == "Fire":
        modifier *= 1.5
        damage_mods.append("Flash Fire=1.5")
    if attacker.ability == "Reckless" and move.recoil_fraction:
        modifier *= 1.2
        damage_mods.append("Reckless=1.2")
    if attacker.ability == "Analytic" and target_already_moved:
        modifier *= 1.3
        damage_mods.append("Analytic=1.3")

    crit = rng.random() < 1 / 16
    if crit:
        modifier *= 1.5
        damage_mods.append("crit=1.5")

    random_roll = rng.randint(85, 100) / 100
    modifier *= random_roll
    damage_mods.append(f"random={random_roll:.2f}")

    if move.type in species_att.types:
        stab = 2.0 if attacker.ability == "Adaptability" else 1.5
        modifier *= stab
        damage_mods.append(f"STAB={stab}")

    modifier *= eff
    damage_mods.append(f"type={eff}")

    if attacker.item == "Life Orb":
        modifier *= 1.3
        damage_mods.append("Life Orb=1.3")
    if attacker.item == "Expert Belt" and eff > 1:
        modifier *= 1.2
        damage_mods.append("Expert Belt=1.2")

    raw_damage = int(base * modifier)
    damage = raw_damage
    if damage == 0 and eff > 0:
        damage = 1

    sash_or_sturdy = ""
    if defender.item == "Focus Sash" and defender.hp == defender.max_hp and damage >= defender.hp:
        damage = defender.hp - 1
        defender.item_removed = True
        sash_or_sturdy = "Focus Sash"
    elif defender_ability == "Sturdy" and defender.hp == defender.max_hp and damage >= defender.hp:
        damage = defender.hp - 1
        sash_or_sturdy = "Sturdy"

    debug_parts.extend([
        f"base_power={base_power}",
        f"final_power={power}",
        f"power_mods={power_mods or ['none']}",
        f"attack_stat={attack_stat}",
        f"attack_value={atk}",
        f"defense_stat={defense_stat}",
        f"defense_value_before_multiscale={defense_before_multiscale}",
        f"defense_value={defense}",
        f"base_damage={base}",
        f"damage_mods={damage_mods or ['none']}",
        f"combined_modifier={modifier:.4f}",
        f"raw_damage={raw_damage}",
        f"final_damage={max(0, damage)}",
        f"sash_or_sturdy={sash_or_sturdy or 'none'}",
    ])
    if log:
        log.debug("damage_calc | " + " | ".join(debug_parts))

    return max(0, damage), eff


def apply_substitute_damage(mon: PokemonState, amount: int, log: TurnLog) -> None:
    if mon.substitute_hp <= 0:
        return
    absorbed = min(mon.substitute_hp, max(0, amount))
    mon.substitute_hp -= absorbed
    log.add(f"{mon.species}'s substitute took {absorbed} damage.")
    if mon.substitute_hp <= 0:
        mon.substitute_hp = 0
        log.add(f"{mon.species}'s substitute broke.")


def apply_damage(
    mon: PokemonState,
    amount: int,
    log: TurnLog,
    source: str = "",
    damage_category: str | None = None,
    source_player: int | None = None,
) -> None:
    amount = max(0, amount)
    if mon.ability == "Magic Guard" and source == "residual":
        return
    mon.hp = max(0, mon.hp - amount)
    if damage_category:
        mon.last_damage_taken += amount
        mon.last_damage_category = damage_category
        mon.last_damage_source_player = source_player
    log.add(f"{mon.species} took {amount} damage ({mon.hp}/{mon.max_hp}).")
    if mon.hp <= 0:
        mon.fainted = True
        mon.hp = 0
        log.add(f"{mon.species} fainted.")


def heal(mon: PokemonState, amount: int, log: TurnLog) -> None:
    if mon.fainted:
        return
    old = mon.hp
    mon.hp = min(mon.max_hp, mon.hp + max(0, amount))
    healed = mon.hp - old
    if healed > 0:
        log.add(f"{mon.species} healed {healed} HP ({mon.hp}/{mon.max_hp}).")


def apply_boosts(mon: PokemonState, boosts: dict[str, int], log: TurnLog, *, source_opponent: bool = False) -> None:
    lowered_by_opponent = False
    for stat, original_delta in boosts.items():
        delta = -original_delta if mon.ability == "Contrary" else original_delta
        if source_opponent and delta < 0 and mon.ability == "Clear Body":
            log.add(f"{mon.species}'s Clear Body prevented the stat drop.")
            continue
        old = mon.boosts.get(stat, 0)
        mon.boosts[stat] = max(-6, min(6, old + delta))
        if source_opponent and delta < 0 and mon.boosts[stat] < old:
            lowered_by_opponent = True
        log.add(f"{mon.species}'s {stat} changed from {old} to {mon.boosts[stat]}.")
    if lowered_by_opponent and mon.ability == "Defiant":
        old = mon.boosts.get("atk", 0)
        mon.boosts["atk"] = max(-6, min(6, old + 2))
        log.add(f"{mon.species}'s Defiant raised its atk from {old} to {mon.boosts['atk']}.")


def try_apply_status(
    target: PokemonState,
    status: str,
    move_type: str,
    log: TurnLog,
    *,
    rng: random.Random | None = None,
    sleep_duration: int | None = None,
    safeguarded: bool = False,
) -> None:
    if target.status is not None or target.fainted:
        return
    if safeguarded:
        log.add(f"{target.species} was protected by Safeguard.")
        return
    target_types = SPECIES[target.species].types
    if status in {"psn", "tox"} and ("Poison" in target_types or "Steel" in target_types):
        log.add(f"{target.species} could not be poisoned.")
        return
    if status == "brn" and "Fire" in target_types:
        log.add(f"{target.species} could not be burned.")
        return
    if status == "par" and "Ground" in target_types and move_type == "Electric":
        log.add(f"{target.species} was immune to paralysis.")
        return
    if status == "slp" and "Grass" in target_types:
        log.add(f"{target.species} resisted the sleep effect.")
        return
    target.status = status
    target.toxic_counter = 1 if status == "tox" else 0
    target.sleep_counter = 0
    if status == "slp":
        target.sleep_duration = sleep_duration if sleep_duration is not None else (rng.randint(1, 3) if rng else 1)
    else:
        target.sleep_duration = 0
    log.add(f"{target.species} is now {status}.")
    if target.item == "Lum Berry":
        clear_status(target)
        target.item_removed = True
        log.add(f"{target.species}'s Lum Berry cured its status.")


def end_of_turn(state: BattleState, log: TurnLog) -> None:
    for player in [1, 2]:
        mon = _team(state, player).active_mon()
        if mon.fainted:
            continue

        if mon.status == "brn":
            apply_damage(mon, max(1, mon.max_hp // 8), log, source="residual")
            log.add(f"{mon.species} was hurt by its burn.")
        elif mon.status == "psn":
            apply_damage(mon, max(1, mon.max_hp // 8), log, source="residual")
            log.add(f"{mon.species} was hurt by poison.")
        elif mon.status == "tox":
            dmg = max(1, mon.max_hp * max(1, mon.toxic_counter) // 16)
            apply_damage(mon, dmg, log, source="residual")
            log.add(f"{mon.species} was hurt by toxic poison.")
            mon.toxic_counter += 1

        if mon.fainted:
            continue

        if mon.leech_seeded_by is not None:
            seed_damage = max(1, mon.max_hp // 8)
            apply_damage(mon, seed_damage, log, source="residual")
            log.add(f"{mon.species}'s health was sapped by Leech Seed.")
            if not mon.fainted:
                seeder_team = _team(state, mon.leech_seeded_by)
                healer = seeder_team.active_mon()
                if not healer.fainted:
                    heal(healer, seed_damage, log)

        if mon.fainted:
            continue

        if mon.item == "Leftovers":
            heal(mon, max(1, mon.max_hp // 16), log)
        elif mon.item == "Black Sludge":
            if "Poison" in SPECIES[mon.species].types:
                heal(mon, max(1, mon.max_hp // 16), log)
            else:
                apply_damage(mon, max(1, mon.max_hp // 8), log, source="residual")
        elif mon.item == "Sitrus Berry" and mon.hp <= mon.max_hp // 2:
            heal(mon, mon.max_hp // 4, log)
            mon.item_removed = True

        if mon.ability == "Poison Heal" and mon.status in {"psn", "tox"} and not mon.fainted:
            heal(mon, max(1, mon.max_hp // 8), log)

    for player in (1, 2):
        team = _team(state, player)
        for attr, label in (
            ("reflect_turns", "Reflect"),
            ("light_screen_turns", "Light Screen"),
            ("safeguard_turns", "Safeguard"),
        ):
            turns = getattr(team.side, attr)
            if turns > 0:
                setattr(team.side, attr, turns - 1)
                if turns - 1 == 0:
                    log.add(f"Player {player}'s {label} wore off.")

        active = team.active_mon()
        if active.taunt_turns > 0:
            active.taunt_turns -= 1
            if active.taunt_turns == 0:
                log.add(f"{active.species}'s taunt wore off.")
        if active.disabled_turns > 0:
            active.disabled_turns -= 1
            if active.disabled_turns == 0:
                active.disabled_move = None
                log.add(f"{active.species}'s disable wore off.")

    if state.field.trick_room_turns > 0:
        state.field.trick_room_turns -= 1
        if state.field.trick_room_turns == 0:
            log.add("The twisted dimensions returned to normal.")

    if state.field.weather_turns > 0:
        state.field.weather_turns -= 1
        if state.field.weather_turns == 0:
            log.add(f"The {state.field.weather} weather ended.")
            state.field.weather = None


def do_switch(state: BattleState, player: int, new_index: int, log: TurnLog) -> None:
    team = _team(state, player)
    if new_index == team.active:
        return
    if new_index < 0 or new_index >= len(team.mons):
        log.add(f"Invalid switch index {new_index}.")
        return
    outgoing = team.active_mon()
    incoming = team.mons[new_index]
    if incoming.fainted or incoming.hp <= 0:
        log.add(f"Cannot switch to fainted {incoming.species}.")
        return

    if outgoing.status == "slp":
        outgoing.sleep_counter = 0
    if outgoing.ability == "Natural Cure":
        clear_status(outgoing)
    if outgoing.ability == "Regenerator" and not outgoing.fainted:
        heal(outgoing, outgoing.max_hp // 3, log)
    outgoing.boosts = {k: 0 for k in outgoing.boosts}
    outgoing.choice_locked_move = None
    outgoing.substitute_hp = 0
    outgoing.taunt_turns = 0
    outgoing.leech_seeded_by = None
    outgoing.active_ability = outgoing.set.ability
    outgoing.last_damage_taken = 0
    outgoing.last_damage_category = None
    outgoing.last_damage_source_player = None
    outgoing.flash_fire_active = False
    outgoing.disabled_move = None
    outgoing.disabled_turns = 0

    team.active = new_index
    log.add(f"Player {player} switched to {incoming.species}.")
    apply_on_switch_in(state, player, log)


def apply_on_switch_in(state: BattleState, player: int, log: TurnLog) -> None:
    team = _team(state, player)
    mon = team.active_mon()
    if mon.fainted:
        return

    opponent = _team(state, 3 - player).active_mon()
    if mon.ability == "Trace" and not opponent.fainted and opponent.ability != "Trace":
        mon.ability = opponent.ability
        log.add(f"{mon.species} traced {opponent.ability}.")

    if mon.ability == "Sand Stream":
        state.field.weather = "sand"
        state.field.weather_turns = 0
        log.add("A sandstorm kicked up.")
    elif mon.ability == "Drizzle":
        state.field.weather = "rain"
        state.field.weather_turns = 0
        log.add("Rain began to fall.")
    elif mon.ability == "Drought":
        state.field.weather = "sun"
        state.field.weather_turns = 0
        log.add("The sunlight turned harsh.")

    if mon.ability == "Intimidate" and not opponent.fainted:
        if opponent.ability == "Inner Focus":
            log.add(f"{opponent.species}'s Inner Focus blocked Intimidate.")
        else:
            apply_boosts(opponent, {"atk": -1}, log, source_opponent=True)

    if mon.ability != "Magic Guard":
        if team.side.stealth_rock:
            rock_eff = effectiveness("Rock", SPECIES[mon.species].types, mon.ability)
            dmg = int(mon.max_hp * rock_eff / 8)
            if dmg > 0:
                apply_damage(mon, max(1, dmg), log, source="residual")
                log.add(f"{mon.species} was hurt by Stealth Rock.")

        grounded = "Flying" not in SPECIES[mon.species].types and mon.ability != "Levitate"
        if team.side.spikes and grounded:
            frac = {1: 8, 2: 6, 3: 4}[team.side.spikes]
            apply_damage(mon, max(1, mon.max_hp // frac), log, source="residual")
            log.add(f"{mon.species} was hurt by Spikes.")

        if team.side.toxic_spikes and grounded and mon.status is None:
            if "Poison" in SPECIES[mon.species].types:
                team.side.toxic_spikes = 0
                log.add(f"{mon.species} absorbed the Toxic Spikes.")
            elif "Steel" not in SPECIES[mon.species].types:
                try_apply_status(
                    mon,
                    "tox" if team.side.toxic_spikes >= 2 else "psn",
                    "Poison",
                    log,
                    safeguarded=team.side.safeguard_turns > 0,
                )


def check_winner(state: BattleState, log: TurnLog) -> None:
    p1_alive = state.p1.alive_count()
    p2_alive = state.p2.alive_count()
    if p1_alive == 0 and p2_alive == 0:
        state.winner = 0
        log.add("Battle ended in a draw.")
    elif p1_alive == 0:
        state.winner = 2
        log.add("Player 2 wins.")
    elif p2_alive == 0:
        state.winner = 1
        log.add("Player 1 wins.")


def evaluate_material(state: BattleState, player: int) -> float:
    # Simple rollout heuristic in [-1, 1]. Positive favors player.
    own = _team(state, player)
    opp = _team(state, 3 - player)

    def team_score(team: TeamState) -> float:
        score = 0.0
        for mon in team.mons:
            if mon.fainted:
                continue
            score += 1.0 + mon.hp / mon.max_hp
        return score

    a = team_score(own)
    b = team_score(opp)
    if a + b == 0:
        return 0.0
    return (a - b) / (a + b)
