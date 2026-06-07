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
