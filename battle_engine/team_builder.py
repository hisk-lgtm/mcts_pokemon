from __future__ import annotations

from pathlib import Path
import random
from typing import Iterable

from .data import MOVES, SPECIES
from .import_sets import parse_showdown_sets_file
from .model import PokemonSet


def is_supported_set(pokeset: PokemonSet) -> bool:
    return pokeset.species in SPECIES and all(move in MOVES for move in pokeset.moves)


def unsupported_reasons(pokeset: PokemonSet) -> list[str]:
    reasons: list[str] = []
    if pokeset.species not in SPECIES:
        reasons.append(f"missing species: {pokeset.species}")
    missing_moves = [move for move in pokeset.moves if move not in MOVES]
    if missing_moves:
        reasons.append(f"missing moves: {', '.join(missing_moves)}")
    return reasons


def load_set_pool(
    path: str | Path,
    *,
    expand_variants: bool = True,
    supported_only: bool = True,
) -> list[PokemonSet]:
    sets = parse_showdown_sets_file(
        str(path),
        expand_variants=expand_variants,
        max_variants_per_set=2048,
    )
    if supported_only:
        sets = [s for s in sets if is_supported_set(s)]
    return sets


def random_team(
    pool: Iterable[PokemonSet],
    *,
    rng: random.Random | None = None,
    size: int = 6,
    unique_species: bool = True,
) -> list[PokemonSet]:
    rng = rng or random.Random()
    candidates = list(pool)
    rng.shuffle(candidates)

    team: list[PokemonSet] = []
    used_species: set[str] = set()
    for pokeset in candidates:
        if unique_species and pokeset.species in used_species:
            continue
        team.append(pokeset)
        used_species.add(pokeset.species)
        if len(team) == size:
            return team

    raise ValueError(f"Could not build a team of {size} from {len(candidates)} candidate sets.")


def default_compendium_path() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "ou_sets_to_import_variants.txt"


def generate_team_candidates(
    pool: Iterable[PokemonSet],
    *,
    rng: random.Random | None = None,
    candidate_count: int = 32,
    size: int = 6,
    unique_species: bool = True,
) -> list[list[PokemonSet]]:
    rng = rng or random.Random()
    candidates: list[list[PokemonSet]] = []
    pool_list = list(pool)
    seen: set[tuple[str, ...]] = set()

    attempts = 0
    max_attempts = max(candidate_count * 20, 100)
    while len(candidates) < candidate_count and attempts < max_attempts:
        attempts += 1
        try:
            team = random_team(pool_list, rng=rng, size=size, unique_species=unique_species)
        except ValueError:
            break

        signature = tuple(sorted(p.species for p in team))
        if signature in seen:
            continue
        seen.add(signature)
        candidates.append(team)

    if not candidates:
        raise ValueError("Could not generate any team candidates.")
    return candidates
