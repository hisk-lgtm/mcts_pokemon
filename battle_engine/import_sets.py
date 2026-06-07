from __future__ import annotations

from dataclasses import dataclass
import itertools
import re
from typing import Iterable

from .model import PokemonSet
from .sample_sets import IV31

STAT_ALIASES = {
    "HP": "hp",
    "Atk": "atk",
    "Attack": "atk",
    "Def": "def",
    "Defense": "def",
    "SpA": "spa",
    "SpAtk": "spa",
    "SpAttack": "spa",
    "SpD": "spd",
    "SpDef": "spd",
    "SDef": "spd",
    "SpDefense": "spd",
    "Spe": "spe",
    "Speed": "spe",
}

HP_TYPE_ALIASES = {
    "Fight": "Fighting",
    "Fighting": "Fighting",
    "Fire": "Fire",
    "Water": "Water",
    "Electric": "Electric",
    "Grass": "Grass",
    "Ice": "Ice",
    "Poison": "Poison",
    "Ground": "Ground",
    "Flying": "Flying",
    "Psychic": "Psychic",
    "Bug": "Bug",
    "Rock": "Rock",
    "Ghost": "Ghost",
    "Dragon": "Dragon",
    "Dark": "Dark",
    "Steel": "Steel",
}

MOVE_ALIASES = {
    # Common typo / spacing variants seen in copied compendium text.
    "Energyball": "Energy Ball",
    "Shadow Snake": "Shadow Sneak",
    "ExtremeSpeed": "Extreme Speed",
}


@dataclass(frozen=True)
class ParsedSetOptions:
    species: str
    item_options: list[str]
    ability_options: list[str]
    ev_options: list[dict[str, int]]
    nature_options: list[str]
    move_slot_options: list[list[str]]
    level: int = 50

    def variant_count(self) -> int:
        total = (
            max(1, len(self.item_options))
            * max(1, len(self.ability_options))
            * max(1, len(self.ev_options))
            * max(1, len(self.nature_options))
        )
        for slot in self.move_slot_options:
            total *= max(1, len(slot))
        return total


def _clean_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def _split_slash_options(value: str) -> list[str]:
    return [_clean_spaces(part) for part in re.split(r"\s*/\s*", value) if part.strip()]


def _first_or_blank(options: list[str]) -> str:
    return options[0] if options else ""


def _canonical_hp_type(value: str) -> str | None:
    clean = _clean_spaces(value)
    match = re.fullmatch(r"Hidden Power\s+\[?([A-Za-z]+)\]?", clean)
    if match:
        clean = match.group(1)
    return HP_TYPE_ALIASES.get(clean)


def normalize_move_name(move_name: str) -> str:
    move_name = _clean_spaces(move_name)
    hp_type = _canonical_hp_type(move_name)
    if hp_type:
        return f"Hidden Power {hp_type}"
    return MOVE_ALIASES.get(move_name, move_name)


def split_move_options(move_text: str) -> list[str]:
    """Split one move slot into legal alternatives.

    Handles compendium shorthand like:
    - Hidden Power Ice / Fight
    as:
    - Hidden Power Ice
    - Hidden Power Fighting

    It does not try to validate whether the engine has implemented the move.
    """
    parts = _split_slash_options(move_text)
    if not parts:
        return []

    first_is_hidden_power = _canonical_hp_type(parts[0]) is not None
    expanded: list[str] = []
    for i, part in enumerate(parts):
        if i > 0 and first_is_hidden_power:
            hp_type = _canonical_hp_type(part)
            if hp_type:
                part = f"Hidden Power {hp_type}"
        expanded.append(normalize_move_name(part))
    return expanded


def parse_ev_spread(spread_text: str) -> dict[str, int]:
    evs = {"hp": 0, "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0}
    for part in spread_text.split("/"):
        part = part.strip()
        if not part:
            continue
        match = re.search(r"(\d+)\s+([A-Za-z.]+)", part)
        if not match:
            raise ValueError(f"Could not parse EV component: {part!r}")
        value = int(match.group(1))
        stat_text = match.group(2).replace(".", "")
        try:
            stat = STAT_ALIASES[stat_text]
        except KeyError as exc:
            raise ValueError(f"Unknown EV stat: {stat_text!r}") from exc
        evs[stat] = value
    return evs


def parse_ev_options(line: str) -> list[dict[str, int]]:
    body = line.split(":", 1)[1] if ":" in line else line
    spreads = [part.strip() for part in re.split(r"\s+or\s+", body, flags=re.IGNORECASE) if part.strip()]
    return [parse_ev_spread(spread) for spread in spreads]


def parse_evs(line: str) -> dict[str, int]:
    """Backward-compatible helper: return the first EV spread only."""
    return parse_ev_options(line)[0]


def parse_nature_options(line: str) -> list[str]:
    body = re.sub(r"\s+Nature\s*$", "", line.strip(), flags=re.IGNORECASE)
    return _split_slash_options(body)


def parse_showdown_set_options(text: str) -> ParsedSetOptions:
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    if not lines:
        raise ValueError("Cannot parse an empty set block.")

    header = lines[0]
    match = re.match(r"(.+?)(?:\s*@\s*(.+))?$", header)
    if not match:
        raise ValueError(f"Could not parse set header: {header!r}")

    species = _clean_spaces(match.group(1))
    item_options = _split_slash_options(match.group(2) or "")

    ability_options: list[str] = []
    nature_options: list[str] = ["Hardy"]
    ev_options: list[dict[str, int]] = [{"hp": 0, "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0}]
    move_slot_options: list[list[str]] = []
    level = 50

    for line in lines[1:]:
        if line.startswith("Ability:"):
            ability_options = _split_slash_options(line.split(":", 1)[1])
        elif line.startswith("Level:"):
            level = int(line.split(":", 1)[1].strip())
        elif line.startswith("EVs:"):
            ev_options = parse_ev_options(line)
        elif re.search(r"\s+Nature\s*$", line, flags=re.IGNORECASE):
            nature_options = parse_nature_options(line)
        elif line.startswith("-"):
            move_slot_options.append(split_move_options(line[1:].strip()))

    return ParsedSetOptions(
        species=species,
        item_options=item_options,
        ability_options=ability_options,
        ev_options=ev_options,
        nature_options=nature_options,
        move_slot_options=move_slot_options,
        level=level,
    )


def iter_showdown_set_variants(
    text: str,
    *,
    max_variants: int | None = 2048,
) -> Iterable[PokemonSet]:
    options = parse_showdown_set_options(text)
    total = options.variant_count()
    if max_variants is not None and total > max_variants:
        raise ValueError(
            f"{options.species} expands to {total} variants, above max_variants={max_variants}. "
            "Raise the limit if this is intentional."
        )

    item_options = options.item_options or [""]
    ability_options = options.ability_options or [""]
    ev_options = options.ev_options or [{"hp": 0, "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0}]
    nature_options = options.nature_options or ["Hardy"]
    move_products = itertools.product(*options.move_slot_options) if options.move_slot_options else [()]

    for item, ability, evs, nature, moves in itertools.product(
        item_options,
        ability_options,
        ev_options,
        nature_options,
        move_products,
    ):
        yield PokemonSet(
            species=options.species,
            item=item,
            ability=ability,
            nature=nature,
            evs=dict(evs),
            ivs=dict(IV31),
            moves=list(moves),
            level=options.level,
        )


def parse_showdown_set_variants(
    text: str,
    *,
    max_variants: int | None = 2048,
) -> list[PokemonSet]:
    return list(iter_showdown_set_variants(text, max_variants=max_variants))


def parse_showdown_set(text: str) -> PokemonSet:
    """Backward-compatible parser: return the first concrete option only.

    Example:
    Gyarados @ Leftovers / Lum Berry
    Jolly / Adamant Nature
    - Ice Fang / Bounce

    returns Leftovers, Jolly, and Ice Fang.
    """
    return next(iter_showdown_set_variants(text, max_variants=None))


def split_showdown_blocks(text: str) -> list[str]:
    """Split a file containing many Showdown-style sets separated by blank lines."""
    blocks = []
    current = []
    for line in text.splitlines():
        if line.strip():
            current.append(line)
        elif current:
            blocks.append("\n".join(current))
            current = []
    if current:
        blocks.append("\n".join(current))
    return blocks


def parse_showdown_sets_text(
    text: str,
    *,
    expand_variants: bool = False,
    max_variants_per_set: int | None = 2048,
) -> list[PokemonSet]:
    sets: list[PokemonSet] = []
    for block in split_showdown_blocks(text):
        if expand_variants:
            sets.extend(parse_showdown_set_variants(block, max_variants=max_variants_per_set))
        else:
            sets.append(parse_showdown_set(block))
    return sets


def parse_showdown_sets_file(
    path: str,
    *,
    expand_variants: bool = False,
    max_variants_per_set: int | None = 2048,
) -> list[PokemonSet]:
    with open(path, "r", encoding="utf-8") as f:
        return parse_showdown_sets_text(
            f.read(),
            expand_variants=expand_variants,
            max_variants_per_set=max_variants_per_set,
        )
