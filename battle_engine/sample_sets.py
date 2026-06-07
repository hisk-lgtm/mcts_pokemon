from __future__ import annotations

from .model import PokemonSet

def evs(**kwargs):
    base = {"hp": 0, "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0}
    base.update(kwargs)
    return base

IV31 = {"hp": 31, "atk": 31, "def": 31, "spa": 31, "spd": 31, "spe": 31}

TYRANITAR_CB = PokemonSet(
    species="Tyranitar",
    item="Choice Band",
    ability="Sand Stream",
    nature="Adamant",
    evs=evs(hp=4, atk=252, spe=252),
    ivs=IV31,
    moves=["Crunch", "Stone Edge", "Superpower", "Earthquake"],
)

SCIZOR_CB = PokemonSet(
    species="Scizor",
    item="Choice Band",
    ability="Technician",
    nature="Adamant",
    evs=evs(hp=248, atk=252, spd=8),
    ivs=IV31,
    moves=["Bullet Punch", "U-turn", "Superpower", "Bug Bite"],
)

GARCHOMP_SD = PokemonSet(
    species="Garchomp",
    item="Life Orb",
    ability="Rough Skin",
    nature="Jolly",
    evs=evs(atk=252, spe=252, hp=4),
    ivs=IV31,
    moves=["Swords Dance", "Earthquake", "Dragon Claw", "Fire Punch"],
)

ROTOM_W_DEF = PokemonSet(
    species="Rotom-Wash",
    item="Leftovers",
    ability="Levitate",
    nature="Bold",
    evs=evs(hp=252, spe=4, **{"def": 252}),
    ivs=IV31,
    moves=["Hydro Pump", "Volt Switch", "Will-O-Wisp", "Thunderbolt"],
)

STARMIE_OFF = PokemonSet(
    species="Starmie",
    item="Life Orb",
    ability="Natural Cure",
    nature="Timid",
    evs=evs(spa=252, spe=252, hp=4),
    ivs=IV31,
    moves=["Hydro Pump", "Ice Beam", "Thunderbolt", "Rapid Spin"],
)

FERROTHORN_UTIL = PokemonSet(
    species="Ferrothorn",
    item="Leftovers",
    ability="Iron Barbs",
    nature="Relaxed",
    evs=evs(hp=252, spd=168, **{"def": 88}),
    ivs=IV31,
    moves=["Spikes", "Stealth Rock", "Giga Drain", "Thunder Wave"],
)

DRAGONITE_DD = PokemonSet(
    species="Dragonite",
    item="Lum Berry",
    ability="Multiscale",
    nature="Adamant",
    evs=evs(atk=252, spe=252, hp=4),
    ivs=IV31,
    moves=["Dragon Dance", "Dragon Claw", "Fire Punch", "Extreme Speed"],
)

CONKELDURR_GUTS = PokemonSet(
    species="Conkeldurr",
    item="Leftovers",
    ability="Guts",
    nature="Adamant",
    evs=evs(hp=120, atk=252, spd=136),
    ivs=IV31,
    moves=["Drain Punch", "Mach Punch", "Facade", "Thunder Punch"],
)

TEAM_BALANCE_A = [TYRANITAR_CB, SCIZOR_CB, GARCHOMP_SD, ROTOM_W_DEF, STARMIE_OFF, FERROTHORN_UTIL]
TEAM_BALANCE_B = [DRAGONITE_DD, CONKELDURR_GUTS, ROTOM_W_DEF, SCIZOR_CB, FERROTHORN_UTIL, STARMIE_OFF]
