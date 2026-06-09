from battle_engine import Action, legal_actions, make_battle, step
from battle_engine.sample_sets import TYRANITAR_CB, DRAGONITE_DD, FERROTHORN_UTIL, STARMIE_OFF, ROTOM_W_DEF, SCIZOR_CB

def test_damage_and_choice_lock():
    state = make_battle([TYRANITAR_CB], [DRAGONITE_DD], seed=1)
    state, log = step(state, Action("move", 1), Action("move", 0))
    assert state.p2.active_mon().hp < state.p2.active_mon().max_hp
    legal = legal_actions(state, 1)
    move_actions = [a for a in legal if a.kind == "move"]
    assert len(move_actions) == 1
    assert TYRANITAR_CB.moves[move_actions[0].index] == "Stone Edge"

def test_stealth_rock_on_switch():
    state = make_battle([FERROTHORN_UTIL, ROTOM_W_DEF], [DRAGONITE_DD, SCIZOR_CB], seed=2)
    state, log = step(state, Action("move", 1), Action("switch", 1))
    assert state.p2.side.stealth_rock is True
    hp_before = state.p2.mons[0].hp
    state, log = step(state, Action("move", 2), Action("switch", 0))
    assert state.p2.mons[0].hp < hp_before

def test_rapid_spin_clears_hazards():
    state = make_battle([FERROTHORN_UTIL], [STARMIE_OFF], seed=3)
    state, log = step(state, Action("move", 0), Action("move", 2))  # Spikes / Thunderbolt
    assert state.p2.side.spikes == 1
    state, log = step(state, Action("move", 2), Action("move", 3))  # Giga Drain / Rapid Spin
    assert state.p2.side.spikes == 0


def test_parse_variant_options():
    from battle_engine.import_sets import parse_showdown_set_options, parse_showdown_set_variants

    text = """
    Gyarados @ Leftovers / Lum Berry
    Ability: Moxie / Intimidate
    Level: 50
    EVs: 6 HP / 252 Atk / 252 Spe
    Jolly / Adamant Nature
    - Waterfall
    - Power Whip
    - Ice Fang / Bounce
    - Dragon Dance
    """

    options = parse_showdown_set_options(text)
    assert options.item_options == ["Leftovers", "Lum Berry"]
    assert options.ability_options == ["Moxie", "Intimidate"]
    assert options.nature_options == ["Jolly", "Adamant"]
    assert options.move_slot_options[2] == ["Ice Fang", "Bounce"]
    assert options.variant_count() == 16

    variants = parse_showdown_set_variants(text)
    assert len(variants) == 16
    assert variants[0].item == "Leftovers"
    assert variants[0].ability == "Moxie"
    assert variants[0].nature == "Jolly"
    assert variants[0].moves[2] == "Ice Fang"


def test_parse_ev_spread_and_hidden_power_variants():
    from battle_engine.import_sets import parse_ev_options, split_move_options

    ev_options = parse_ev_options("EVs: 252 HP / 156 Def / 100 Spe or 252 HP / 156 SpDef / 100 Spe")
    assert len(ev_options) == 2
    assert ev_options[0]["def"] == 156
    assert ev_options[0]["spd"] == 0
    assert ev_options[1]["def"] == 0
    assert ev_options[1]["spd"] == 156

    assert split_move_options("Hidden Power Ice / Fight") == [
        "Hidden Power Ice",
        "Hidden Power Fighting",
    ]
    assert split_move_options("Hidden Power Fire / Rock") == [
        "Hidden Power Fire",
        "Hidden Power Rock",
    ]



def test_compendium_coverage_has_no_missing_engine_data():
    from battle_engine.data import MOVES, SPECIES
    from battle_engine.import_sets import parse_showdown_sets_file
    from battle_engine.team_builder import default_compendium_path

    sets = parse_showdown_sets_file(default_compendium_path(), expand_variants=True)
    missing_species = sorted({s.species for s in sets if s.species not in SPECIES})
    missing_moves = sorted({m for s in sets for m in s.moves if m not in MOVES})
    assert missing_species == []
    assert missing_moves == []


def test_random_team_builder_and_smoke_battle():
    import random
    from battle_engine import legal_actions, make_battle, step
    from battle_engine.team_builder import default_compendium_path, load_set_pool, random_team

    rng = random.Random(123)
    pool = load_set_pool(default_compendium_path(), expand_variants=True)
    team1 = random_team(pool, rng=rng)
    team2 = random_team(pool, rng=rng)
    assert len(team1) == 6
    assert len(team2) == 6
    assert len({s.species for s in team1}) == 6

    state = make_battle(team1, team2, seed=123)
    for _ in range(3):
        if state.winner is not None:
            break
        p1_action = legal_actions(state, 1)[0]
        p2_action = legal_actions(state, 2)[0]
        state, _ = step(state, p1_action, p2_action)


def test_life_orb_recoil_on_type_immunity():
    from battle_engine.model import PokemonSet
    from battle_engine.sample_sets import IV31, evs

    gengar = PokemonSet(
        species="Gengar",
        item="Life Orb",
        ability="Cursed Body",
        nature="Timid",
        evs=evs(spa=252, spe=252, hp=4),
        ivs=IV31,
        moves=["Shadow Ball"],
    )
    chansey = PokemonSet(
        species="Chansey",
        item="Eviolite",
        ability="Natural Cure",
        nature="Bold",
        evs=evs(hp=252, **{"def": 252}),
        ivs=IV31,
        moves=["Soft-Boiled"],
    )

    state = make_battle([gengar], [chansey], seed=10)
    hp_before = state.p1.active_mon().hp
    state, log = step(state, Action("move", 0), Action("move", 0))

    assert "It had no effect." in str(log)
    assert state.p1.active_mon().hp == hp_before - state.p1.active_mon().max_hp // 10


def test_life_orb_does_not_recoil_when_target_fainted_before_move():
    from battle_engine.model import PokemonSet
    from battle_engine.sample_sets import IV31, evs

    fast_self_faint = PokemonSet(
        species="Gengar",
        item="Focus Sash",
        ability="Cursed Body",
        nature="Timid",
        evs=evs(atk=252, spe=252, hp=4),
        ivs=IV31,
        moves=["Explosion"],
    )
    slow_life_orb = PokemonSet(
        species="Chansey",
        item="Life Orb",
        ability="Natural Cure",
        nature="Bold",
        evs=evs(hp=252, **{"def": 252}),
        ivs=IV31,
        moves=["Seismic Toss"],
    )

    state = make_battle([fast_self_faint], [slow_life_orb], seed=11)
    state, log = step(state, Action("move", 0), Action("move", 0))

    assert "no target" in str(log)
    assert "lost some HP from Life Orb" not in str(log)


def test_protect_fails_into_hard_switch():
    from battle_engine.model import PokemonSet
    from battle_engine.sample_sets import IV31, evs

    protector = PokemonSet(
        species="Chansey",
        item="Eviolite",
        ability="Natural Cure",
        nature="Bold",
        evs=evs(hp=252, **{"def": 252}),
        ivs=IV31,
        moves=["Protect"],
    )
    lead = PokemonSet(
        species="Tyranitar",
        item="Leftovers",
        ability="Sand Stream",
        nature="Adamant",
        evs=evs(hp=252),
        ivs=IV31,
        moves=["Crunch"],
    )
    bench = PokemonSet(
        species="Scizor",
        item="Leftovers",
        ability="Technician",
        nature="Adamant",
        evs=evs(hp=252),
        ivs=IV31,
        moves=["Bullet Punch"],
    )

    state = make_battle([protector], [lead, bench], seed=12)
    state, log = step(state, Action("move", 0), Action("switch", 1))

    assert "Protect failed" in str(log)
    assert state.p1.active_mon().protected is False


def test_end_of_turn_faint_requires_free_replacement():
    from battle_engine import needs_replacement, replace_fainted
    from battle_engine.model import PokemonSet
    from battle_engine.sample_sets import IV31, evs

    active = PokemonSet(
        species="Chansey",
        item="",
        ability="Natural Cure",
        nature="Bold",
        evs=evs(hp=252, **{"def": 252}),
        ivs=IV31,
        moves=["Protect"],
    )
    bench = PokemonSet(
        species="Scizor",
        item="Leftovers",
        ability="Technician",
        nature="Adamant",
        evs=evs(hp=252),
        ivs=IV31,
        moves=["Bullet Punch"],
    )
    opponent = PokemonSet(
        species="Blissey",
        item="",
        ability="Natural Cure",
        nature="Bold",
        evs=evs(hp=252, **{"def": 252}),
        ivs=IV31,
        moves=["Protect"],
    )

    state = make_battle([active, bench], [opponent], seed=13)
    state.p1.active_mon().hp = 1
    state.p1.active_mon().status = "brn"

    state, log = step(state, Action("move", 0), Action("move", 0))

    assert needs_replacement(state, 1)
    assert "must choose a replacement" in str(log)

    state, replacement_log = replace_fainted(state, 1, 1)
    assert not needs_replacement(state, 1)
    assert state.p1.active_mon().species == "Scizor"


def test_choice_item_locks_after_successful_move_and_resets_on_switch():
    from battle_engine.model import PokemonSet
    from battle_engine.sample_sets import IV31, evs

    scizor = PokemonSet(
        species="Scizor",
        item="Choice Band",
        ability="Technician",
        nature="Adamant",
        evs=evs(hp=248, atk=252, spd=8),
        ivs=IV31,
        moves=["Bullet Punch", "U-turn", "Superpower", "Bug Bite"],
    )
    bench = PokemonSet(
        species="Rotom-Wash",
        item="Leftovers",
        ability="Levitate",
        nature="Bold",
        evs=evs(hp=252, **{"def": 252}),
        ivs=IV31,
        moves=["Hydro Pump", "Volt Switch", "Will-O-Wisp", "Thunderbolt"],
    )
    target = PokemonSet(
        species="Chansey",
        item="Eviolite",
        ability="Natural Cure",
        nature="Bold",
        evs=evs(hp=252, **{"def": 252}),
        ivs=IV31,
        moves=["Soft-Boiled"],
    )

    state = make_battle([scizor, bench], [target], seed=21)
    state, log = step(state, Action("move", 0), Action("move", 0))

    assert state.p1.active_mon().choice_locked_move == "Bullet Punch"
    legal = legal_actions(state, 1)
    assert [a for a in legal if a.kind == "move"] == [Action("move", 0)]

    state, log = step(state, Action("switch", 1), Action("move", 0))
    state, log = step(state, Action("switch", 0), Action("move", 0))

    assert state.p1.active_mon().species == "Scizor"
    assert state.p1.active_mon().choice_locked_move is None
    move_actions = [a for a in legal_actions(state, 1) if a.kind == "move"]
    assert len(move_actions) == 4


def test_choice_item_locks_status_move_too():
    from battle_engine.model import PokemonSet
    from battle_engine.sample_sets import IV31, evs

    rotom = PokemonSet(
        species="Rotom-Wash",
        item="Choice Scarf",
        ability="Levitate",
        nature="Timid",
        evs=evs(hp=252, spe=252),
        ivs=IV31,
        moves=["Will-O-Wisp", "Hydro Pump", "Volt Switch", "Thunderbolt"],
    )
    target = PokemonSet(
        species="Chansey",
        item="Eviolite",
        ability="Natural Cure",
        nature="Bold",
        evs=evs(hp=252, **{"def": 252}),
        ivs=IV31,
        moves=["Soft-Boiled"],
    )

    state = make_battle([rotom], [target], seed=22)
    state, log = step(state, Action("move", 0), Action("move", 0))

    assert state.p1.active_mon().choice_locked_move == "Will-O-Wisp"
    assert [a for a in legal_actions(state, 1) if a.kind == "move"] == [Action("move", 0)]


def test_choice_item_tricked_after_target_moved_does_not_retroactively_lock_target():
    from battle_engine.model import PokemonSet
    from battle_engine.sample_sets import IV31, evs

    slow_tricker = PokemonSet(
        species="Chansey",
        item="Choice Scarf",
        ability="Natural Cure",
        nature="Bold",
        evs=evs(hp=252, **{"def": 252}),
        ivs=IV31,
        moves=["Trick", "Soft-Boiled"],
    )
    fast_target = PokemonSet(
        species="Starmie",
        item="Leftovers",
        ability="Natural Cure",
        nature="Timid",
        evs=evs(spa=252, spe=252),
        ivs=IV31,
        moves=["Ice Beam", "Thunderbolt", "Recover", "Rapid Spin"],
    )

    state = make_battle([slow_tricker], [fast_target], seed=23)
    state, log = step(state, Action("move", 0), Action("move", 0))

    assert state.p2.active_mon().item == "Choice Scarf"
    assert state.p2.active_mon().choice_locked_move is None
    assert state.p1.active_mon().item == "Leftovers"


def test_choice_item_tricked_before_target_moves_locks_target_when_it_uses_move():
    from battle_engine.model import PokemonSet
    from battle_engine.sample_sets import IV31, evs

    fast_tricker = PokemonSet(
        species="Starmie",
        item="Choice Scarf",
        ability="Natural Cure",
        nature="Timid",
        evs=evs(spa=252, spe=252),
        ivs=IV31,
        moves=["Trick", "Ice Beam"],
    )
    slow_target = PokemonSet(
        species="Chansey",
        item="Leftovers",
        ability="Natural Cure",
        nature="Bold",
        evs=evs(hp=252, **{"def": 252}),
        ivs=IV31,
        moves=["Soft-Boiled", "Toxic"],
    )

    state = make_battle([fast_tricker], [slow_target], seed=24)
    state, log = step(state, Action("move", 0), Action("move", 0))

    assert state.p2.active_mon().item == "Choice Scarf"
    assert state.p2.active_mon().choice_locked_move == "Soft-Boiled"


def test_stat_boosts_change_offensive_damage_values():
    from battle_engine.model import PokemonSet
    from battle_engine.sample_sets import IV31, evs

    attacker = PokemonSet(
        species="Garchomp",
        item="",
        ability="Rough Skin",
        nature="Jolly",
        evs=evs(atk=252, spe=252),
        ivs=IV31,
        moves=["Earthquake"],
    )
    boosted_attacker = PokemonSet(
        species="Garchomp",
        item="",
        ability="Rough Skin",
        nature="Jolly",
        evs=evs(atk=252, spe=252),
        ivs=IV31,
        moves=["Earthquake"],
    )
    defender = PokemonSet(
        species="Chansey",
        item="Eviolite",
        ability="Natural Cure",
        nature="Bold",
        evs=evs(hp=252, **{"def": 252}),
        ivs=IV31,
        moves=["Soft-Boiled"],
    )

    unboosted = make_battle([attacker], [defender], seed=30)
    boosted = make_battle([boosted_attacker], [defender], seed=30)
    boosted.p1.active_mon().boosts["atk"] = 2

    unboosted, _ = step(unboosted, Action("move", 0), Action("move", 0))
    boosted, _ = step(boosted, Action("move", 0), Action("move", 0))

    unboosted_damage = unboosted.p2.active_mon().max_hp - unboosted.p2.active_mon().hp
    boosted_damage = boosted.p2.active_mon().max_hp - boosted.p2.active_mon().hp

    assert boosted_damage > unboosted_damage * 1.7


def test_stat_boosts_change_defensive_damage_values():
    from battle_engine.model import PokemonSet
    from battle_engine.sample_sets import IV31, evs

    attacker = PokemonSet(
        species="Garchomp",
        item="",
        ability="Rough Skin",
        nature="Jolly",
        evs=evs(atk=252, spe=252),
        ivs=IV31,
        moves=["Earthquake"],
    )
    defender = PokemonSet(
        species="Chansey",
        item="Eviolite",
        ability="Natural Cure",
        nature="Bold",
        evs=evs(hp=252, **{"def": 252}),
        ivs=IV31,
        moves=["Soft-Boiled"],
    )

    normal = make_battle([attacker], [defender], seed=31)
    boosted_defense = make_battle([attacker], [defender], seed=31)
    boosted_defense.p2.active_mon().boosts["def"] = 2

    normal, _ = step(normal, Action("move", 0), Action("move", 0))
    boosted_defense, _ = step(boosted_defense, Action("move", 0), Action("move", 0))

    normal_damage = normal.p2.active_mon().max_hp - normal.p2.active_mon().hp
    boosted_defense_damage = boosted_defense.p2.active_mon().max_hp - boosted_defense.p2.active_mon().hp

    assert boosted_defense_damage < normal_damage * 0.7



def test_spore_sets_sleep_duration_and_sleep_does_not_tick_at_end_of_turn():
    from battle_engine.model import PokemonSet
    from battle_engine.sample_sets import IV31, evs

    breloom = PokemonSet(
        species="Breloom",
        item="",
        ability="Technician",
        nature="Jolly",
        evs=evs(atk=252, spe=252),
        ivs=IV31,
        moves=["Spore"],
    )
    starmie = PokemonSet(
        species="Starmie",
        item="",
        ability="Natural Cure",
        nature="Timid",
        evs=evs(spa=252, spe=252),
        ivs=IV31,
        moves=["Rapid Spin"],
    )

    state = make_battle([breloom], [starmie], seed=40)
    state, log = step(state, Action("move", 0), Action("move", 0))

    sleeping = state.p2.active_mon()
    assert sleeping.status == "slp"
    assert 1 <= sleeping.sleep_duration <= 3
    assert sleeping.sleep_counter == 0


def test_sleep_counter_increments_only_when_attempting_to_move_and_can_wake_same_turn():
    from battle_engine.model import PokemonSet
    from battle_engine.sample_sets import IV31, evs

    sleeper = PokemonSet(
        species="Chansey",
        item="",
        ability="Natural Cure",
        nature="Bold",
        evs=evs(hp=252, **{"def": 252}),
        ivs=IV31,
        moves=["Seismic Toss"],
    )
    target = PokemonSet(
        species="Blissey",
        item="",
        ability="Natural Cure",
        nature="Bold",
        evs=evs(hp=252, **{"def": 252}),
        ivs=IV31,
        moves=["Soft-Boiled"],
    )

    state = make_battle([sleeper], [target], seed=41)
    state.p1.active_mon().status = "slp"
    state.p1.active_mon().sleep_duration = 2
    state.p1.active_mon().sleep_counter = 0

    state, log = step(state, Action("move", 0), Action("move", 0))
    assert state.p1.active_mon().status == "slp"
    assert state.p1.active_mon().sleep_counter == 1
    assert "fast asleep" in str(log)

    state, log = step(state, Action("move", 0), Action("move", 0))
    assert state.p1.active_mon().status is None
    assert "woke up" in str(log)
    assert state.p2.active_mon().hp < state.p2.active_mon().max_hp


def test_sleep_counter_resets_on_switch_out():
    from battle_engine.model import PokemonSet
    from battle_engine.sample_sets import IV31, evs

    sleeper = PokemonSet(
        species="Gengar",
        item="",
        ability="Cursed Body",
        nature="Timid",
        evs=evs(spa=252, spe=252),
        ivs=IV31,
        moves=["Shadow Ball"],
    )
    bench = PokemonSet(
        species="Scizor",
        item="",
        ability="Technician",
        nature="Adamant",
        evs=evs(atk=252),
        ivs=IV31,
        moves=["Bullet Punch"],
    )
    target = PokemonSet(
        species="Chansey",
        item="",
        ability="Natural Cure",
        nature="Bold",
        evs=evs(hp=252, **{"def": 252}),
        ivs=IV31,
        moves=["Soft-Boiled"],
    )

    state = make_battle([sleeper, bench], [target], seed=42)
    state.p1.active_mon().status = "slp"
    state.p1.active_mon().sleep_duration = 3
    state.p1.active_mon().sleep_counter = 2

    state, log = step(state, Action("switch", 1), Action("move", 0))
    assert state.p1.mons[0].status == "slp"
    assert state.p1.mons[0].sleep_counter == 0
    assert state.p1.mons[0].sleep_duration == 3


def test_rest_sets_three_attempt_sleep_counter():
    from battle_engine.model import PokemonSet
    from battle_engine.sample_sets import IV31, evs

    suicune = PokemonSet(
        species="Suicune",
        item="",
        ability="Pressure",
        nature="Bold",
        evs=evs(hp=252, **{"def": 252}),
        ivs=IV31,
        moves=["Rest"],
    )
    target = PokemonSet(
        species="Blissey",
        item="",
        ability="Natural Cure",
        nature="Bold",
        evs=evs(hp=252, **{"def": 252}),
        ivs=IV31,
        moves=["Protect"],
    )

    state = make_battle([suicune], [target], seed=43)
    state.p1.active_mon().hp = state.p1.active_mon().max_hp // 2
    state, log = step(state, Action("move", 0), Action("move", 0))

    assert state.p1.active_mon().hp == state.p1.active_mon().max_hp
    assert state.p1.active_mon().status == "slp"
    assert state.p1.active_mon().sleep_duration == 3
    assert state.p1.active_mon().sleep_counter == 0


def test_sleep_talk_can_call_a_move_while_asleep():
    from battle_engine.model import PokemonSet
    from battle_engine.sample_sets import IV31, evs

    sleeper = PokemonSet(
        species="Chansey",
        item="",
        ability="Natural Cure",
        nature="Bold",
        evs=evs(hp=252, **{"def": 252}),
        ivs=IV31,
        moves=["Sleep Talk", "Seismic Toss"],
    )
    target = PokemonSet(
        species="Blissey",
        item="",
        ability="Natural Cure",
        nature="Bold",
        evs=evs(hp=252, **{"def": 252}),
        ivs=IV31,
        moves=["Soft-Boiled"],
    )

    state = make_battle([sleeper], [target], seed=44)
    state.p1.active_mon().status = "slp"
    state.p1.active_mon().sleep_duration = 3
    state.p1.active_mon().sleep_counter = 0

    state, log = step(state, Action("move", 0), Action("move", 0))
    assert state.p1.active_mon().sleep_counter == 1
    assert "Sleep Talk called Seismic Toss" in str(log)
    assert state.p2.active_mon().hp < state.p2.active_mon().max_hp


def test_toxic_damage_increases_each_turn():
    from battle_engine.model import PokemonSet
    from battle_engine.sample_sets import IV31, evs

    toxic_mon = PokemonSet(
        species="Chansey",
        item="",
        ability="Natural Cure",
        nature="Bold",
        evs=evs(hp=252, **{"def": 252}),
        ivs=IV31,
        moves=["Protect"],
    )
    opponent = PokemonSet(
        species="Blissey",
        item="",
        ability="Natural Cure",
        nature="Bold",
        evs=evs(hp=252, **{"def": 252}),
        ivs=IV31,
        moves=["Protect"],
    )

    state = make_battle([toxic_mon], [opponent], seed=45)
    mon = state.p1.active_mon()
    mon.status = "tox"
    mon.toxic_counter = 1
    max_hp = mon.max_hp

    state, _ = step(state, Action("move", 0), Action("move", 0))
    after_first = state.p1.active_mon().hp
    state, _ = step(state, Action("move", 0), Action("move", 0))
    after_second = state.p1.active_mon().hp

    first_damage = max_hp - after_first
    second_damage = after_first - after_second
    assert first_damage == max(1, max_hp // 16)
    assert second_damage == max(1, max_hp * 2 // 16)


def test_weight_based_base_power_tables():
    from battle_engine.engine import weight_power, heavy_slam_power

    assert weight_power(9.9) == 20
    assert weight_power(10.0) == 40
    assert weight_power(24.9) == 40
    assert weight_power(25.0) == 60
    assert weight_power(49.9) == 60
    assert weight_power(50.0) == 80
    assert weight_power(99.9) == 80
    assert weight_power(100.0) == 100
    assert weight_power(199.9) == 100
    assert weight_power(200.0) == 120

    assert heavy_slam_power(500, 100) == 120
    assert heavy_slam_power(400, 100) == 100
    assert heavy_slam_power(300, 100) == 80
    assert heavy_slam_power(200, 100) == 60
    assert heavy_slam_power(199, 100) == 40


def test_variable_weight_moves_change_damage_by_target_weight():
    from battle_engine.model import PokemonSet
    from battle_engine.sample_sets import IV31, evs

    attacker = PokemonSet(
        species="Mienshao",
        item="",
        ability="Regenerator",
        nature="Jolly",
        evs=evs(atk=252, spe=252),
        ivs=IV31,
        moves=["Low Kick"],
    )
    light_target = PokemonSet(
        species="Weezing",
        item="",
        ability="Neutralizing Gas",
        nature="Bold",
        evs=evs(hp=252, **{"def": 252}),
        ivs=IV31,
        moves=["Sludge Bomb"],
    )
    heavy_target = PokemonSet(
        species="Tyranitar",
        item="",
        ability="Sand Stream",
        nature="Adamant",
        evs=evs(hp=252),
        ivs=IV31,
        moves=["Crunch"],
    )

    light = make_battle([attacker], [light_target], seed=46)
    heavy = make_battle([attacker], [heavy_target], seed=46)
    light, _ = step(light, Action("move", 0), Action("move", 0))
    heavy, _ = step(heavy, Action("move", 0), Action("move", 0))

    light_damage = light.p2.active_mon().max_hp - light.p2.active_mon().hp
    heavy_damage = heavy.p2.active_mon().max_hp - heavy.p2.active_mon().hp
    assert heavy_damage > light_damage


def test_gyro_ball_uses_speed_ratio_for_base_power():
    from battle_engine.engine import gyro_ball_power
    from battle_engine.model import PokemonSet
    from battle_engine.sample_sets import IV31, evs

    ferro = PokemonSet(
        species="Ferrothorn",
        item="",
        ability="Iron Barbs",
        nature="Relaxed",
        evs=evs(hp=252),
        ivs=IV31,
        moves=["Gyro Ball"],
    )
    weavile = PokemonSet(
        species="Weavile",
        item="",
        ability="Pressure",
        nature="Jolly",
        evs=evs(spe=252),
        ivs=IV31,
        moves=["Night Slash"],
    )
    state = make_battle([ferro], [weavile], seed=47)
    assert gyro_ball_power(state.p1.active_mon(), state.p2.active_mon()) > 100


def test_teleport_switches_user_to_bench():
    from battle_engine.model import PokemonSet
    from battle_engine.sample_sets import IV31, evs

    user = PokemonSet("Chansey", "Eviolite", "Natural Cure", "Bold", evs(hp=252, **{"def": 252}), IV31, ["Teleport"])
    bench = PokemonSet("Scizor", "Leftovers", "Technician", "Adamant", evs(hp=252, atk=252), IV31, ["Bullet Punch"])
    target = PokemonSet("Blissey", "", "Natural Cure", "Bold", evs(hp=252, **{"def": 252}), IV31, ["Protect"])

    state = make_battle([user, bench], [target], seed=40)
    state, log = step(state, Action("move", 0), Action("move", 0))

    assert state.p1.active_mon().species == "Scizor"


def test_counter_returns_double_physical_damage():
    from battle_engine.model import PokemonSet
    from battle_engine.sample_sets import IV31, evs

    attacker = PokemonSet("Scizor", "", "Technician", "Adamant", evs(atk=252), IV31, ["Bullet Punch"])
    counter_user = PokemonSet("Chansey", "", "Natural Cure", "Bold", evs(hp=252, **{"def": 252}), IV31, ["Counter"])

    state = make_battle([attacker], [counter_user], seed=41)
    target_hp = state.p1.active_mon().hp
    state, log = step(state, Action("move", 0), Action("move", 0))

    bullet_damage = state.p2.active_mon().last_damage_taken
    counter_damage = target_hp - state.p1.active_mon().hp
    assert counter_damage == min(target_hp, bullet_damage * 2)


def test_leech_seed_persists_when_seeder_switches_and_clears_when_seeded_switches():
    from battle_engine.model import PokemonSet
    from battle_engine.sample_sets import IV31, evs

    seeder = PokemonSet("Chansey", "", "Natural Cure", "Bold", evs(hp=252, **{"def": 252}), IV31, ["Leech Seed", "Teleport"])
    seeder_bench = PokemonSet("Scizor", "", "Technician", "Adamant", evs(hp=252), IV31, ["Bullet Punch"])
    seeded = PokemonSet("Blissey", "", "Natural Cure", "Bold", evs(hp=252, **{"def": 252}), IV31, ["Soft-Boiled"])
    seeded_bench = PokemonSet("Tyranitar", "", "Sand Stream", "Adamant", evs(hp=252), IV31, ["Crunch"])

    state = make_battle([seeder, seeder_bench], [seeded, seeded_bench], seed=42)
    state, log = step(state, Action("move", 0), Action("move", 0))
    assert state.p2.active_mon().leech_seeded_by == 1

    state, log = step(state, Action("switch", 1), Action("move", 0))
    assert state.p2.active_mon().leech_seeded_by == 1

    state, log = step(state, Action("move", 0), Action("switch", 1))
    assert state.p2.mons[0].leech_seeded_by is None


def test_reflect_and_light_screen_reduce_damage():
    from battle_engine.model import PokemonSet
    from battle_engine.sample_sets import IV31, evs

    physical = PokemonSet("Scizor", "", "Technician", "Adamant", evs(atk=252), IV31, ["Bullet Punch"])
    special = PokemonSet("Starmie", "", "Natural Cure", "Timid", evs(spa=252, spe=252), IV31, ["Thunderbolt"])
    defender = PokemonSet("Chansey", "", "Natural Cure", "Bold", evs(hp=252, **{"def": 252}), IV31, ["Reflect", "Light Screen"])

    normal_phys = make_battle([physical], [defender], seed=43)
    screened_phys = make_battle([physical], [defender], seed=43)
    screened_phys.p2.side.reflect_turns = 5
    normal_phys, _ = step(normal_phys, Action("move", 0), Action("move", 0))
    screened_phys, _ = step(screened_phys, Action("move", 0), Action("move", 0))
    normal_damage = normal_phys.p2.active_mon().max_hp - normal_phys.p2.active_mon().hp
    screened_damage = screened_phys.p2.active_mon().max_hp - screened_phys.p2.active_mon().hp
    assert screened_damage < normal_damage

    normal_spec = make_battle([special], [defender], seed=44)
    screened_spec = make_battle([special], [defender], seed=44)
    screened_spec.p2.side.light_screen_turns = 5
    normal_spec, _ = step(normal_spec, Action("move", 0), Action("move", 0))
    screened_spec, _ = step(screened_spec, Action("move", 0), Action("move", 0))
    normal_damage = normal_spec.p2.active_mon().max_hp - normal_spec.p2.active_mon().hp
    screened_damage = screened_spec.p2.active_mon().max_hp - screened_spec.p2.active_mon().hp
    assert screened_damage < normal_damage


def test_safeguard_blocks_new_status():
    from battle_engine.model import PokemonSet
    from battle_engine.sample_sets import IV31, evs

    status_user = PokemonSet("Rotom-Wash", "", "Levitate", "Bold", evs(hp=252), IV31, ["Will-O-Wisp"])
    target = PokemonSet("Chansey", "", "Natural Cure", "Bold", evs(hp=252, **{"def": 252}), IV31, ["Soft-Boiled"])

    state = make_battle([status_user], [target], seed=45)
    state.p2.side.safeguard_turns = 5
    state, log = step(state, Action("move", 0), Action("move", 0))

    assert state.p2.active_mon().status is None
    assert "Safeguard" in str(log)


def test_skill_swap_changes_abilities_and_resets_on_switch():
    from battle_engine.model import PokemonSet
    from battle_engine.sample_sets import IV31, evs

    user = PokemonSet("Espeon", "", "Magic Bounce", "Timid", evs(hp=252, spe=252), IV31, ["Skill Swap"])
    bench = PokemonSet("Scizor", "", "Technician", "Adamant", evs(hp=252), IV31, ["Bullet Punch"])
    target = PokemonSet("Rotom-Wash", "", "Levitate", "Bold", evs(hp=252), IV31, ["Thunderbolt"])

    state = make_battle([user, bench], [target], seed=46)
    state, log = step(state, Action("move", 0), Action("move", 0))
    assert state.p1.active_mon().ability == "Levitate"
    assert state.p2.active_mon().ability == "Magic Bounce"

    state, log = step(state, Action("switch", 1), Action("move", 0))
    state, log = step(state, Action("switch", 0), Action("move", 0))
    assert state.p1.active_mon().ability == "Magic Bounce"


def test_substitute_absorbs_damage_and_disappears_on_switch():
    from battle_engine.model import PokemonSet
    from battle_engine.sample_sets import IV31, evs

    user = PokemonSet("Chansey", "", "Natural Cure", "Bold", evs(hp=252, **{"def": 252}), IV31, ["Substitute"])
    bench = PokemonSet("Scizor", "", "Technician", "Adamant", evs(hp=252), IV31, ["Bullet Punch"])
    attacker = PokemonSet("Blissey", "", "Natural Cure", "Bold", evs(hp=252, **{"def": 252}), IV31, ["Seismic Toss"])

    state = make_battle([user, bench], [attacker], seed=47)
    state, log = step(state, Action("move", 0), Action("move", 0))
    assert state.p1.active_mon().substitute_hp > 0

    hp_after_sub = state.p1.active_mon().hp
    state, log = step(state, Action("move", 0), Action("move", 0))
    assert state.p1.active_mon().hp == hp_after_sub

    state, log = step(state, Action("switch", 1), Action("move", 0))
    assert state.p1.mons[0].substitute_hp == 0


def test_switcheroo_swaps_items():
    from battle_engine.model import PokemonSet
    from battle_engine.sample_sets import IV31, evs

    user = PokemonSet("Weavile", "Choice Band", "Pressure", "Jolly", evs(atk=252, spe=252), IV31, ["Switcheroo"])
    target = PokemonSet("Chansey", "Eviolite", "Natural Cure", "Bold", evs(hp=252, **{"def": 252}), IV31, ["Soft-Boiled"])

    state = make_battle([user], [target], seed=48)
    state, log = step(state, Action("move", 0), Action("move", 0))

    assert state.p1.active_mon().item == "Eviolite"
    assert state.p2.active_mon().item == "Choice Band"


def test_taunt_blocks_status_cannot_retaunt_and_clears_on_switch():
    from battle_engine.model import PokemonSet
    from battle_engine.sample_sets import IV31, evs

    taunter = PokemonSet("Gengar", "", "Cursed Body", "Timid", evs(spa=252, spe=252), IV31, ["Taunt"])
    target = PokemonSet("Chansey", "", "Natural Cure", "Bold", evs(hp=252, **{"def": 252}), IV31, ["Soft-Boiled"])
    bench = PokemonSet("Blissey", "", "Natural Cure", "Bold", evs(hp=252, **{"def": 252}), IV31, ["Protect"])

    state = make_battle([taunter], [target, bench], seed=49)
    state, log = step(state, Action("move", 0), Action("move", 0))
    assert state.p2.active_mon().taunt_turns > 0
    assert "cannot use Soft-Boiled" in str(log)

    state, log = step(state, Action("move", 0), Action("move", 0))
    assert "already taunted" in str(log)

    state, log = step(state, Action("move", 0), Action("switch", 1))
    assert state.p2.mons[0].taunt_turns == 0


def test_trick_room_reverses_speed_order():
    from battle_engine.model import PokemonSet
    from battle_engine.sample_sets import IV31, evs

    fast = PokemonSet("Starmie", "", "Natural Cure", "Timid", evs(spa=252, spe=252), IV31, ["Thunderbolt"])
    slow = PokemonSet("Reuniclus", "", "Magic Guard", "Quiet", evs(hp=252, spa=252), IV31, ["Shadow Ball"])

    normal = make_battle([fast], [slow], seed=50)
    normal, log = step(normal, Action("move", 0), Action("move", 0))
    assert str(log).splitlines()[0].startswith("Starmie used")

    reversed_state = make_battle([fast], [slow], seed=50)
    reversed_state.field.trick_room_turns = 4
    reversed_state, log = step(reversed_state, Action("move", 0), Action("move", 0))
    assert str(log).splitlines()[0].startswith("Reuniclus used")


def test_adaptability_boosts_stab_damage():
    from battle_engine.model import PokemonSet
    from battle_engine.sample_sets import IV31, evs

    adapted = PokemonSet("Crawdaunt", "", "Adaptability", "Adamant", evs(atk=252), IV31, ["Crunch"])
    normal = PokemonSet("Crawdaunt", "", "Shell Armor", "Adamant", evs(atk=252), IV31, ["Crunch"])
    target = PokemonSet("Chansey", "", "Natural Cure", "Bold", evs(hp=252, **{"def": 252}), IV31, ["Soft-Boiled"])

    s1 = make_battle([normal], [target], seed=60)
    s2 = make_battle([adapted], [target], seed=60)
    s1, _ = step(s1, Action("move", 0), Action("move", 0))
    s2, _ = step(s2, Action("move", 0), Action("move", 0))

    d1 = s1.p2.active_mon().max_hp - s1.p2.active_mon().hp
    d2 = s2.p2.active_mon().max_hp - s2.p2.active_mon().hp
    assert d2 > d1


def test_weather_speed_abilities_change_order():
    from battle_engine.model import PokemonSet
    from battle_engine.sample_sets import IV31, evs

    kabutops = PokemonSet("Kabutops", "", "Swift Swim", "Adamant", evs(atk=252), IV31, ["Waterfall"])
    starmie = PokemonSet("Starmie", "", "Natural Cure", "Timid", evs(spa=252, spe=252), IV31, ["Thunderbolt"])

    dry = make_battle([kabutops], [starmie], seed=61)
    dry, log = step(dry, Action("move", 0), Action("move", 0))
    assert str(log).splitlines()[0].startswith("Starmie used")

    rain = make_battle([kabutops], [starmie], seed=61)
    rain.field.weather = "rain"
    rain, log = step(rain, Action("move", 0), Action("move", 0))
    assert str(log).splitlines()[0].startswith("Kabutops used")


def test_sturdy_survives_full_hp_ko():
    from battle_engine.model import PokemonSet
    from battle_engine.sample_sets import IV31, evs

    attacker = PokemonSet("Darmanitan", "Choice Band", "Sheer Force", "Adamant", evs(atk=252), IV31, ["Flare Blitz"])
    sturdy = PokemonSet("Gengar", "", "Sturdy", "Timid", evs(hp=0), IV31, ["Nasty Plot"])

    state = make_battle([attacker], [sturdy], seed=62)
    state, log = step(state, Action("move", 0), Action("move", 0))
    assert state.p2.active_mon().hp == 1
    assert not state.p2.active_mon().fainted


def test_mold_breaker_ignores_levitate():
    from battle_engine.model import PokemonSet
    from battle_engine.sample_sets import IV31, evs

    mold = PokemonSet("Excadrill", "", "Mold Breaker", "Adamant", evs(atk=252), IV31, ["Earthquake"])
    normal = PokemonSet("Excadrill", "", "Sand Rush", "Adamant", evs(atk=252), IV31, ["Earthquake"])
    rotom = PokemonSet("Rotom-Wash", "", "Levitate", "Bold", evs(hp=252, **{"def": 252}), IV31, ["Hydro Pump"])

    s1 = make_battle([normal], [rotom], seed=63)
    s2 = make_battle([mold], [rotom], seed=63)
    s1, log1 = step(s1, Action("move", 0), Action("move", 0))
    s2, log2 = step(s2, Action("move", 0), Action("move", 0))
    assert "It had no effect" in str(log1)
    assert s2.p2.active_mon().hp < s2.p2.active_mon().max_hp


def test_storm_drain_absorbs_water_and_boosts_spa():
    from battle_engine.model import PokemonSet
    from battle_engine.sample_sets import IV31, evs

    attacker = PokemonSet("Starmie", "", "Natural Cure", "Timid", evs(spa=252), IV31, ["Surf"])
    target = PokemonSet("Gastrodon", "", "Storm Drain", "Calm", evs(hp=252), IV31, ["Recover"])

    state = make_battle([attacker], [target], seed=64)
    hp_before = state.p2.active_mon().hp
    state, log = step(state, Action("move", 0), Action("move", 0))
    assert state.p2.active_mon().hp == hp_before
    assert state.p2.active_mon().boosts["spa"] == 1


def test_flash_fire_absorbs_and_boosts_fire_moves():
    from battle_engine.model import PokemonSet
    from battle_engine.sample_sets import IV31, evs

    fire_user = PokemonSet("Chandelure", "", "Flash Fire", "Timid", evs(spa=252), IV31, ["Flamethrower"])
    attacker = PokemonSet("Infernape", "", "Blaze", "Naive", evs(spa=252), IV31, ["Flamethrower"])

    state = make_battle([attacker], [fire_user], seed=65)
    state, log = step(state, Action("move", 0), Action("move", 0))
    assert state.p2.active_mon().flash_fire_active is True

    target = PokemonSet("Chansey", "", "Natural Cure", "Calm", evs(hp=252, spd=252), IV31, ["Toxic"])
    boosted = make_battle([fire_user], [target], seed=66)
    unboosted = make_battle([fire_user], [target], seed=66)
    boosted.p1.active_mon().flash_fire_active = True
    boosted, _ = step(boosted, Action("move", 0), Action("move", 0))
    unboosted, _ = step(unboosted, Action("move", 0), Action("move", 0))
    assert boosted.p2.active_mon().hp < unboosted.p2.active_mon().hp


def test_clear_body_and_defiant_react_to_intimidate():
    from battle_engine.model import PokemonSet
    from battle_engine.sample_sets import IV31, evs

    intimidator = PokemonSet("Gyarados", "", "Intimidate", "Adamant", evs(atk=252), IV31, ["Waterfall"])
    clear_body = PokemonSet("Metagross", "", "Clear Body", "Adamant", evs(atk=252), IV31, ["Meteor Mash"])
    defiant = PokemonSet("Empoleon", "", "Defiant", "Adamant", evs(atk=252), IV31, ["Waterfall"])

    s1 = make_battle([intimidator], [clear_body], seed=67)
    assert s1.p2.active_mon().boosts["atk"] == 0

    s2 = make_battle([intimidator], [defiant], seed=68)
    assert s2.p2.active_mon().boosts["atk"] == 1


def test_magic_bounce_reflects_status():
    from battle_engine.model import PokemonSet
    from battle_engine.sample_sets import IV31, evs

    burner = PokemonSet("Rotom-Wash", "", "Levitate", "Bold", evs(hp=252), IV31, ["Will-O-Wisp"])
    bounce = PokemonSet("Espeon", "", "Magic Bounce", "Timid", evs(hp=252, spe=252), IV31, ["Psychic"])

    state = make_battle([burner], [bounce], seed=69)
    state, log = step(state, Action("move", 0), Action("move", 0))
    assert state.p1.active_mon().status == "brn"
    assert state.p2.active_mon().status is None


def test_moxie_boosts_after_ko():
    from battle_engine.model import PokemonSet
    from battle_engine.sample_sets import IV31, evs

    moxie = PokemonSet("Gyarados", "", "Moxie", "Adamant", evs(atk=252), IV31, ["Waterfall"])
    victim = PokemonSet("Gengar", "", "Cursed Body", "Timid", evs(hp=0), IV31, ["Nasty Plot"])

    state = make_battle([moxie], [victim], seed=70)
    state.p2.active_mon().hp = 1
    state, log = step(state, Action("move", 0), Action("move", 0))
    assert state.p1.active_mon().boosts["atk"] == 1


def test_magnet_pull_removes_switch_actions_for_steel():
    from battle_engine.model import PokemonSet
    from battle_engine.sample_sets import IV31, evs

    steel = PokemonSet("Scizor", "", "Technician", "Adamant", evs(atk=252), IV31, ["Bullet Punch"])
    bench = PokemonSet("Rotom-Wash", "", "Levitate", "Bold", evs(hp=252), IV31, ["Hydro Pump"])
    zone = PokemonSet("Magnezone", "", "Magnet Pull", "Modest", evs(spa=252), IV31, ["Thunderbolt"])

    state = make_battle([steel, bench], [zone], seed=71)
    actions = legal_actions(state, 1)
    assert not any(a.kind == "switch" for a in actions)


def test_damage_debug_log_contains_stats_and_modifiers():
    state = make_battle([TYRANITAR_CB], [DRAGONITE_DD], seed=80)
    state, log = step(state, Action("move", 0), Action("move", 0), debug_damage=True)

    debug = "\n".join(log.debug_lines)
    assert "damage_calc" in debug
    assert "attack_value=" in debug
    assert "defense_value=" in debug
    assert "base_power=" in debug
    assert "damage_mods=" in debug
    assert "final_damage=" in debug


def test_mcts_returns_legal_action():
    from battle_engine.mcts import MCTSAgent, MCTSConfig

    state = make_battle([TYRANITAR_CB, SCIZOR_CB], [DRAGONITE_DD, STARMIE_OFF], seed=81)
    agent = MCTSAgent(MCTSConfig(simulations=4, max_depth=3), rng=__import__("random").Random(1))
    result = agent.search(state, 1)

    assert result.action in legal_actions(state, 1)
    assert result.stats
    assert sum(s.visits for s in result.stats) == 4


def test_mcts_search_backend_with_python_backend():
    from battle_engine.backends import PythonBattleBackend
    from battle_engine.mcts import MCTSAgent, MCTSConfig

    backend = PythonBattleBackend([TYRANITAR_CB, SCIZOR_CB], [DRAGONITE_DD, STARMIE_OFF], seed=83)
    root_summary = backend.state_summary()
    agent = MCTSAgent(MCTSConfig(simulations=4, max_depth=2), rng=__import__("random").Random(2))

    result = agent.search_backend(backend, 1)

    assert result.action in backend.legal_actions(1)
    assert result.stats
    assert sum(s.visits for s in result.stats) == 4
    assert backend.state_summary() == root_summary


def test_linear_agent_updates_weights():
    from battle_engine.ml_agent import LinearPolicyValueAgent

    state = make_battle([TYRANITAR_CB, SCIZOR_CB], [DRAGONITE_DD, STARMIE_OFF], seed=82)
    legal = legal_actions(state, 1)
    agent = LinearPolicyValueAgent(learning_rate=0.1)
    before = dict(agent.policy_weights)

    agent.update_policy_toward(state, 1, legal[0], legal)
    agent.update_value(state, 1, 0.5)

    assert agent.policy_weights != before
    assert agent.value_weights


def test_training_log_formatter_outputs_battle_log_style_text():
    from battle_engine.log_formatter import format_training_event

    event = {
        "type": "turn",
        "game_id": "g0-0",
        "turn_index": 0,
        "state": {
            "turn": 1,
            "weather": None,
            "trick_room_turns": 0,
            "p1": {
                "active": "Metagross",
                "hp": 187,
                "max_hp": 187,
                "status": None,
                "alive": 6,
                "hazards": {"sr": False, "spikes": 0, "toxic_spikes": 0},
            },
            "p2": {
                "active": "Skarmory",
                "hp": 172,
                "max_hp": 172,
                "status": None,
                "alive": 6,
                "hazards": {"sr": False, "spikes": 0, "toxic_spikes": 0},
            },
        },
        "p1_action": "move:Earthquake",
        "p2_action": "move:Stealth Rock",
        "p1_mcts": {
            "stats": [
                {"label": "move:Earthquake", "visits": 8, "mean_value": 0.25, "prior": 0.1},
            ]
        },
        "p2_mcts": {
            "stats": [
                {"label": "move:Stealth Rock", "visits": 9, "mean_value": 0.1, "prior": 0.2},
            ]
        },
        "turn_log": [
            "Metagross used Earthquake.",
            "It had no effect.",
            "Skarmory used Stealth Rock.",
        ],
    }

    text = format_training_event(event)
    assert "=== g0-0 | Turn 1 ===" in text
    assert "P1: Metagross 187/187" in text
    assert "P1 chose: move:Earthquake" in text
    assert "P1 MCTS top" in text
    assert "Battle log:" in text
    assert "Metagross used Earthquake." in text


def test_team_role_features_detect_basic_roles():
    from battle_engine.sample_sets import FERROTHORN_UTIL, STARMIE_OFF, SCIZOR_CB, GARCHOMP_SD, ROTOM_W_DEF, DRAGONITE_DD
    from battle_engine.team_roles import infer_set_tags, team_features, team_summary

    assert "hazard_setter" in infer_set_tags(FERROTHORN_UTIL)
    assert "hazard_removal" in infer_set_tags(STARMIE_OFF)
    assert "pivot" in infer_set_tags(SCIZOR_CB)

    team = [FERROTHORN_UTIL, STARMIE_OFF, SCIZOR_CB, GARCHOMP_SD, ROTOM_W_DEF, DRAGONITE_DD]
    features = team_features(team)
    summary = team_summary(team)

    assert features["team_has_hazard_setter"] == 1.0
    assert features["team_has_hazard_removal"] == 1.0
    assert features["team_has_physical_attacker"] == 1.0
    assert summary["role_counts"]["hazard_setter"] >= 1


def test_agent_scores_and_updates_team_weights():
    from battle_engine.ml_agent import LinearPolicyValueAgent
    from battle_engine.sample_sets import FERROTHORN_UTIL, STARMIE_OFF, SCIZOR_CB, GARCHOMP_SD, ROTOM_W_DEF, DRAGONITE_DD

    agent = LinearPolicyValueAgent(learning_rate=0.1)
    team = [FERROTHORN_UTIL, STARMIE_OFF, SCIZOR_CB, GARCHOMP_SD, ROTOM_W_DEF, DRAGONITE_DD]
    before = dict(agent.team_weights)
    score = agent.score_team(team)
    agent.update_team_value(team, 1.0)

    assert isinstance(score, float)
    assert agent.team_weights != before
    assert "team_bias" in agent.team_weights


def test_agent_choose_team_uses_team_weights():
    from battle_engine.ml_agent import LinearPolicyValueAgent
    from battle_engine.sample_sets import FERROTHORN_UTIL, STARMIE_OFF, SCIZOR_CB, GARCHOMP_SD, ROTOM_W_DEF, DRAGONITE_DD, TYRANITAR_CB, CONKELDURR_GUTS

    balanced = [FERROTHORN_UTIL, STARMIE_OFF, SCIZOR_CB, GARCHOMP_SD, ROTOM_W_DEF, DRAGONITE_DD]
    no_removal = [FERROTHORN_UTIL, SCIZOR_CB, GARCHOMP_SD, ROTOM_W_DEF, DRAGONITE_DD, TYRANITAR_CB]
    agent = LinearPolicyValueAgent(team_weights={"team_has_hazard_removal": 5.0})

    chosen = agent.choose_team([no_removal, balanced])
    assert chosen == balanced


def test_generate_team_candidates_returns_unique_species_teams():
    from battle_engine.sample_sets import TEAM_BALANCE_A, TEAM_BALANCE_B
    from battle_engine.team_builder import generate_team_candidates
    import random

    pool = TEAM_BALANCE_A + TEAM_BALANCE_B
    candidates = generate_team_candidates(pool, rng=random.Random(1), candidate_count=2)

    assert candidates
    for team in candidates:
        assert len({p.species for p in team}) == len(team)


def test_team_preview_formatter_includes_roles():
    from battle_engine.log_formatter import format_training_event
    from battle_engine.sample_sets import FERROTHORN_UTIL, STARMIE_OFF, SCIZOR_CB, GARCHOMP_SD, ROTOM_W_DEF, DRAGONITE_DD
    from battle_engine.team_roles import team_summary, short_team_label

    team = [FERROTHORN_UTIL, STARMIE_OFF, SCIZOR_CB, GARCHOMP_SD, ROTOM_W_DEF, DRAGONITE_DD]
    event = {
        "type": "team_preview",
        "game_id": "g0-r0-p0-0",
        "p1_agent_id": 0,
        "p2_agent_id": 1,
        "p1_agent_name": "a0",
        "p2_agent_name": "a1",
        "p1_team": team_summary(team),
        "p2_team": team_summary(team),
        "p1_team_label": short_team_label(team),
        "p2_team_label": short_team_label(team),
        "p1_team_score": 1.25,
        "p2_team_score": -0.5,
        "candidate_count": 8,
    }

    text = format_training_event(event)
    assert "Team Preview" in text
    assert "hazard_setter" in text
    assert "Ferrothorn" in text


def test_elo_update_moves_ratings_after_win():
    from battle_engine.training import _apply_elo_update

    p1_new, p2_new, event = _apply_elo_update(1000.0, 1000.0, 1, k_factor=32.0)

    assert round(p1_new, 2) == 1016.0
    assert round(p2_new, 2) == 984.0
    assert event["p1_expected"] == 0.5
    assert event["p1_elo_delta"] == 16.0
    assert event["p2_elo_delta"] == -16.0


def test_agent_serializes_elo():
    from battle_engine.ml_agent import LinearPolicyValueAgent

    agent = LinearPolicyValueAgent(name="elo-test", elo=1234.5)
    restored = LinearPolicyValueAgent.from_dict(agent.to_dict())

    assert restored.elo == 1234.5


def test_elo_training_smoke_saves_elos(tmp_path):
    from battle_engine.training import TrainingConfig, run_generational_training
    import json

    config = TrainingConfig(
        generations=1,
        agent_count=2,
        swiss_rounds=1,
        games_per_pairing=1,
        mcts_simulations=1,
        mcts_depth=1,
        max_turns=1,
        seed=456,
        elo_initial=1200,
        elo_k_factor=16,
        team_candidate_count=2,
        log_path=str(tmp_path / "train.jsonl"),
        human_log_path=str(tmp_path / "train.log"),
        model_path=str(tmp_path / "best.json"),
        population_path=str(tmp_path / "population.json"),
    )

    run_generational_training(config)

    jsonl = (tmp_path / "train.jsonl").read_text(encoding="utf-8")
    log_text = (tmp_path / "train.log").read_text(encoding="utf-8")
    population = json.loads((tmp_path / "population.json").read_text(encoding="utf-8"))

    assert '"type": "elo_update"' in jsonl
    assert "Elo Update" in log_text
    assert all("elo" in agent for agent in population)


def test_log_formatter_outputs_elo_update():
    from battle_engine.log_formatter import format_training_event

    text = format_training_event({
        "type": "elo_update",
        "game_id": "g0-r0-p0-0",
        "winner": 1,
        "p1_agent_id": 0,
        "p2_agent_id": 1,
        "p1_old_elo": 1000,
        "p2_old_elo": 1000,
        "p1_new_elo": 1016,
        "p2_new_elo": 984,
        "p1_elo_delta": 16,
        "p2_elo_delta": -16,
        "p1_expected": 0.5,
        "p2_expected": 0.5,
        "k_factor": 32,
    })

    assert "Elo Update" in text
    assert "1000 -> 1016" in text
    assert "Agent 1" in text


def test_progress_training_outputs_runtime_messages(tmp_path, capsys):
    from battle_engine.training import TrainingConfig, run_generational_training

    config = TrainingConfig(
        generations=1,
        agent_count=2,
        swiss_rounds=1,
        games_per_pairing=1,
        mcts_simulations=1,
        mcts_depth=1,
        max_turns=1,
        seed=789,
        team_candidate_count=2,
        progress=True,
        progress_turns=True,
        progress_every=1,
        log_path=str(tmp_path / "train.jsonl"),
        human_log_path=str(tmp_path / "train.log"),
        model_path=str(tmp_path / "best.json"),
        population_path=str(tmp_path / "population.json"),
    )

    run_generational_training(config)
    output = capsys.readouterr().out

    assert "[training]" in output
    assert "[generation 0]" in output
    assert "pairings:" in output
    assert "[team" in output
    assert "[turn" in output
    assert "[elo" in output
    assert "standings:" in output


def test_progress_every_suppresses_non_interval_turns(tmp_path, capsys):
    from battle_engine.training import TrainingConfig, run_generational_training

    config = TrainingConfig(
        generations=1,
        agent_count=2,
        swiss_rounds=1,
        games_per_pairing=1,
        mcts_simulations=1,
        mcts_depth=1,
        max_turns=3,
        seed=790,
        team_candidate_count=2,
        progress=True,
        progress_turns=True,
        progress_every=99,
        log_path=str(tmp_path / "train.jsonl"),
        human_log_path=str(tmp_path / "train.log"),
        model_path=str(tmp_path / "best.json"),
        population_path=str(tmp_path / "population.json"),
    )

    run_generational_training(config)
    output = capsys.readouterr().out

    assert "[turn" in output


def test_trick_room_move_reverses_next_turn_order():
    from battle_engine.model import PokemonSet
    from battle_engine.sample_sets import IV31, evs

    fast = PokemonSet(
        species="Starmie",
        item="",
        ability="Natural Cure",
        nature="Timid",
        evs=evs(spa=252, spe=252),
        ivs=IV31,
        moves=["Thunderbolt"],
    )
    slow_setter = PokemonSet(
        species="Reuniclus",
        item="",
        ability="Magic Guard",
        nature="Quiet",
        evs=evs(hp=252, spa=252),
        ivs=IV31,
        moves=["Trick Room", "Shadow Ball"],
    )

    state = make_battle([fast], [slow_setter], seed=201)

    state, first_log = step(state, Action("move", 0), Action("move", 0))
    assert str(first_log).splitlines()[0].startswith("Starmie used Thunderbolt")
    assert "The dimensions were twisted." in str(first_log)
    assert state.field.trick_room_turns > 0

    state, second_log = step(state, Action("move", 0), Action("move", 1))
    assert str(second_log).splitlines()[0].startswith("Reuniclus used Shadow Ball")


def test_trick_room_reverses_only_inside_priority_bracket():
    from battle_engine.model import PokemonSet
    from battle_engine.sample_sets import IV31, evs

    priority_user = PokemonSet(
        species="Scizor",
        item="",
        ability="Technician",
        nature="Adamant",
        evs=evs(atk=252),
        ivs=IV31,
        moves=["Bullet Punch"],
    )
    slow = PokemonSet(
        species="Reuniclus",
        item="",
        ability="Magic Guard",
        nature="Quiet",
        evs=evs(hp=252, spa=252),
        ivs=IV31,
        moves=["Shadow Ball"],
    )

    state = make_battle([priority_user], [slow], seed=202)
    state.field.trick_room_turns = 4

    state, log = step(state, Action("move", 0), Action("move", 0))
    assert str(log).splitlines()[0].startswith("Scizor used Bullet Punch")


def test_trick_room_second_use_cancels_trick_room():
    from battle_engine.model import PokemonSet
    from battle_engine.sample_sets import IV31, evs

    fast = PokemonSet(
        species="Starmie",
        item="",
        ability="Natural Cure",
        nature="Timid",
        evs=evs(spa=252, spe=252),
        ivs=IV31,
        moves=["Thunderbolt"],
    )
    slow_setter = PokemonSet(
        species="Reuniclus",
        item="",
        ability="Magic Guard",
        nature="Quiet",
        evs=evs(hp=252, spa=252),
        ivs=IV31,
        moves=["Trick Room"],
    )

    state = make_battle([fast], [slow_setter], seed=203)
    state.field.trick_room_turns = 4

    state, log = step(state, Action("move", 0), Action("move", 0))
    assert "The twisted dimensions returned to normal." in str(log)
    assert state.field.trick_room_turns == 0


def test_python_backend_wraps_existing_engine():
    from battle_engine.backends import PythonBattleBackend
    from battle_engine.sample_sets import TEAM_BALANCE_A, TEAM_BALANCE_B

    backend = PythonBattleBackend(TEAM_BALANCE_A, TEAM_BALANCE_B, seed=301)
    before = backend.state_summary()

    assert before["turn"] == 1
    assert backend.legal_actions(1)
    assert backend.legal_actions(2)

    result = backend.step(backend.legal_actions(1)[0], backend.legal_actions(2)[0])

    assert result.state_summary["turn"] >= 1
    assert isinstance(result.log_lines, list)
    assert result.winner in {None, 0, 1, 2}


def test_python_backend_reset_changes_state():
    from battle_engine.backends import PythonBattleBackend
    from battle_engine.sample_sets import TEAM_BALANCE_A, TEAM_BALANCE_B

    backend = PythonBattleBackend()
    summary = backend.reset(TEAM_BALANCE_A, TEAM_BALANCE_B, seed=302)

    assert summary["p1"]["active"] == TEAM_BALANCE_A[0].species
    assert summary["p2"]["active"] == TEAM_BALANCE_B[0].species


def test_showdown_set_text_exports_importable_shape():
    from battle_engine.backends import showdown_set_text
    from battle_engine.sample_sets import TYRANITAR_CB

    text = showdown_set_text(TYRANITAR_CB)

    assert "Tyranitar @ Choice Band" in text
    assert "Ability:" in text
    assert "EVs:" in text
    assert "Adamant Nature" in text
    assert "- Crunch" in text


def test_showdown_backend_check_is_structured():
    from battle_engine.backends import ShowdownBattleBackend

    check = ShowdownBattleBackend(node_bin="definitely-not-node").check_available()

    assert check["available"] is False
    assert "reason" in check
    assert "node_bin" in check


def test_showdown_backend_reset_returns_importable_teams_without_running_server():
    from battle_engine.backends import ShowdownBattleBackend
    from battle_engine.sample_sets import TEAM_BALANCE_A, TEAM_BALANCE_B

    backend = ShowdownBattleBackend(node_bin="definitely-not-node")
    summary = backend.reset(TEAM_BALANCE_A, TEAM_BALANCE_B, seed=303)

    assert summary["backend"] == "showdown"
    assert "team1_importable" in summary
    assert TEAM_BALANCE_A[0].species in summary["team1_importable"]


def test_showdown_backend_steps_battle_when_available():
    import pytest

    from battle_engine.backends import ShowdownBattleBackend

    backend = ShowdownBattleBackend()
    check = backend.check_available()
    if not check.get("available"):
        pytest.skip(f"Showdown backend unavailable: {check.get('reason')}")

    summary = backend.reset([TYRANITAR_CB], [DRAGONITE_DD], seed=304)

    assert summary["backend"] == "showdown"
    assert summary["turn"] == 1
    assert Action("move", 0) in backend.legal_actions(1)
    assert Action("move", 0) in backend.legal_actions(2)

    result = backend.step(Action("move", 0), Action("move", 0))

    assert result.state_summary["turn"] >= 2
    assert result.state_summary["p2"]["mons"][0]["hp"] < result.state_summary["p2"]["mons"][0]["max_hp"]
    assert isinstance(result.log_lines, list)
    assert result.winner in {None, 0, 1, 2}


def test_mcts_search_backend_with_showdown_backend_when_available():
    import pytest

    from battle_engine.backends import ShowdownBattleBackend
    from battle_engine.mcts import MCTSAgent, MCTSConfig

    backend = ShowdownBattleBackend()
    check = backend.check_available()
    if not check.get("available"):
        pytest.skip(f"Showdown backend unavailable: {check.get('reason')}")

    backend.reset([TYRANITAR_CB], [DRAGONITE_DD], seed=305)
    legal = backend.legal_actions(1)
    root_summary = backend.state_summary()
    agent = MCTSAgent(MCTSConfig(simulations=1, max_depth=0), rng=__import__("random").Random(3))

    result = agent.search_backend(backend, 1)

    assert result.action in legal
    assert result.stats
    assert sum(s.visits for s in result.stats) == 1
    assert backend.state_summary() == root_summary


def test_create_backend_factory_builds_python_backend():
    from battle_engine.backends import PythonBattleBackend, create_backend
    from battle_engine.sample_sets import TEAM_BALANCE_A, TEAM_BALANCE_B

    backend = create_backend("python", TEAM_BALANCE_A, TEAM_BALANCE_B, seed=306)

    assert isinstance(backend, PythonBattleBackend)
    assert backend.state_summary()["p1"]["active"] == TEAM_BALANCE_A[0].species


def test_create_backend_factory_rejects_unknown_backend():
    import pytest

    from battle_engine.backends import create_backend

    with pytest.raises(ValueError, match="Unknown backend"):
        create_backend("nonsense")  # type: ignore[arg-type]


def test_pokemmo_showdown_mod_template_exists():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    template = root / "showdown_mod_template"

    assert (template / "config/custom-formats.ts").exists()
    assert (template / "data/mods/pokemmo/scripts.ts").exists()
    assert (template / "data/mods/pokemmo/typechart.ts").exists()
    assert (template / "data/mods/pokemmo/pokedex.ts").exists()
    assert (template / "data/mods/pokemmo/rulesets.ts").exists()


def test_pokemmo_showdown_mod_template_uses_gen8_base_and_gen5_type_chart():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    scripts = (root / "showdown_mod_template/data/mods/pokemmo/scripts.ts").read_text(encoding="utf-8")
    typechart = (root / "showdown_mod_template/data/mods/pokemmo/typechart.ts").read_text(encoding="utf-8")
    pokedex = (root / "showdown_mod_template/data/mods/pokemmo/pokedex.ts").read_text(encoding="utf-8")

    assert "inherit: 'gen8'" in scripts
    assert "Ghost: 2" in typechart  # Gen 5 Steel resists Ghost.
    assert "Dark: 2" in typechart   # Gen 5 Steel resists Dark.
    assert 'fairy: {' in typechart
    assert 'isNonstandard: "Past"' in typechart
    assert 'togekiss: { inherit: true, types: ["Normal", "Flying"] }' in pokedex


def test_install_showdown_mod_dry_run_copies_expected_files(tmp_path):
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    showdown = tmp_path / "pokemon-showdown"
    (showdown / "sim").mkdir(parents=True)
    (showdown / "data").mkdir()
    (showdown / "config").mkdir()
    (showdown / "package.json").write_text("{}", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/install_showdown_mod.py"),
            "--showdown-root",
            str(showdown),
            "--dry-run",
        ],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0
    assert "WOULD COPY" in result.stdout
    assert not (showdown / "data/mods/pokemmo/typechart.ts").exists()


def test_install_and_check_pokemmo_mod(tmp_path):
    import json
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    showdown = tmp_path / "pokemon-showdown"
    (showdown / "sim").mkdir(parents=True)
    (showdown / "data").mkdir()
    (showdown / "config").mkdir()
    (showdown / "package.json").write_text("{}", encoding="utf-8")

    install = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/install_showdown_mod.py"),
            "--showdown-root",
            str(showdown),
        ],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=30,
    )
    assert install.returncode == 0

    check = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/check_pokemmo_mod.py"),
            "--showdown-root",
            str(showdown),
        ],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=30,
    )
    assert check.returncode == 0
    assert '"ok": true' in check.stdout

def test_pokemmo_rulesets_uses_showdown_format_data_table():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    rulesets = (root / "showdown_mod_template/data/mods/pokemmo/rulesets.ts").read_text(encoding="utf-8")
    typechart = (root / "showdown_mod_template/data/mods/pokemmo/typechart.ts").read_text(encoding="utf-8")

    assert "FormatDataTable" in rulesets
    assert "ModdedFormatData" not in rulesets
    assert "\tsteel: {" in typechart
    assert "\tNormal: {" not in typechart


def test_compare_backends_compact_summary_normalizes_python_and_showdown_shapes():
    from examples.compare_backends import compact_summary, diff_compact_summaries

    python_raw = {
        "turn": 2,
        "winner": None,
        "weather": "sandstorm",
        "p1": {"active": "Tyranitar", "hp": 150, "max_hp": 200, "status": None, "alive": 1, "hazards": {}},
        "p2": {"active": "Dragonite", "hp": 100, "max_hp": 200, "status": "brn", "alive": 1, "hazards": {}},
    }
    showdown_raw = {
        "turn": 2,
        "winner": None,
        "weather": "sandstorm",
        "p1": {
            "active": "Tyranitar",
            "active_index": 0,
            "alive_count": 1,
            "side_conditions": {},
            "mons": [{"species": "Tyranitar", "hp": 150, "max_hp": 200, "status": None, "active": True}],
        },
        "p2": {
            "active": "Dragonite",
            "active_index": 0,
            "alive_count": 1,
            "side_conditions": {},
            "mons": [{"species": "Dragonite", "hp": 100, "max_hp": 200, "status": "brn", "active": True}],
        },
    }

    python_summary = compact_summary(python_raw)
    showdown_summary = compact_summary(showdown_raw)

    assert python_summary["p1"]["hp_fraction"] == 0.75
    assert showdown_summary["p2"]["hp_fraction"] == 0.5
    assert diff_compact_summaries(python_summary, showdown_summary) == []


def test_compare_backends_script_help_runs():
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / "examples/compare_backends.py"), "--help"],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0
    assert "Compare Python and Showdown backend summaries" in result.stdout


def test_backend_selfplay_script_writes_python_jsonl(tmp_path):
    import json
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    out = tmp_path / "selfplay.jsonl"
    result = subprocess.run(
        [
            sys.executable,
            str(root / "examples/backend_selfplay.py"),
            "--backend",
            "python",
            "--teams",
            "single",
            "--games",
            "1",
            "--turns",
            "1",
            "--sims",
            "1",
            "--depth",
            "0",
            "--seed",
            "1",
            "--out",
            str(out),
        ],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stdout
    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2

    first = json.loads(lines[0])
    second = json.loads(lines[1])
    assert first["schema_version"] == 1
    assert first["record_type"] == "decision"
    assert first["backend"] == "python"
    assert first["player"] == 1
    assert second["player"] == 2
    assert first["state_summary"]["p1"]["active"] == "Tyranitar"
    assert first["legal_actions"]
    assert first["chosen_action"] in first["legal_actions"]
    assert first["mcts"]["simulations"] == 1
    assert first["final_winner"] in {None, 0, 1, 2}
    assert first["value_target"] in {-1.0, 0.0, 1.0}



def test_backend_selfplay_can_save_replay_logs(tmp_path):
    import json
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    out = tmp_path / "selfplay.jsonl"
    replay_dir = tmp_path / "replays"
    result = subprocess.run(
        [
            sys.executable,
            str(root / "examples/backend_selfplay.py"),
            "--backend",
            "python",
            "--teams",
            "single",
            "--games",
            "1",
            "--turns",
            "1",
            "--sims",
            "1",
            "--depth",
            "0",
            "--out",
            str(out),
            "--save-replay-logs",
            str(replay_dir),
        ],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stdout
    log_path = replay_dir / "game_0000.log"
    meta_path = replay_dir / "game_0000.json"
    assert log_path.exists()
    assert meta_path.exists()
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    assert metadata["source"] == "backend_selfplay"
    assert metadata["backend"] == "python"
    assert metadata["replay_log_path"] == str(log_path)
    assert metadata["line_count"] >= 0
    assert "raw Showdown battle protocol" in metadata["viewer_note"]

def test_backend_selfplay_script_help_runs():
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / "examples/backend_selfplay.py"), "--help"],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0
    assert "Run backend self-play" in result.stdout


def test_backend_state_features_support_python_summary_shape():
    from battle_engine.backend_features import backend_action_features, backend_state_features
    from battle_engine.model import Action

    summary = {
        "turn": 2,
        "winner": None,
        "weather": "sand",
        "terrain": None,
        "p1": {
            "active": "Tyranitar",
            "hp": 88,
            "max_hp": 176,
            "status": "brn",
            "alive": 3,
            "hazards": {"sr": True, "spikes": 2, "toxic_spikes": 1},
            "needs_replacement": False,
        },
        "p2": {
            "active": "Dragonite",
            "hp": 167,
            "max_hp": 167,
            "status": None,
            "alive": 2,
            "hazards": {"sr": False, "spikes": 0, "toxic_spikes": 0},
            "needs_replacement": True,
        },
    }

    state = backend_state_features(summary, 1)
    action = backend_action_features(summary, 1, Action("switch", 2))

    assert state["bias"] == 1.0
    assert state["own_active_hp"] == 0.5
    assert state["opp_active_hp"] == 1.0
    assert state["weather_sandstorm"] == 1.0
    assert state["own_hazards_any"] == 1.0
    assert state["own_spikes"] == 2 / 3
    assert state["own_toxic_spikes"] == 0.5
    assert state["own_status_burn"] == 1.0
    assert state["opp_needs_replacement"] == 1.0
    assert action["action_is_switch"] == 1.0
    assert action["action_index_2"] == 1.0
    assert action["switch_with_own_hazards"] == 1.0


def test_backend_state_features_support_showdown_summary_shape():
    from battle_engine.backend_features import backend_action_features, backend_state_features

    summary = {
        "turn": 2,
        "winner": None,
        "weather": "sandstorm",
        "terrain": "electricterrain",
        "p1": {
            "active": "Tyranitar",
            "active_index": 0,
            "alive_count": 1,
            "needs_replacement": False,
            "side_conditions": {"Stealth Rock": 1},
            "mons": [
                {"species": "Tyranitar", "hp": 176, "max_hp": 176, "status": None, "active": True}
            ],
        },
        "p2": {
            "active": "Dragonite",
            "active_index": 0,
            "alive_count": 1,
            "needs_replacement": False,
            "side_conditions": {},
            "mons": [
                {"species": "Dragonite", "hp": 94, "max_hp": 167, "status": "par", "active": True}
            ],
        },
    }

    state = backend_state_features(summary, 1)
    action = backend_action_features(summary, 1, {"kind": "move", "index": 0})

    assert state["own_active_hp"] == 1.0
    assert round(state["opp_active_hp"], 4) == round(94 / 167, 4)
    assert state["weather_sandstorm"] == 1.0
    assert state["terrain_any"] == 1.0
    assert state["own_stealth_rock"] == 1.0
    assert state["opp_status_paralysis"] == 1.0
    assert action["action_is_move"] == 1.0
    assert action["action_index_0"] == 1.0


def test_backend_record_features_from_selfplay_record():
    from battle_engine.backend_features import ACTION_FEATURE_NAMES, STATE_FEATURE_NAMES, backend_record_features

    record = {
        "record_type": "decision",
        "player": 2,
        "chosen_action": {"kind": "move", "index": 0},
        "state_summary": {
            "weather": None,
            "p1": {"active": "A", "hp": 10, "max_hp": 100, "status": None, "alive": 1, "hazards": {}},
            "p2": {"active": "B", "hp": 90, "max_hp": 100, "status": None, "alive": 1, "hazards": {}},
        },
    }

    features = backend_record_features(record)
    assert tuple(features["state"].keys()) == STATE_FEATURE_NAMES
    assert tuple(features["action"].keys()) == ACTION_FEATURE_NAMES
    assert features["state"]["own_active_hp"] == 0.9
    assert features["state"]["opp_active_hp"] == 0.1
    assert features["action"]["move_when_opp_low_hp"] == 1.0


def test_inspect_backend_features_script_reads_jsonl(tmp_path):
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    out = tmp_path / "selfplay.jsonl"
    out.write_text(
        '{"record_type":"decision","backend":"python","game_id":0,"turn_index":1,"player":1,'
        '"chosen_action":{"kind":"move","index":0},"value_target":1.0,'
        '"state_summary":{"weather":"sand","p1":{"active":"Tyranitar","hp":176,"max_hp":176,'
        '"status":null,"alive":1,"hazards":{}},"p2":{"active":"Dragonite","hp":94,'
        '"max_hp":167,"status":null,"alive":1,"hazards":{}}}}\n',
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(root / "examples/inspect_backend_features.py"), str(out), "--limit", "1", "--top", "5"],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stdout
    assert "Record 1" in result.stdout
    assert "own_active_hp=1" in result.stdout
    assert "action_is_move=1" in result.stdout


def test_inspect_backend_features_script_help_runs():
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / "examples/inspect_backend_features.py"), "--help"],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0
    assert "Inspect backend self-play JSONL records" in result.stdout


def _backend_training_record(*, chosen_index: int = 0, player: int = 1, value_target: float = 1.0) -> dict:
    return {
        "record_type": "decision",
        "backend": "python",
        "game_id": 0,
        "turn_index": 1,
        "player": player,
        "legal_actions": [
            {"kind": "move", "index": 0},
            {"kind": "move", "index": 1},
            {"kind": "switch", "index": 2},
        ],
        "chosen_action": {"kind": "move", "index": chosen_index},
        "value_target": value_target,
        "state_summary": {
            "weather": "sand",
            "terrain": None,
            "p1": {
                "active": "Tyranitar",
                "hp": 176,
                "max_hp": 176,
                "status": None,
                "alive": 1,
                "hazards": {},
            },
            "p2": {
                "active": "Dragonite",
                "hp": 94,
                "max_hp": 167,
                "status": None,
                "alive": 1,
                "hazards": {},
            },
        },
    }


def test_backend_linear_agent_updates_from_record_and_round_trips(tmp_path):
    from battle_engine.backend_agent import BackendLinearPolicyValueAgent
    from battle_engine.backend_features import action_from_payload

    record = _backend_training_record(chosen_index=1, value_target=1.0)
    agent = BackendLinearPolicyValueAgent(learning_rate=0.1)

    before = agent.action_priors(record["state_summary"], 1, [action_from_payload(a) for a in record["legal_actions"]])
    metrics = agent.update_from_record(record)
    after = agent.action_priors(record["state_summary"], 1, [action_from_payload(a) for a in record["legal_actions"]])

    chosen = action_from_payload(record["chosen_action"])
    assert metrics["action_label"] == "move:1"
    assert metrics["policy_loss"] is not None
    assert metrics["value_loss"] is not None
    assert after[chosen] > before[chosen]
    assert agent.evaluate(record["state_summary"], 1) > 0
    assert agent.policy_weights
    assert agent.value_weights

    model_path = tmp_path / "backend_agent.json"
    agent.save(model_path)
    loaded = BackendLinearPolicyValueAgent.load(model_path)
    assert loaded.to_dict() == agent.to_dict()


def test_backend_linear_agent_ranks_and_explains_actions():
    from battle_engine.backend_agent import BackendLinearPolicyValueAgent

    record = _backend_training_record(chosen_index=1, value_target=1.0)
    agent = BackendLinearPolicyValueAgent(
        policy_weights={"action_index_1": 2.0, "action_is_move": 0.5},
        value_weights={"bias": 0.25},
    )

    ranked = agent.rank_actions(record["state_summary"], 1, record["legal_actions"], top_contributions=2)

    assert ranked[0]["label"] == "move:1"
    assert ranked[0]["score"] > ranked[1]["score"]
    assert ranked[0]["probability"] > 0.0
    assert ranked[0]["top_contributions"]
    assert ranked[0]["top_contributions"][0]["feature"] == "action_index_1"
    assert agent.top_weights(limit=1)["policy"] == [{"feature": "action_index_1", "weight": 2.0}]


def test_train_backend_agent_script_trains_from_jsonl(tmp_path):
    import json
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    data_path = tmp_path / "records.jsonl"
    model_path = tmp_path / "backend_agent.json"
    metrics_path = tmp_path / "metrics.json"

    records = [
        _backend_training_record(chosen_index=0, player=1, value_target=1.0),
        _backend_training_record(chosen_index=1, player=2, value_target=-1.0),
    ]
    data_path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(root / "examples/train_backend_agent.py"),
            str(data_path),
            "--out",
            str(model_path),
            "--metrics-out",
            str(metrics_path),
            "--epochs",
            "2",
            "--learning-rate",
            "0.1",
            "--no-shuffle",
        ],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stdout
    assert "Trained backend agent" in result.stdout
    assert "feature_schema=v" in result.stdout
    assert "Top policy weights" in result.stdout

    model = json.loads(model_path.read_text(encoding="utf-8"))
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert model["model_type"] == "BackendLinearPolicyValueAgent"
    assert model["policy_weights"]
    assert model["value_weights"]
    assert metrics["records"] == 2
    assert metrics["updates"] == 4
    assert metrics["feature_schema_version"] >= 5
    assert metrics["top_weights"]["policy"]


def test_train_backend_agent_script_help_runs():
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / "examples/train_backend_agent.py"), "--help"],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0
    assert "Train a lightweight backend policy/value agent" in result.stdout


def test_evaluate_backend_agent_summarizes_results():
    from examples.evaluate_backend_agent import summarize_results

    results = [
        {"winner": 1, "agent_won": True, "opponent_won": False, "unresolved": False, "turns_played": 2},
        {"winner": 2, "agent_won": False, "opponent_won": True, "unresolved": False, "turns_played": 4},
        {"winner": None, "agent_won": False, "opponent_won": False, "unresolved": True, "turns_played": 6},
    ]

    summary = summarize_results(results)
    assert summary["games"] == 3
    assert summary["agent_wins"] == 1
    assert summary["opponent_wins"] == 1
    assert summary["unresolved"] == 1
    assert summary["agent_win_rate"] == 1 / 3
    assert summary["average_turns"] == 4


def test_evaluate_backend_agent_script_runs_python_backend(tmp_path):
    import json
    import subprocess
    import sys
    from pathlib import Path

    from battle_engine.backend_agent import BackendLinearPolicyValueAgent

    root = Path(__file__).resolve().parents[1]
    model_path = tmp_path / "backend_agent.json"
    report_path = tmp_path / "evaluation.json"
    agent = BackendLinearPolicyValueAgent(
        policy_weights={"action_is_move": 1.0, "action_index_1": 2.0},
        value_weights={"bias": 0.25},
        name="test-eval-agent",
    )
    agent.save(model_path)

    result = subprocess.run(
        [
            sys.executable,
            str(root / "examples/evaluate_backend_agent.py"),
            "--agent",
            str(model_path),
            "--backend",
            "python",
            "--teams",
            "single",
            "--games",
            "1",
            "--turns",
            "2",
            "--opponent",
            "first",
            "--out",
            str(report_path),
            "--trace-actions",
            "2",
            "--explain-top",
            "2",
        ],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stdout
    assert "Backend agent evaluation" in result.stdout
    assert "Feature schema:" in result.stdout
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["summary"]["games"] == 1
    assert report["summary"]["backend"] == "python"
    assert len(report["games"]) == 1
    assert report["summary"]["trace_actions"] == 2
    assert report["games"][0]["team1_species"] == ["Tyranitar"]
    trace = report["games"][0]["action_trace"]
    assert trace
    assert trace[0]["chosen_label"].startswith("move:") or trace[0]["chosen_label"].startswith("switch:")
    assert trace[0]["ranked_actions"]
    assert "chosen_rank" in trace[0]



def test_evaluate_backend_agent_can_save_replay_logs(tmp_path):
    import json
    import subprocess
    import sys
    from pathlib import Path

    from battle_engine.backend_agent import BackendLinearPolicyValueAgent

    root = Path(__file__).resolve().parents[1]
    model_path = tmp_path / "backend_agent.json"
    report_path = tmp_path / "evaluation.json"
    replay_dir = tmp_path / "eval_replays"
    BackendLinearPolicyValueAgent(policy_weights={"action_is_move": 1.0}).save(model_path)

    result = subprocess.run(
        [
            sys.executable,
            str(root / "examples/evaluate_backend_agent.py"),
            "--agent",
            str(model_path),
            "--backend",
            "python",
            "--teams",
            "single",
            "--games",
            "1",
            "--turns",
            "1",
            "--opponent",
            "first",
            "--out",
            str(report_path),
            "--save-replay-logs",
            str(replay_dir),
        ],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stdout
    report = json.loads(report_path.read_text(encoding="utf-8"))
    replay_files = report["games"][0]["replay_files"]
    assert replay_files["replay_log_path"] == str(replay_dir / "game_0000.log")
    assert Path(replay_files["metadata_path"]).exists()
    metadata = json.loads(Path(replay_files["metadata_path"]).read_text(encoding="utf-8"))
    assert metadata["source"] == "evaluate_backend_agent"
    assert metadata["agent_name"]

def test_evaluate_backend_agent_script_help_runs():
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / "examples/evaluate_backend_agent.py"), "--help"],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0
    assert "Evaluate a saved backend policy/value agent" in result.stdout


def test_evaluate_backend_agent_damage_policy_prefers_expected_damage():
    from examples.evaluate_backend_agent import _choose_damage_policy_action

    summary = {
        "weather": None,
        "p1": {
            "active": "Tyranitar",
            "types": ["Rock", "Dark"],
            "level": 50,
            "stats": {"atk": 204, "def": 130, "spa": 103, "spd": 120},
            "boosts": {"atk": 0, "def": 0, "spa": 0, "spd": 0},
            "hp": 176,
            "max_hp": 176,
            "status": None,
            "alive": 1,
            "hazards": {},
        },
        "p2": {
            "active": "Dragonite",
            "types": ["Dragon", "Flying"],
            "level": 50,
            "stats": {"atk": 186, "def": 115, "spa": 108, "spd": 120},
            "boosts": {"atk": 0, "def": 0, "spa": 0, "spd": 0},
            "hp": 167,
            "max_hp": 167,
            "status": None,
            "alive": 1,
            "hazards": {},
        },
    }
    legal = [
        Action("move", 0, {"id": "crunch", "type": "Dark", "category": "physical", "base_power": 80, "accuracy": 100}),
        Action("move", 1, {"id": "stoneedge", "type": "Rock", "category": "physical", "base_power": 100, "accuracy": 80}),
        Action("move", 2, {"id": "dragondance", "type": "Dragon", "category": "status", "base_power": 0, "accuracy": True}),
    ]

    chosen = _choose_damage_policy_action(summary, 1, legal)

    assert chosen.index == 1
    assert chosen.metadata["id"] == "stoneedge"


def test_action_metadata_does_not_affect_action_identity():
    left = Action("move", 0, {"id": "crunch"})
    right = Action("move", 0, {"id": "stoneedge"})

    assert left == right
    assert len({left, right}) == 1


def test_python_backend_legal_actions_include_move_metadata():
    from battle_engine.backend_features import backend_action_features, backend_action_label
    from battle_engine.backends import PythonBattleBackend

    backend = PythonBattleBackend([TYRANITAR_CB], [DRAGONITE_DD], seed=401)
    crunch = next(action for action in backend.legal_actions(1) if action.kind == "move" and action.index == 0)

    assert crunch.metadata["name"] == "Crunch"
    assert crunch.metadata["type"] == "Dark"
    assert crunch.metadata["category"] == "physical"
    assert crunch.metadata["base_power"] == 80
    assert backend_action_label(crunch) == "move:crunch"

    features = backend_action_features(backend.state_summary(), 1, crunch)
    assert features["move_base_power"] == 0.8
    assert features["move_accuracy"] == 1.0
    assert features["move_is_physical"] == 1.0
    assert features["move_type_dark"] == 1.0


def test_backend_selfplay_action_payload_preserves_action_metadata():
    from examples.backend_selfplay import action_to_payload

    payload = action_to_payload(
        Action(
            "move",
            1,
            {
                "id": "stoneedge",
                "name": "Stone Edge",
                "type": "Rock",
                "category": "physical",
                "base_power": 100,
                "accuracy": 80,
            },
        )
    )

    assert payload == {
        "kind": "move",
        "index": 1,
        "id": "stoneedge",
        "name": "Stone Edge",
        "type": "Rock",
        "category": "physical",
        "base_power": 100,
        "accuracy": 80,
    }


def test_backend_action_features_use_move_metadata_from_payload():
    from battle_engine.backend_features import backend_action_features, backend_action_label, action_from_payload

    summary = {
        "weather": None,
        "terrain": None,
        "p1": {"active": "Tyranitar", "hp": 176, "max_hp": 176, "status": None, "alive": 1, "hazards": {}},
        "p2": {"active": "Dragonite", "hp": 20, "max_hp": 167, "status": None, "alive": 1, "hazards": {}},
    }
    payload = {
        "kind": "move",
        "index": 1,
        "id": "stoneedge",
        "name": "Stone Edge",
        "type": "Rock",
        "category": "physical",
        "base_power": 100,
        "accuracy": 80,
        "priority": 0,
    }

    action = action_from_payload(payload)
    features = backend_action_features(summary, 1, action)

    assert action.metadata["id"] == "stoneedge"
    assert backend_action_label(action) == "move:stoneedge"
    assert features["move_base_power"] == 1.0
    assert features["move_accuracy"] == 0.8
    assert features["move_is_physical"] == 1.0
    assert features["move_type_rock"] == 1.0
    assert features["move_when_opp_low_hp"] == 1.0




def test_backend_action_features_include_stab_and_type_effectiveness():
    from battle_engine.backend_features import backend_action_features

    summary = {
        "weather": None,
        "terrain": None,
        "p1": {
            "active": "Tyranitar",
            "types": ["Rock", "Dark"],
            "hp": 176,
            "max_hp": 176,
            "status": None,
            "alive": 1,
            "hazards": {},
        },
        "p2": {
            "active": "Dragonite",
            "types": ["Dragon", "Flying"],
            "hp": 167,
            "max_hp": 167,
            "status": None,
            "alive": 1,
            "hazards": {},
        },
    }

    stone_edge = {
        "kind": "move",
        "index": 1,
        "id": "stoneedge",
        "type": "Rock",
        "category": "physical",
        "base_power": 100,
        "accuracy": 80,
    }
    crunch = {
        "kind": "move",
        "index": 0,
        "id": "crunch",
        "type": "Dark",
        "category": "physical",
        "base_power": 80,
        "accuracy": 100,
    }

    rock_features = backend_action_features(summary, 1, stone_edge)
    dark_features = backend_action_features(summary, 1, crunch)

    assert rock_features["own_type_rock"] == 1.0
    assert rock_features["own_type_dark"] == 1.0
    assert rock_features["opp_type_dragon"] == 1.0
    assert rock_features["opp_type_flying"] == 1.0
    assert rock_features["move_stab"] == 1.0
    assert rock_features["move_effectiveness"] == 2.0
    assert rock_features["move_super_effective"] == 1.0
    assert rock_features["move_resisted"] == 0.0
    assert rock_features["move_immune"] == 0.0
    assert rock_features["move_effective_power"] == 2.0

    assert dark_features["move_stab"] == 1.0
    assert dark_features["move_effectiveness"] == 1.0
    assert dark_features["move_neutral"] == 1.0


def test_backend_action_features_mark_resisted_and_immune_moves():
    from battle_engine.backend_features import backend_action_features

    resisted_summary = {
        "p1": {"active": "Tyranitar", "types": ["Rock", "Dark"], "hp": 176, "max_hp": 176, "alive": 1, "hazards": {}},
        "p2": {"active": "Skarmory", "types": ["Steel", "Flying"], "hp": 140, "max_hp": 140, "alive": 1, "hazards": {}},
    }
    immune_summary = {
        "p1": {"active": "Tyranitar", "types": ["Rock", "Dark"], "hp": 176, "max_hp": 176, "alive": 1, "hazards": {}},
        "p2": {"active": "Gengar", "types": ["Ghost", "Poison"], "hp": 120, "max_hp": 120, "alive": 1, "hazards": {}},
    }

    crunch = {"kind": "move", "index": 0, "type": "Dark", "category": "physical", "base_power": 80}
    normal_hit = {"kind": "move", "index": 0, "type": "Normal", "category": "physical", "base_power": 80}

    resisted = backend_action_features(resisted_summary, 1, crunch)
    immune = backend_action_features(immune_summary, 1, normal_hit)

    assert resisted["move_effectiveness"] == 0.5
    assert resisted["move_resisted"] == 1.0
    assert resisted["move_effective_power"] == 0.4
    assert immune["move_effectiveness"] == 0.0
    assert immune["move_immune"] == 1.0
    assert immune["move_effective_power"] == 0.0



def test_python_backend_summary_exposes_stats_for_backend_damage_features():
    from battle_engine.backends import PythonBattleBackend

    backend = PythonBattleBackend([TYRANITAR_CB], [DRAGONITE_DD], seed=403)
    summary = backend.state_summary()

    assert summary["p1"]["level"] == 50
    assert summary["p1"]["stats"]["atk"] > 100
    assert summary["p1"]["boosts"]["atk"] == 0
    assert summary["p2"]["stats"]["def"] > 0


def test_backend_action_features_include_rough_damage_estimates():
    from battle_engine.backend_features import backend_action_features

    summary = {
        "weather": None,
        "p1": {
            "active": "Tyranitar",
            "types": ["Rock", "Dark"],
            "level": 50,
            "stats": {"atk": 204, "def": 130, "spa": 103, "spd": 120},
            "boosts": {"atk": 0, "def": 0, "spa": 0, "spd": 0},
            "hp": 176,
            "max_hp": 176,
            "status": None,
            "alive": 1,
            "hazards": {},
        },
        "p2": {
            "active": "Dragonite",
            "types": ["Dragon", "Flying"],
            "level": 50,
            "stats": {"atk": 186, "def": 115, "spa": 108, "spd": 120},
            "boosts": {"atk": 0, "def": 0, "spa": 0, "spd": 0},
            "hp": 167,
            "max_hp": 167,
            "status": None,
            "alive": 1,
            "hazards": {},
        },
    }
    stone_edge = {
        "kind": "move",
        "index": 1,
        "id": "stoneedge",
        "type": "Rock",
        "category": "physical",
        "base_power": 100,
        "accuracy": 80,
    }
    status_move = {
        "kind": "move",
        "index": 0,
        "id": "dragondance",
        "type": "Dragon",
        "category": "status",
        "base_power": 0,
        "accuracy": True,
    }

    features = backend_action_features(summary, 1, stone_edge)
    status_features = backend_action_features(summary, 2, status_move)

    assert features["move_damage_estimate"] > 0.5
    assert features["move_expected_damage"] < features["move_damage_estimate"]
    assert features["move_damage_accuracy_discount"] > 0.0
    assert features["move_can_ko"] == 1.0
    assert features["move_2hko"] == 1.0
    assert features["move_overkill"] > 0.0

    assert status_features["move_damage_estimate"] == 0.0
    assert status_features["move_can_ko"] == 0.0


def test_backend_action_features_rough_damage_uses_burn_and_weather():
    from battle_engine.backend_features import backend_action_features

    base_summary = {
        "weather": None,
        "p1": {
            "active": "Starmie",
            "types": ["Water", "Psychic"],
            "level": 50,
            "stats": {"atk": 85, "def": 105, "spa": 152, "spd": 105},
            "boosts": {"atk": 0, "def": 0, "spa": 0, "spd": 0},
            "hp": 136,
            "max_hp": 136,
            "status": None,
            "alive": 1,
            "hazards": {},
        },
        "p2": {
            "active": "Tyranitar",
            "types": ["Rock", "Dark"],
            "level": 50,
            "stats": {"atk": 204, "def": 130, "spa": 103, "spd": 120},
            "boosts": {"atk": 0, "def": 0, "spa": 0, "spd": 0},
            "hp": 176,
            "max_hp": 176,
            "status": None,
            "alive": 1,
            "hazards": {},
        },
    }
    surf = {"kind": "move", "index": 0, "type": "Water", "category": "special", "base_power": 95, "accuracy": 100}
    fire_punch = {"kind": "move", "index": 1, "type": "Fire", "category": "physical", "base_power": 75, "accuracy": 100}

    dry = backend_action_features(base_summary, 1, surf)
    rain_summary = dict(base_summary, weather="rain")
    rain = backend_action_features(rain_summary, 1, surf)

    burned_summary = {**base_summary, "p1": {**base_summary["p1"], "status": "brn"}}
    physical_dry = backend_action_features(base_summary, 1, fire_punch)
    physical_burned = backend_action_features(burned_summary, 1, fire_punch)

    assert rain["move_damage_estimate"] > dry["move_damage_estimate"]
    assert physical_burned["move_damage_estimate"] < physical_dry["move_damage_estimate"]

def test_showdown_backend_legal_actions_include_move_metadata_when_available():
    import pytest

    from battle_engine.backends import ShowdownBattleBackend

    backend = ShowdownBattleBackend()
    check = backend.check_available()
    if not check.get("available"):
        pytest.skip(f"Showdown backend unavailable: {check.get('reason')}")

    backend.reset([TYRANITAR_CB], [DRAGONITE_DD], seed=402)
    moves = [action for action in backend.legal_actions(1) if action.kind == "move"]
    stone_edge = next(action for action in moves if action.index == 1)

    assert stone_edge.metadata["id"] == "stoneedge"
    assert stone_edge.metadata["type"] == "Rock"
    assert stone_edge.metadata["category"] == "physical"
    assert stone_edge.metadata["base_power"] == 100
    assert stone_edge.metadata["accuracy"] == 80


def test_backend_action_features_score_switch_target_hazards_and_types():
    from battle_engine.backend_features import backend_action_features

    summary = {
        "p1": {
            "active": "Gengar",
            "types": ["Ghost", "Poison"],
            "hp": 20,
            "max_hp": 120,
            "status": "brn",
            "alive": 2,
            "hazards": {"sr": True, "spikes": 1},
        },
        "p2": {
            "active": "Dragonite",
            "types": ["Dragon", "Flying"],
            "hp": 167,
            "max_hp": 167,
            "status": None,
            "alive": 1,
            "hazards": {},
        },
    }
    switch = {
        "kind": "switch",
        "index": 1,
        "species": "Skarmory",
        "types": ["Steel", "Flying"],
        "hp_fraction": 0.75,
        "status": None,
    }

    features = backend_action_features(summary, 1, switch)

    assert features["action_is_switch"] == 1.0
    assert features["switch_target_type_steel"] == 1.0
    assert features["switch_target_type_flying"] == 1.0
    assert features["switch_target_hp"] == 0.75
    assert features["switch_stealth_rock_damage"] == 0.125
    assert features["switch_spikes_damage"] == 0.0
    assert features["switch_hazard_damage"] == 0.125
    assert features["switch_hp_after_hazards"] == 0.625
    assert features["switch_resists_opp_stab"] == 1.0
    assert features["switch_weak_to_opp_stab"] == 0.0
    assert features["switch_vs_opp_stab_max_effectiveness"] == 0.5
    assert features["switch_when_own_low_hp"] == 1.0
    assert features["switch_when_own_statused"] == 1.0


def test_backend_action_features_mark_switch_fainting_to_hazards():
    from battle_engine.backend_features import backend_action_features

    summary = {
        "p1": {
            "active": "Blissey",
            "types": ["Normal"],
            "hp": 100,
            "max_hp": 300,
            "alive": 2,
            "hazards": {"stealth_rock": True, "spikes": 3},
        },
        "p2": {
            "active": "Tyranitar",
            "types": ["Rock", "Dark"],
            "hp": 176,
            "max_hp": 176,
            "alive": 1,
            "hazards": {},
        },
    }
    switch = {
        "kind": "switch",
        "index": 1,
        "species": "Volcarona",
        "types": ["Bug", "Fire"],
        "hp_fraction": 0.49,
        "status": "par",
    }

    features = backend_action_features(summary, 1, switch)

    assert features["switch_target_type_bug"] == 1.0
    assert features["switch_target_type_fire"] == 1.0
    assert features["switch_target_statused"] == 1.0
    assert features["switch_target_rock_weak"] == 1.0
    assert features["switch_stealth_rock_damage"] == 0.5
    assert features["switch_spikes_damage"] == 0.25
    assert features["switch_hazard_damage"] == 0.75
    assert features["switch_hp_after_hazards"] == 0.0
    assert features["switch_likely_faints_to_hazards"] == 1.0
    assert features["switch_weak_to_opp_stab"] == 1.0


def test_replay_log_writer_saves_log_metadata_and_input_log(tmp_path):
    import json

    from battle_engine.replay_logs import write_replay_files

    result = write_replay_files(
        tmp_path,
        game_id=7,
        log_lines=["|turn|1", "|win|p1"],
        input_log=[">start {}", ">p1 move 1"],
        metadata={"backend": "showdown", "source": "unit"},
    )

    assert (tmp_path / "game_0007.log").read_text(encoding="utf-8").splitlines() == ["|turn|1", "|win|p1"]
    assert (tmp_path / "game_0007.input.log").exists()
    metadata = json.loads((tmp_path / "game_0007.json").read_text(encoding="utf-8"))
    assert metadata["backend"] == "showdown"
    assert metadata["line_count"] == 2
    assert metadata["input_line_count"] == 2
    assert result["input_log_path"] == str(tmp_path / "game_0007.input.log")


def test_run_backend_experiment_script_help_runs():
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / "examples/run_backend_experiment.py"), "--help"],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0
    assert "complete backend learning experiment" in result.stdout


def test_run_backend_experiment_writes_complete_python_experiment(tmp_path):
    import json
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    out_dir = tmp_path / "experiment"
    result = subprocess.run(
        [
            sys.executable,
            str(root / "examples/run_backend_experiment.py"),
            "--backend",
            "python",
            "--teams",
            "single",
            "--games",
            "1",
            "--turns",
            "1",
            "--sims",
            "1",
            "--depth",
            "0",
            "--epochs",
            "1",
            "--eval-games",
            "1",
            "--eval-turns",
            "1",
            "--eval-opponents",
            "first",
            "random",
            "--out-dir",
            str(out_dir),
        ],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stdout
    assert (out_dir / "config.json").exists()
    assert (out_dir / "selfplay.jsonl").exists()
    assert (out_dir / "selfplay_summary.json").exists()
    assert (out_dir / "agent.json").exists()
    assert (out_dir / "train_metrics.json").exists()
    assert (out_dir / "eval_first.json").exists()
    assert (out_dir / "eval_random.json").exists()
    assert (out_dir / "summary.json").exists()
    assert (out_dir / "summary.txt").exists()

    summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["config"]["backend"] == "python"
    assert summary["selfplay"]["records"] == 2
    assert summary["evaluation"]["first"]["games"] == 1
    assert summary["evaluation"]["random"]["games"] == 1
    assert "Backend experiment summary" in (out_dir / "summary.txt").read_text(encoding="utf-8")


def test_compare_experiments_reads_current_validation_schema(tmp_path):
    import json

    from examples.compare_experiments import compare_experiments, render_text_report

    exp_dir = tmp_path / "exp_a"
    exp_dir.mkdir()
    summary = {
        "config": {
            "backend": "python",
            "teams": "round-robin",
            "seed": 7,
            "games": 2,
            "turns": 3,
            "sims": 1,
            "depth": 0,
            "feature_schema_version": 5,
        },
        "selfplay": {"records": 4},
        "validation": {
            "valid": True,
            "errors": [],
            "warnings": ["low switch metadata coverage: 0.0%"],
            "move_metadata_rate": 1.0,
            "switch_metadata_rate": 0.0,
        },
        "training": {"policy_loss_avg": 0.25, "value_loss_avg": 0.5, "updates": 4},
        "evaluation": {
            "first": {
                "games": 1,
                "agent_win_rate": 1.0,
                "opponent_win_rate": 0.0,
                "unresolved_rate": 0.0,
                "average_turns": 2.0,
            }
        },
    }
    (exp_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")

    payload = compare_experiments([exp_dir])
    row = payload["experiments"][0]

    assert row["validation_ok"] is True
    assert row["validation_errors"] == 0
    assert row["validation_warnings"] == 1
    assert row["move_metadata_rate"] == 1.0
    assert row["switch_metadata_rate"] == 0.0

    text = render_text_report(payload)
    assert "True" in text
    assert "100.0%" in text
    assert "0.0%" in text
