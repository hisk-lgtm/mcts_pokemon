from __future__ import annotations

from .model import SpeciesData, MoveData

NATURES = {
    "Hardy": {},
    "Lonely": {"atk": 1.1, "def": 0.9},
    "Brave": {"atk": 1.1, "spe": 0.9},
    "Adamant": {"atk": 1.1, "spa": 0.9},
    "Naughty": {"atk": 1.1, "spd": 0.9},

    "Bold": {"def": 1.1, "atk": 0.9},
    "Docile": {},
    "Relaxed": {"def": 1.1, "spe": 0.9},
    "Impish": {"def": 1.1, "spa": 0.9},
    "Lax": {"def": 1.1, "spd": 0.9},

    "Timid": {"spe": 1.1, "atk": 0.9},
    "Hasty": {"spe": 1.1, "def": 0.9},
    "Serious": {},
    "Jolly": {"spe": 1.1, "spa": 0.9},
    "Naive": {"spe": 1.1, "spd": 0.9},

    "Modest": {"spa": 1.1, "atk": 0.9},
    "Mild": {"spa": 1.1, "def": 0.9},
    "Quiet": {"spa": 1.1, "spe": 0.9},
    "Bashful": {},
    "Rash": {"spa": 1.1, "spd": 0.9},

    "Calm": {"spd": 1.1, "atk": 0.9},
    "Gentle": {"spd": 1.1, "def": 0.9},
    "Sassy": {"spd": 1.1, "spe": 0.9},
    "Careful": {"spd": 1.1, "spa": 0.9},
    "Quirky": {},
}

# Base stats and type pairs for the current OU compendium import file.
# These are enough to instantiate random teams for manual testing.
SPECIES = {
    "Amoonguss": SpeciesData(("Grass", "Poison"), {"hp": 114, "atk": 85, "def": 70, "spa": 85, "spd": 80, "spe": 30}, weight_kg=10.5),
    "Blissey": SpeciesData(("Normal",), {"hp": 255, "atk": 10, "def": 10, "spa": 75, "spd": 135, "spe": 55}, weight_kg=46.8),
    "Breloom": SpeciesData(("Grass", "Fighting"), {"hp": 60, "atk": 130, "def": 80, "spa": 60, "spd": 60, "spe": 70}, weight_kg=39.2),
    "Bronzong": SpeciesData(("Steel", "Psychic"), {"hp": 67, "atk": 89, "def": 116, "spa": 79, "spd": 116, "spe": 33}, weight_kg=187.0),
    "Chansey": SpeciesData(("Normal",), {"hp": 250, "atk": 5, "def": 5, "spa": 35, "spd": 105, "spe": 50}, weight_kg=34.6),
    "Chandelure": SpeciesData(("Ghost", "Fire"), {"hp": 60, "atk": 55, "def": 90, "spa": 145, "spd": 90, "spe": 80}, weight_kg=34.3),
    "Conkeldurr": SpeciesData(("Fighting",), {"hp": 105, "atk": 140, "def": 95, "spa": 55, "spd": 65, "spe": 45}, weight_kg=87.0),
    "Crawdaunt": SpeciesData(("Water", "Dark"), {"hp": 63, "atk": 120, "def": 85, "spa": 90, "spd": 55, "spe": 55}, weight_kg=32.8),
    "Darmanitan": SpeciesData(("Fire",), {"hp": 105, "atk": 140, "def": 55, "spa": 30, "spd": 55, "spe": 95}, weight_kg=92.9),
    "Dragonite": SpeciesData(("Dragon", "Flying"), {"hp": 91, "atk": 134, "def": 95, "spa": 100, "spd": 100, "spe": 80}, weight_kg=210.0),
    "Empoleon": SpeciesData(("Water", "Steel"), {"hp": 84, "atk": 86, "def": 88, "spa": 111, "spd": 101, "spe": 60}, weight_kg=84.5),
    "Espeon": SpeciesData(("Psychic",), {"hp": 65, "atk": 65, "def": 60, "spa": 130, "spd": 95, "spe": 110}, weight_kg=26.5),
    "Excadrill": SpeciesData(("Ground", "Steel"), {"hp": 110, "atk": 135, "def": 60, "spa": 50, "spd": 65, "spe": 88}, weight_kg=40.4),
    "Ferrothorn": SpeciesData(("Grass", "Steel"), {"hp": 74, "atk": 94, "def": 131, "spa": 54, "spd": 116, "spe": 20}, weight_kg=110.0),
    "Gallade": SpeciesData(("Psychic", "Fighting"), {"hp": 68, "atk": 125, "def": 65, "spa": 65, "spd": 115, "spe": 80}, weight_kg=52.0),
    "Garchomp": SpeciesData(("Dragon", "Ground"), {"hp": 108, "atk": 130, "def": 95, "spa": 80, "spd": 85, "spe": 102}, weight_kg=95.0),
    "Gastrodon": SpeciesData(("Water", "Ground"), {"hp": 111, "atk": 83, "def": 68, "spa": 92, "spd": 82, "spe": 39}, weight_kg=29.9),
    "Gengar": SpeciesData(("Ghost", "Poison"), {"hp": 60, "atk": 65, "def": 60, "spa": 130, "spd": 75, "spe": 110}, weight_kg=40.5),
    "Gliscor": SpeciesData(("Ground", "Flying"), {"hp": 75, "atk": 95, "def": 125, "spa": 45, "spd": 75, "spe": 95}, weight_kg=42.5),
    "Gyarados": SpeciesData(("Water", "Flying"), {"hp": 95, "atk": 125, "def": 79, "spa": 60, "spd": 100, "spe": 81}, weight_kg=235.0),
    "Haxorus": SpeciesData(("Dragon",), {"hp": 76, "atk": 147, "def": 90, "spa": 60, "spd": 70, "spe": 97}, weight_kg=105.5),
    "Hydreigon": SpeciesData(("Dark", "Dragon"), {"hp": 92, "atk": 105, "def": 90, "spa": 125, "spd": 90, "spe": 98}, weight_kg=160.0),
    "Infernape": SpeciesData(("Fire", "Fighting"), {"hp": 76, "atk": 104, "def": 71, "spa": 104, "spd": 71, "spe": 108}, weight_kg=55.0),
    "Jellicent": SpeciesData(("Water", "Ghost"), {"hp": 100, "atk": 60, "def": 70, "spa": 85, "spd": 105, "spe": 60}, weight_kg=135.0),
    "Kabutops": SpeciesData(("Rock", "Water"), {"hp": 60, "atk": 115, "def": 105, "spa": 65, "spd": 70, "spe": 80}, weight_kg=40.5),
    "Kingdra": SpeciesData(("Water", "Dragon"), {"hp": 75, "atk": 95, "def": 95, "spa": 95, "spd": 95, "spe": 85}, weight_kg=152.0),
    "Lucario": SpeciesData(("Fighting", "Steel"), {"hp": 70, "atk": 110, "def": 70, "spa": 115, "spd": 70, "spe": 90}, weight_kg=54.0),
    "Magnezone": SpeciesData(("Electric", "Steel"), {"hp": 70, "atk": 70, "def": 115, "spa": 130, "spd": 90, "spe": 60}, weight_kg=180.0),
    "Mamoswine": SpeciesData(("Ice", "Ground"), {"hp": 110, "atk": 130, "def": 80, "spa": 70, "spd": 60, "spe": 80}, weight_kg=291.0),
    "Metagross": SpeciesData(("Steel", "Psychic"), {"hp": 80, "atk": 135, "def": 130, "spa": 95, "spd": 90, "spe": 70}, weight_kg=550.0),
    "Mienshao": SpeciesData(("Fighting",), {"hp": 65, "atk": 125, "def": 60, "spa": 95, "spd": 60, "spe": 105}, weight_kg=35.5),
    "Pelipper": SpeciesData(("Water", "Flying"), {"hp": 60, "atk": 50, "def": 100, "spa": 95, "spd": 70, "spe": 65}, weight_kg=28.0),
    "Porygon2": SpeciesData(("Normal",), {"hp": 85, "atk": 80, "def": 90, "spa": 105, "spd": 95, "spe": 60}, weight_kg=32.5),
    "Reuniclus": SpeciesData(("Psychic",), {"hp": 110, "atk": 65, "def": 75, "spa": 125, "spd": 85, "spe": 30}, weight_kg=20.1),
    "Rotom-Wash": SpeciesData(("Electric", "Water"), {"hp": 50, "atk": 65, "def": 107, "spa": 105, "spd": 107, "spe": 86}, weight_kg=0.3),
    "Scizor": SpeciesData(("Bug", "Steel"), {"hp": 70, "atk": 130, "def": 100, "spa": 55, "spd": 80, "spe": 65}, weight_kg=118.0),
    "Serperior": SpeciesData(("Grass",), {"hp": 75, "atk": 75, "def": 95, "spa": 75, "spd": 95, "spe": 113}, weight_kg=63.0),
    "Skarmory": SpeciesData(("Steel", "Flying"), {"hp": 65, "atk": 80, "def": 140, "spa": 40, "spd": 70, "spe": 70}, weight_kg=50.5),
    "Starmie": SpeciesData(("Water", "Psychic"), {"hp": 60, "atk": 75, "def": 85, "spa": 100, "spd": 85, "spe": 115}, weight_kg=80.0),
    "Staraptor": SpeciesData(("Normal", "Flying"), {"hp": 85, "atk": 120, "def": 70, "spa": 50, "spd": 60, "spe": 100}, weight_kg=24.9),
    "Suicune": SpeciesData(("Water",), {"hp": 100, "atk": 75, "def": 115, "spa": 90, "spd": 115, "spe": 85}, weight_kg=187.0),
    "Togekiss": SpeciesData(("Normal", "Flying"), {"hp": 85, "atk": 50, "def": 95, "spa": 120, "spd": 115, "spe": 80}, weight_kg=38.0),
    "Torkoal": SpeciesData(("Fire",), {"hp": 70, "atk": 85, "def": 140, "spa": 85, "spd": 70, "spe": 20}, weight_kg=80.4),
    "Tyranitar": SpeciesData(("Rock", "Dark"), {"hp":100, "atk":134, "def":110, "spa":95, "spd":100, "spe":61}, weight_kg=202.0),
    "Volcarona": SpeciesData(("Bug", "Fire"), {"hp":85, "atk":60, "def":65, "spa":135, "spd":105, "spe":100}, weight_kg=46.0),
    "Weavile": SpeciesData(("Dark", "Ice"), {"hp": 70, "atk": 120, "def": 65, "spa": 45, "spd": 85, "spe": 125}, weight_kg=34.0),
    "Weezing": SpeciesData(("Poison",), {"hp": 65, "atk": 90, "def": 120, "spa": 85, "spd": 70, "spe": 60}, weight_kg=9.5),
    "Zapdos": SpeciesData(("Electric", "Flying"), {"hp": 90, "atk": 90, "def": 85, "spa": 125, "spd": 90, "spe": 100}, weight_kg=52.6),
}

# First-pass move data for the imported OU compendium sets. Many secondary effects are
# intentionally simplified so the simulator stays usable for MCTS experiments.
MOVES = {
    # Physical attacks
    "Acrobatics": MoveData("Flying", "physical", 55, contact=True),
    "Aqua Jet": MoveData("Water", "physical", 40, priority=1, contact=True),
    "Aqua Tail": MoveData("Water", "physical", 90, accuracy=90, contact=True),
    "Bounce": MoveData("Flying", "physical", 85, accuracy=85, contact=True),
    "Brave Bird": MoveData("Flying", "physical", 120, contact=True, recoil_fraction=1/3),
    "Bug Bite": MoveData("Bug", "physical", 60, contact=True),
    "Bullet Punch": MoveData("Steel", "physical", 40, priority=1, contact=True),
    "Bullet Seed": MoveData("Grass", "physical", 25, accuracy=100, contact=False, hits=3),
    "Close Combat": MoveData("Fighting", "physical", 120, contact=True, boost_self={"def": -1, "spd": -1}),
    "Counter": MoveData("Fighting", "physical", 0, priority=-5, effect="counter"),
    "Crabhammer": MoveData("Water", "physical", 90, accuracy=90, contact=True),
    "Crunch": MoveData("Dark", "physical", 80, contact=True),
    "Double-Edge": MoveData("Normal", "physical", 120, contact=True, recoil_fraction=1/3),
    "Dragon Claw": MoveData("Dragon", "physical", 80, contact=True),
    "Dragon Rush": MoveData("Dragon", "physical", 100, accuracy=75, contact=True),
    "Dragon Tail": MoveData("Dragon", "physical", 60, accuracy=90, priority=-6, contact=True, effect="force_switch"),
    "Drain Punch": MoveData("Fighting", "physical", 75, contact=True, drain_fraction=0.5),
    "Dual Chop": MoveData("Dragon", "physical", 40, accuracy=90, contact=True, hits=2),
    "Earthquake": MoveData("Ground", "physical", 100),
    "Endeavor": MoveData("Normal", "physical", 0, contact=True, effect="endeavor"),
    "Explosion": MoveData("Normal", "physical", 250, accuracy=100, effect="self_faint"),
    "Extreme Speed": MoveData("Normal", "physical", 80, priority=2, contact=True),
    "Facade": MoveData("Normal", "physical", 70, contact=True, effect="facade"),
    "Fake Out": MoveData("Normal", "physical", 40, priority=3, contact=True),
    "Fire Fang": MoveData("Fire", "physical", 65, accuracy=95, contact=True),
    "Fire Punch": MoveData("Fire", "physical", 75, contact=True),
    "Flare Blitz": MoveData("Fire", "physical", 120, contact=True, recoil_fraction=1/3),
    "Foul Play": MoveData("Dark", "physical", 95, contact=True, effect="foul_play"),
    "Gyro Ball": MoveData("Steel", "physical", 1, contact=True, effect="gyro_ball"),
    "Hammer Arm": MoveData("Fighting", "physical", 100, accuracy=90, contact=True, boost_self={"spe": -1}),
    "Heavy Slam": MoveData("Steel", "physical", 1, contact=True, effect="heavy_slam"),
    "Ice Fang": MoveData("Ice", "physical", 65, accuracy=95, contact=True),
    "Ice Punch": MoveData("Ice", "physical", 75, contact=True),
    "Ice Shard": MoveData("Ice", "physical", 40, priority=1, contact=False),
    "Icicle Crash": MoveData("Ice", "physical", 85, accuracy=90, contact=False),
    "Icicle Spear": MoveData("Ice", "physical", 25, accuracy=100, contact=False, hits=3),
    "Iron Head": MoveData("Steel", "physical", 80, contact=True),
    "Knock Off": MoveData("Dark", "physical", 65, contact=True, effect="knock_off"),
    "Leaf Blade": MoveData("Grass", "physical", 90, contact=True),
    "Low Kick": MoveData("Fighting", "physical", 1, contact=True, effect="weight_power"),
    "Mach Punch": MoveData("Fighting", "physical", 40, priority=1, contact=True),
    "Meteor Mash": MoveData("Steel", "physical", 100, accuracy=85, contact=True),
    "Night Slash": MoveData("Dark", "physical", 70, contact=True),
    "Power Whip": MoveData("Grass", "physical", 120, accuracy=85, contact=True),
    "Psycho Cut": MoveData("Psychic", "physical", 70, contact=True),
    "Pursuit": MoveData("Dark", "physical", 40, contact=True),
    "Rapid Spin": MoveData("Normal", "physical", 20, contact=True, effect="rapid_spin"),
    "Rock Blast": MoveData("Rock", "physical", 25, accuracy=90, contact=False, hits=3),
    "Rock Slide": MoveData("Rock", "physical", 75, accuracy=90),
    "Rock Tomb": MoveData("Rock", "physical", 60, accuracy=95, boost_target={"spe": -1}),
    "Sacred Sword": MoveData("Fighting", "physical", 90, contact=True),
    "Seismic Toss": MoveData("Fighting", "physical", 0, contact=True, effect="fixed_level"),
    "Shadow Sneak": MoveData("Ghost", "physical", 40, priority=1, contact=True),
    "Smack Down": MoveData("Rock", "physical", 50),
    "Stone Edge": MoveData("Rock", "physical", 100, accuracy=80),
    "Superpower": MoveData("Fighting", "physical", 120, contact=True, boost_self={"atk": -1, "def": -1}),
    "Thief": MoveData("Dark", "physical", 60, contact=True),
    "Thunder Punch": MoveData("Electric", "physical", 75, contact=True),
    "U-turn": MoveData("Bug", "physical", 70, contact=True, effect="pivot"),
    "Waterfall": MoveData("Water", "physical", 80, contact=True),
    "Zen Headbutt": MoveData("Psychic", "physical", 80, accuracy=90, contact=True),

    # Special attacks
    "Air Slash": MoveData("Flying", "special", 75, accuracy=95),
    "Aura Sphere": MoveData("Fighting", "special", 80),
    "Bug Buzz": MoveData("Bug", "special", 90),
    "Charge Beam": MoveData("Electric", "special", 50, accuracy=90, boost_self={"spa": 1}),
    "Clear Smog": MoveData("Poison", "special", 50, effect="clear_boosts"),
    "Dark Pulse": MoveData("Dark", "special", 80),
    "Discharge": MoveData("Electric", "special", 80, ailment="par", ailment_chance=0.30),
    "Draco Meteor": MoveData("Dragon", "special", 140, accuracy=90, boost_self={"spa": -2}),
    "Dragon Pulse": MoveData("Dragon", "special", 90),
    "Earth Power": MoveData("Ground", "special", 90),
    "Energy Ball": MoveData("Grass", "special", 80),
    "Fiery Dance": MoveData("Fire", "special", 80, boost_self={"spa": 1}),
    "Fire Blast": MoveData("Fire", "special", 120, accuracy=85),
    "Flamethrower": MoveData("Fire", "special", 95),
    "Flash Cannon": MoveData("Steel", "special", 80),
    "Focus Blast": MoveData("Fighting", "special", 120, accuracy=70),
    "Future Sight": MoveData("Psychic", "special", 120),
    "Giga Drain": MoveData("Grass", "special", 75, drain_fraction=0.5),
    "Grass Knot": MoveData("Grass", "special", 1, effect="weight_power"),
    "Heat Wave": MoveData("Fire", "special", 100, accuracy=90),
    "Hidden Power Fighting": MoveData("Fighting", "special", 70),
    "Hidden Power Fire": MoveData("Fire", "special", 70),
    "Hidden Power Ice": MoveData("Ice", "special", 70),
    "Hidden Power Psychic": MoveData("Psychic", "special", 70),
    "Hidden Power Rock": MoveData("Rock", "special", 70),
    "Hurricane": MoveData("Flying", "special", 120, accuracy=70),
    "Hydro Pump": MoveData("Water", "special", 120, accuracy=80),
    "Ice Beam": MoveData("Ice", "special", 95),
    "Lava Plume": MoveData("Fire", "special", 80, ailment="brn", ailment_chance=0.30),
    "Leaf Storm": MoveData("Grass", "special", 140, accuracy=90, boost_self={"spa": -2}),
    "Night Shade": MoveData("Ghost", "special", 0, effect="fixed_level"),
    "Overheat": MoveData("Fire", "special", 140, accuracy=90, boost_self={"spa": -2}),
    "Psychic": MoveData("Psychic", "special", 90),
    "Psyshock": MoveData("Psychic", "special", 80, effect="psyshock"),
    "Psywave": MoveData("Psychic", "special", 0, accuracy=100, effect="psywave"),
    "Scald": MoveData("Water", "special", 80, ailment="brn", ailment_chance=0.30),
    "Shadow Ball": MoveData("Ghost", "special", 80),
    "Signal Beam": MoveData("Bug", "special", 75),
    "Sludge Bomb": MoveData("Poison", "special", 90, ailment="psn", ailment_chance=0.30),
    "Sludge Wave": MoveData("Poison", "special", 95, ailment="psn", ailment_chance=0.10),
    "Stored Power": MoveData("Psychic", "special", 20, effect="stored_power"),
    "Surf": MoveData("Water", "special", 95),
    "Thunderbolt": MoveData("Electric", "special", 95),
    "Tri Attack": MoveData("Normal", "special", 80),
    "Vacuum Wave": MoveData("Fighting", "special", 40, priority=1),
    "Volt Switch": MoveData("Electric", "special", 70, effect="pivot"),

    # Status moves and simplified utility effects
    "Acid Armor": MoveData("Poison", "status", boost_self={"def": 2}),
    "Agility": MoveData("Psychic", "status", boost_self={"spe": 2}),
    "Baton Pass": MoveData("Normal", "status", effect="pivot"),
    "Bulk Up": MoveData("Fighting", "status", boost_self={"atk": 1, "def": 1}),
    "Calm Mind": MoveData("Psychic", "status", boost_self={"spa": 1, "spd": 1}),
    "Defog": MoveData("Flying", "status", effect="defog"),
    "Dragon Dance": MoveData("Dragon", "status", boost_self={"atk": 1, "spe": 1}),
    "Endure": MoveData("Normal", "status", priority=4, effect="protect"),
    "Glare": MoveData("Normal", "status", accuracy=100, ailment="par"),
    "Heal Bell": MoveData("Normal", "status", effect="heal_bell"),
    "Hone Claws": MoveData("Dark", "status", boost_self={"atk": 1, "accuracy": 1}),
    "Leech Seed": MoveData("Grass", "status", accuracy=90, effect="leech_seed"),
    "Light Screen": MoveData("Psychic", "status", effect="light_screen"),
    "Nasty Plot": MoveData("Dark", "status", boost_self={"spa": 2}),
    "Pain Split": MoveData("Normal", "status", effect="pain_split"),
    "Protect": MoveData("Normal", "status", priority=4, effect="protect"),
    "Quiver Dance": MoveData("Bug", "status", boost_self={"spa": 1, "spd": 1, "spe": 1}),
    "Recover": MoveData("Normal", "status", effect="recover", heal_fraction=0.5),
    "Reflect": MoveData("Psychic", "status", effect="reflect"),
    "Rest": MoveData("Psychic", "status", effect="rest"),
    "Roar": MoveData("Normal", "status", priority=-6, effect="force_switch"),
    "Roost": MoveData("Flying", "status", effect="recover", heal_fraction=0.5),
    "Safeguard": MoveData("Normal", "status", effect="safeguard"),
    "Skill Swap": MoveData("Psychic", "status", effect="skill_swap"),
    "Sleep Talk": MoveData("Normal", "status", effect="sleep_talk"),
    "Soft-Boiled": MoveData("Normal", "status", effect="recover", heal_fraction=0.5),
    "Spikes": MoveData("Ground", "status", effect="spikes"),
    "Spore": MoveData("Grass", "status", accuracy=100, ailment="slp"),
    "Stealth Rock": MoveData("Rock", "status", effect="stealth_rock"),
    "Substitute": MoveData("Normal", "status", effect="substitute"),
    "Switcheroo": MoveData("Dark", "status", effect="trick"),
    "Swords Dance": MoveData("Normal", "status", boost_self={"atk": 2}),
    "Synthesis": MoveData("Grass", "status", effect="recover", heal_fraction=0.5),
    "Taunt": MoveData("Dark", "status", effect="taunt"),
    "Teleport": MoveData("Psychic", "status", priority=-6, effect="pivot"),
    "Thunder Wave": MoveData("Electric", "status", accuracy=90, ailment="par"),
    "Toxic": MoveData("Poison", "status", accuracy=90, ailment="tox"),
    "Toxic Spikes": MoveData("Poison", "status", effect="toxic_spikes"),
    "Trick": MoveData("Psychic", "status", effect="trick"),
    "Trick Room": MoveData("Psychic", "status", priority=-7, effect="trick_room"),
    "Whirlwind": MoveData("Normal", "status", priority=-6, effect="force_switch"),
    "Will-O-Wisp": MoveData("Fire", "status", accuracy=85, ailment="brn"),
    "Wish": MoveData("Normal", "status", effect="wish"),
}

TYPE_CHART = {t: {} for t in [
    "Normal", "Fire", "Water", "Electric", "Grass", "Ice", "Fighting", "Poison",
    "Ground", "Flying", "Psychic", "Bug", "Rock", "Ghost", "Dragon", "Dark", "Steel"
]}

def _set(attacking, strong=(), weak=(), immune=()):
    for t in strong: TYPE_CHART[attacking][t] = 2.0
    for t in weak: TYPE_CHART[attacking][t] = 0.5
    for t in immune: TYPE_CHART[attacking][t] = 0.0

_set("Normal", weak=("Rock", "Steel"), immune=("Ghost",))
_set("Fire", strong=("Grass", "Ice", "Bug", "Steel"), weak=("Fire", "Water", "Rock", "Dragon"))
_set("Water", strong=("Fire", "Ground", "Rock"), weak=("Water", "Grass", "Dragon"))
_set("Electric", strong=("Water", "Flying"), weak=("Electric", "Grass", "Dragon"), immune=("Ground",))
_set("Grass", strong=("Water", "Ground", "Rock"), weak=("Fire", "Grass", "Poison", "Flying", "Bug", "Dragon", "Steel"))
_set("Ice", strong=("Grass", "Ground", "Flying", "Dragon"), weak=("Fire", "Water", "Ice", "Steel"))
_set("Fighting", strong=("Normal", "Ice", "Rock", "Dark", "Steel"), weak=("Poison", "Flying", "Psychic", "Bug"), immune=("Ghost",))
_set("Poison", strong=("Grass",), weak=("Poison", "Ground", "Rock", "Ghost"), immune=("Steel",))
_set("Ground", strong=("Fire", "Electric", "Poison", "Rock", "Steel"), weak=("Grass", "Bug"), immune=("Flying",))
_set("Flying", strong=("Grass", "Fighting", "Bug"), weak=("Electric", "Rock", "Steel"))
_set("Psychic", strong=("Fighting", "Poison"), weak=("Psychic", "Steel"), immune=("Dark",))
_set("Bug", strong=("Grass", "Psychic", "Dark"), weak=("Fire", "Fighting", "Poison", "Flying", "Ghost", "Steel"))
_set("Rock", strong=("Fire", "Ice", "Flying", "Bug"), weak=("Fighting", "Ground", "Steel"))
_set("Ghost", strong=("Psychic", "Ghost"), weak=("Dark", "Steel"), immune=("Normal",))
_set("Dragon", strong=("Dragon",), weak=("Steel",))
_set("Dark", strong=("Psychic", "Ghost"), weak=("Fighting", "Dark", "Steel"))
_set("Steel", strong=("Ice", "Rock"), weak=("Fire", "Water", "Electric", "Steel"))


def effectiveness(move_type: str, defender_types: tuple[str, ...], defender_ability: str = "") -> float:
    if defender_ability == "Levitate" and move_type == "Ground":
        return 0.0
    mult = 1.0
    for t in defender_types:
        mult *= TYPE_CHART.get(move_type, {}).get(t, 1.0)
    return mult
