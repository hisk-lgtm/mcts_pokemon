from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Literal
import copy

Status = Optional[Literal["brn", "psn", "tox", "par", "slp", "frz"]]
Weather = Optional[Literal["sand", "rain", "sun", "hail"]]


@dataclass(frozen=True)
class PokemonSet:
    species: str
    item: str
    ability: str
    nature: str
    evs: Dict[str, int]
    ivs: Dict[str, int]
    moves: List[str]
    level: int = 50


@dataclass
class PokemonState:
    set: PokemonSet
    stats: Dict[str, int]
    hp: int
    held_item: Optional[str] = None
    active_ability: Optional[str] = None
    status: Status = None
    toxic_counter: int = 0
    sleep_counter: int = 0
    sleep_duration: int = 0
    boosts: Dict[str, int] = field(default_factory=lambda: {
        "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0,
        "accuracy": 0, "evasion": 0,
    })
    fainted: bool = False
    item_removed: bool = False
    protected: bool = False
    choice_locked_move: Optional[str] = None
    substitute_hp: int = 0
    taunt_turns: int = 0
    leech_seeded_by: Optional[int] = None
    last_damage_taken: int = 0
    last_damage_category: Optional[str] = None
    last_damage_source_player: Optional[int] = None
    flash_fire_active: bool = False
    disabled_move: Optional[str] = None
    disabled_turns: int = 0

    @property
    def max_hp(self) -> int:
        return self.stats["hp"]

    @property
    def item(self) -> str:
        if self.item_removed:
            return ""
        return self.held_item if self.held_item is not None else self.set.item

    @item.setter
    def item(self, value: str) -> None:
        self.held_item = value
        self.item_removed = not bool(value)

    @property
    def species(self) -> str:
        return self.set.species

    @property
    def ability(self) -> str:
        return self.active_ability if self.active_ability is not None else self.set.ability

    @ability.setter
    def ability(self, value: str) -> None:
        self.active_ability = value

    @property
    def moves(self) -> List[str]:
        return self.set.moves


@dataclass
class SideConditions:
    stealth_rock: bool = False
    spikes: int = 0
    toxic_spikes: int = 0
    reflect_turns: int = 0
    light_screen_turns: int = 0
    safeguard_turns: int = 0


@dataclass
class TeamState:
    mons: List[PokemonState]
    active: int = 0
    side: SideConditions = field(default_factory=SideConditions)

    def active_mon(self) -> PokemonState:
        return self.mons[self.active]

    def has_healthy_bench(self) -> bool:
        return any(i != self.active and not m.fainted and m.hp > 0 for i, m in enumerate(self.mons))

    def first_healthy_bench(self) -> Optional[int]:
        for i, m in enumerate(self.mons):
            if i != self.active and not m.fainted and m.hp > 0:
                return i
        return None

    def alive_count(self) -> int:
        return sum(not m.fainted and m.hp > 0 for m in self.mons)


@dataclass
class FieldState:
    weather: Weather = None
    weather_turns: int = 0
    trick_room_turns: int = 0
    turn: int = 1


@dataclass(frozen=True)
class Action:
    kind: Literal["move", "switch"]
    index: int


@dataclass
class BattleState:
    p1: TeamState
    p2: TeamState
    field: FieldState = field(default_factory=FieldState)
    rng_seed: int = 1
    winner: Optional[int] = None

    def clone(self) -> "BattleState":
        return copy.deepcopy(self)


@dataclass
class TurnLog:
    lines: List[str] = field(default_factory=list)
    debug_enabled: bool = False
    debug_lines: List[str] = field(default_factory=list)

    def add(self, text: str) -> None:
        self.lines.append(text)

    def debug(self, text: str) -> None:
        if self.debug_enabled:
            self.debug_lines.append(text)

    def extend(self, lines: List[str]) -> None:
        self.lines.extend(lines)

    def all_lines(self) -> List[str]:
        if not self.debug_lines:
            return list(self.lines)
        return list(self.lines) + ["-- debug --"] + list(self.debug_lines)

    def __str__(self) -> str:
        return "\n".join(self.all_lines())


@dataclass(frozen=True)
class SpeciesData:
    types: tuple[str, ...]
    base_stats: Dict[str, int]
    weight_kg: float


@dataclass(frozen=True)
class MoveData:
    type: str
    category: Literal["physical", "special", "status"]
    power: int = 0
    accuracy: int = 100
    priority: int = 0
    contact: bool = False
    effect: Optional[str] = None
    ailment: Optional[str] = None
    ailment_chance: float = 0.0
    boost_self: Optional[Dict[str, int]] = None
    boost_target: Optional[Dict[str, int]] = None
    heal_fraction: float = 0.0
    drain_fraction: float = 0.0
    recoil_fraction: float = 0.0
    hits: int = 1


def make_pokemon(pokeset: PokemonSet) -> PokemonState:
    from .data import SPECIES, NATURES

    species = SPECIES[pokeset.species]
    stats = {}
    level = pokeset.level
    ivs = {s: pokeset.ivs.get(s, 31) for s in ["hp", "atk", "def", "spa", "spd", "spe"]}
    evs = {s: pokeset.evs.get(s, 0) for s in ["hp", "atk", "def", "spa", "spd", "spe"]}

    base_hp = species.base_stats["hp"]
    stats["hp"] = ((2 * base_hp + ivs["hp"] + evs["hp"] // 4) * level) // 100 + level + 10

    nature_mods = NATURES.get(pokeset.nature, {})
    for stat in ["atk", "def", "spa", "spd", "spe"]:
        raw = ((2 * species.base_stats[stat] + ivs[stat] + evs[stat] // 4) * level) // 100 + 5
        mod = nature_mods.get(stat, 1.0)
        stats[stat] = int(raw * mod)

    return PokemonState(set=pokeset, stats=stats, hp=stats["hp"], held_item=pokeset.item, active_ability=pokeset.ability)


def make_battle(team1: List[PokemonSet], team2: List[PokemonSet], seed: int = 1) -> BattleState:
    state = BattleState(
        p1=TeamState([make_pokemon(s) for s in team1]),
        p2=TeamState([make_pokemon(s) for s in team2]),
        rng_seed=seed,
    )
    from .engine import apply_on_switch_in
    log = TurnLog()
    apply_on_switch_in(state, 1, log)
    apply_on_switch_in(state, 2, log)
    return state
