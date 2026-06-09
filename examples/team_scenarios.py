from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Literal

from battle_engine.model import PokemonSet
from battle_engine.sample_sets import TEAM_BALANCE_A, TEAM_BALANCE_B, TYRANITAR_CB, DRAGONITE_DD
from battle_engine.team_builder import default_compendium_path, load_set_pool, random_team

TeamMode = Literal["single", "balance", "random", "mirror", "round-robin"]
TEAM_MODE_CHOICES: tuple[str, ...] = ("single", "balance", "random", "mirror", "round-robin")


@dataclass(frozen=True)
class GameTeams:
    team1: list[PokemonSet]
    team2: list[PokemonSet]
    mode: str
    matchup_id: str
    team1_id: str
    team2_id: str

    def metadata(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "matchup_id": self.matchup_id,
            "team1_id": self.team1_id,
            "team2_id": self.team2_id,
            "team1_species": team_species(self.team1),
            "team2_species": team_species(self.team2),
        }


def team_species(team: list[PokemonSet]) -> list[str]:
    return [mon.species for mon in team]


def _copy_team(team: list[PokemonSet]) -> list[PokemonSet]:
    return list(team)


def _single_tyranitar_vs_dragonite() -> GameTeams:
    return GameTeams(
        team1=[TYRANITAR_CB],
        team2=[DRAGONITE_DD],
        mode="single",
        matchup_id="single_tyranitar_vs_dragonite",
        team1_id="tyranitar_cb",
        team2_id="dragonite_dd",
    )


def _balance_a_vs_b() -> GameTeams:
    return GameTeams(
        team1=_copy_team(TEAM_BALANCE_A),
        team2=_copy_team(TEAM_BALANCE_B),
        mode="balance",
        matchup_id="balance_a_vs_b",
        team1_id="balance_a",
        team2_id="balance_b",
    )


def _balance_b_vs_a() -> GameTeams:
    return GameTeams(
        team1=_copy_team(TEAM_BALANCE_B),
        team2=_copy_team(TEAM_BALANCE_A),
        mode="balance",
        matchup_id="balance_b_vs_a",
        team1_id="balance_b",
        team2_id="balance_a",
    )


def _mirror_balance_a() -> GameTeams:
    return GameTeams(
        team1=_copy_team(TEAM_BALANCE_A),
        team2=_copy_team(TEAM_BALANCE_A),
        mode="mirror",
        matchup_id="mirror_balance_a",
        team1_id="balance_a",
        team2_id="balance_a",
    )


def _mirror_balance_b() -> GameTeams:
    return GameTeams(
        team1=_copy_team(TEAM_BALANCE_B),
        team2=_copy_team(TEAM_BALANCE_B),
        mode="mirror",
        matchup_id="mirror_balance_b",
        team1_id="balance_b",
        team2_id="balance_b",
    )


ROUND_ROBIN_SCENARIOS = (
    _single_tyranitar_vs_dragonite,
    _balance_a_vs_b,
    _balance_b_vs_a,
    _mirror_balance_a,
    _mirror_balance_b,
)


def _random_pair(rng: random.Random) -> GameTeams:
    pool = load_set_pool(default_compendium_path(), expand_variants=True, supported_only=True)
    team1 = random_team(pool, rng=rng)
    team2 = random_team(pool, rng=rng)
    return GameTeams(
        team1=team1,
        team2=team2,
        mode="random",
        matchup_id="random_pair",
        team1_id="random_team_1",
        team2_id="random_team_2",
    )


def build_teams(mode: str, rng: random.Random, *, game_id: int = 0) -> GameTeams:
    """Build a named matchup for backend self-play/evaluation.

    `single`, `balance`, and `random` preserve the older CLI behavior. `mirror`
    and `round-robin` add cheap matchup diversity without requiring an external
    team database yet.
    """
    if mode == "single":
        return _single_tyranitar_vs_dragonite()
    if mode == "balance":
        return _balance_a_vs_b()
    if mode == "random":
        return _random_pair(rng)
    if mode == "mirror":
        return rng.choice((_mirror_balance_a, _mirror_balance_b))()
    if mode == "round-robin":
        return ROUND_ROBIN_SCENARIOS[game_id % len(ROUND_ROBIN_SCENARIOS)]()
    raise ValueError(f"Unknown team mode: {mode!r}. Choices: {', '.join(TEAM_MODE_CHOICES)}")
