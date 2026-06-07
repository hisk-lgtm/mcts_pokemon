from __future__ import annotations

from dataclasses import dataclass, field
import json
import random
from pathlib import Path

from .engine import evaluate_material, legal_actions, needs_replacement, replace_fainted, step
from .features import action_label, state_summary
from .log_formatter import append_human_event
from .mcts import MCTSAgent, MCTSConfig
from .ml_agent import LinearPolicyValueAgent
from .model import BattleState, PokemonSet, make_battle
from .team_builder import default_compendium_path, generate_team_candidates, load_set_pool, random_team
from .team_roles import short_team_label, team_summary


@dataclass
class TrainingConfig:
    generations: int = 3
    games_per_generation: int = 4
    max_turns: int = 80
    mcts_simulations: int = 32
    mcts_depth: int = 20
    seed: int = 1

    agent_count: int = 4
    swiss_rounds: int = 3
    games_per_pairing: int = 1
    elite_count: int = 1
    mutation_scale: float = 0.01

    elo_initial: float = 1000.0
    elo_k_factor: float = 32.0

    team_candidate_count: int = 32
    team_temperature: float = 0.15

    verbose: bool = False
    progress: bool = False
    progress_turns: bool = False
    progress_every: int = 1
    progress_mcts: bool = False
    debug_turns: bool = False
    debug_teams: bool = False
    debug_mcts_top_n: int = 3

    log_path: str = "training_logs/generational_training.jsonl"
    human_log_path: str | None = "training_logs/generational_training.log"
    human_log_top_n: int = 5
    model_path: str = "training_logs/latest_agent.json"
    population_path: str = "training_logs/latest_population.json"


@dataclass
class AgentStanding:
    agent_id: int
    name: str
    points: float = 0.0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    byes: int = 0
    games: int = 0
    turns: int = 0
    elo_start: float = 1000.0
    elo: float = 1000.0
    elo_peak: float = 1000.0
    opponents: set[int] = field(default_factory=set)

    def as_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "points": self.points,
            "wins": self.wins,
            "losses": self.losses,
            "draws": self.draws,
            "byes": self.byes,
            "games": self.games,
            "avg_turns": self.turns / self.games if self.games else 0.0,
            "elo_start": round(self.elo_start, 2),
            "elo": round(self.elo, 2),
            "elo_delta": round(self.elo - self.elo_start, 2),
            "elo_peak": round(self.elo_peak, 2),
            "opponents": sorted(self.opponents),
        }


def _winner_value(state: BattleState, player: int) -> float:
    if state.winner == player:
        return 1.0
    if state.winner == 0:
        return 0.0
    if state.winner is None:
        return evaluate_material(state, player)
    return -1.0


def _elo_expected(own_elo: float, opponent_elo: float) -> float:
    return 1.0 / (1.0 + 10 ** ((opponent_elo - own_elo) / 400.0))


def _elo_score_for_result(winner: int | None, player: int) -> float:
    if winner == player:
        return 1.0
    if winner in (None, 0):
        return 0.5
    return 0.0


def _apply_elo_update(
    p1_elo: float,
    p2_elo: float,
    winner: int | None,
    *,
    k_factor: float,
) -> tuple[float, float, dict]:
    p1_score = _elo_score_for_result(winner, 1)
    p2_score = 1.0 - p1_score
    p1_expected = _elo_expected(p1_elo, p2_elo)
    p2_expected = _elo_expected(p2_elo, p1_elo)

    new_p1 = p1_elo + k_factor * (p1_score - p1_expected)
    new_p2 = p2_elo + k_factor * (p2_score - p2_expected)
    return new_p1, new_p2, {
        "p1_old_elo": round(p1_elo, 2),
        "p2_old_elo": round(p2_elo, 2),
        "p1_expected": round(p1_expected, 4),
        "p2_expected": round(p2_expected, 4),
        "p1_score": p1_score,
        "p2_score": p2_score,
        "p1_new_elo": round(new_p1, 2),
        "p2_new_elo": round(new_p2, 2),
        "p1_elo_delta": round(new_p1 - p1_elo, 2),
        "p2_elo_delta": round(new_p2 - p2_elo, 2),
        "k_factor": k_factor,
    }


def _emit_event(log_file, human_log_file, config: TrainingConfig, event: dict) -> None:
    log_file.write(json.dumps(event) + "\n")
    if human_log_file is not None:
        append_human_event(human_log_file, event, top_n=config.human_log_top_n)


def _debug(config: TrainingConfig, message: str) -> None:
    if config.verbose:
        print(message, flush=True)


def _progress(config: TrainingConfig, message: str) -> None:
    if config.progress or config.verbose:
        print(message, flush=True)


def _progress_turn(config: TrainingConfig, turn_number: int, message: str) -> None:
    if not config.progress_turns:
        return
    interval = max(1, config.progress_every)
    if turn_number == 1 or turn_number % interval == 0:
        print(message, flush=True)


def _standing_line(row: dict) -> str:
    return (
        f"#{row['agent_id']} {row['name']} | "
        f"{row['points']} pts | Elo {row.get('elo', '?')} ({row.get('elo_delta', 0):+}) | "
        f"W-L-D {row['wins']}-{row['losses']}-{row['draws']} | byes={row['byes']}"
    )


def _compact_team_roles(summary: dict) -> str:
    role_counts = summary.get("role_counts", {})
    active_roles = [f"{role}={count}" for role, count in sorted(role_counts.items()) if count]
    return ", ".join(active_roles) if active_roles else "no inferred core roles"



def _make_mcts(agent: LinearPolicyValueAgent, config: TrainingConfig, rng: random.Random) -> MCTSAgent:
    return MCTSAgent(
        MCTSConfig(
            simulations=config.mcts_simulations,
            max_depth=config.mcts_depth,
            exploration=1.25,
        ),
        policy_prior=agent.action_priors,
        value_fn=agent.evaluate,
        rng=rng,
    )


def _choose_team(
    pool: list[PokemonSet],
    agent: LinearPolicyValueAgent,
    config: TrainingConfig,
    rng: random.Random,
) -> tuple[list[PokemonSet], float, list[list[PokemonSet]]]:
    candidates = generate_team_candidates(
        pool,
        rng=rng,
        candidate_count=config.team_candidate_count,
        size=6,
        unique_species=True,
    )
    team = agent.choose_team(candidates, temperature=config.team_temperature, rng=rng)
    return team, agent.score_team(team), candidates


def _handle_replacement_with_agent(
    state: BattleState,
    player: int,
    agent: LinearPolicyValueAgent,
    rng: random.Random,
) -> BattleState:
    while state.winner is None and needs_replacement(state, player):
        actions = legal_actions(state, player)
        switches = [a for a in actions if a.kind == "switch"]
        if not switches:
            break
        action = agent.choose_action(state, player, switches, temperature=0.2, rng=rng)
        state, _ = replace_fainted(state, player, action.index)
    return state


def _format_root_preview(mcts_dict: dict, *, top_n: int) -> str:
    stats = mcts_dict.get("stats", [])[:top_n]
    if not stats:
        return "no MCTS stats"
    return "; ".join(
        f"{s.get('label', '?')} v={s.get('visits', 0)} q={s.get('mean_value', 0.0)}"
        for s in stats
    )


def _team_preview_event(
    *,
    game_id: str,
    generation: int | None,
    swiss_round: int | None,
    p1_agent: LinearPolicyValueAgent,
    p2_agent: LinearPolicyValueAgent,
    p1_agent_id: int | None,
    p2_agent_id: int | None,
    team1: list[PokemonSet],
    team2: list[PokemonSet],
    p1_team_score: float,
    p2_team_score: float,
    candidate_count: int,
) -> dict:
    return {
        "type": "team_preview",
        "game_id": game_id,
        "generation": generation,
        "swiss_round": swiss_round,
        "p1_agent_id": p1_agent_id,
        "p2_agent_id": p2_agent_id,
        "p1_agent_name": p1_agent.name,
        "p2_agent_name": p2_agent.name,
        "p1_team": team_summary(team1),
        "p2_team": team_summary(team2),
        "p1_team_label": short_team_label(team1),
        "p2_team_label": short_team_label(team2),
        "p1_team_score": p1_team_score,
        "p2_team_score": p2_team_score,
        "candidate_count": candidate_count,
    }


def play_training_game_between_agents(
    p1_agent: LinearPolicyValueAgent,
    p2_agent: LinearPolicyValueAgent,
    team1: list[PokemonSet],
    team2: list[PokemonSet],
    *,
    config: TrainingConfig,
    rng: random.Random,
    game_id: str,
    log_file,
    human_log_file=None,
    p1_agent_id: int | None = None,
    p2_agent_id: int | None = None,
    generation: int | None = None,
    swiss_round: int | None = None,
    p1_team_score: float = 0.0,
    p2_team_score: float = 0.0,
) -> dict:
    preview = _team_preview_event(
        game_id=game_id,
        generation=generation,
        swiss_round=swiss_round,
        p1_agent=p1_agent,
        p2_agent=p2_agent,
        p1_agent_id=p1_agent_id,
        p2_agent_id=p2_agent_id,
        team1=team1,
        team2=team2,
        p1_team_score=p1_team_score,
        p2_team_score=p2_team_score,
        candidate_count=config.team_candidate_count,
    )
    _emit_event(log_file, human_log_file, config, preview)

    if config.progress:
        print(f"[team {game_id}] P1 agent {p1_agent_id} score={p1_team_score:.3f}: {preview['p1_team_label']}", flush=True)
        print(f"[team {game_id}] P1 roles: {_compact_team_roles(preview['p1_team'])}", flush=True)
        print(f"[team {game_id}] P2 agent {p2_agent_id} score={p2_team_score:.3f}: {preview['p2_team_label']}", flush=True)
        print(f"[team {game_id}] P2 roles: {_compact_team_roles(preview['p2_team'])}", flush=True)

    if config.debug_teams:
        print(f"[game {game_id}] P1 team score={p1_team_score:.3f}: {preview['p1_team_label']}", flush=True)
        print(f"[game {game_id}] P1 roles={preview['p1_team']['role_counts']}", flush=True)
        print(f"[game {game_id}] P2 team score={p2_team_score:.3f}: {preview['p2_team_label']}", flush=True)
        print(f"[game {game_id}] P2 roles={preview['p2_team']['role_counts']}", flush=True)

    state = make_battle(team1, team2, seed=rng.randint(1, 2**31 - 1))
    p1_examples: list[tuple[BattleState, object, list[object]]] = []
    p2_examples: list[tuple[BattleState, object, list[object]]] = []

    p1_mcts = _make_mcts(p1_agent, config, rng)
    p2_mcts = _make_mcts(p2_agent, config, rng)

    _progress(
        config,
        f"[game {game_id}] start | P1 agent {p1_agent_id} {p1_agent.name} Elo={p1_agent.elo:.1f} "
        f"vs P2 agent {p2_agent_id} {p2_agent.name} Elo={p2_agent.elo:.1f}",
    )

    for turn_index in range(config.max_turns):
        if state.winner is not None:
            break

        state = _handle_replacement_with_agent(state, 1, p1_agent, rng)
        state = _handle_replacement_with_agent(state, 2, p2_agent, rng)

        if state.winner is not None:
            break

        p1_legal = legal_actions(state, 1)
        p2_legal = legal_actions(state, 2)
        if not p1_legal or not p2_legal:
            break

        p1_result = p1_mcts.search(state, 1)
        p2_result = p2_mcts.search(state, 2)
        p1_action = p1_result.action
        p2_action = p2_result.action

        p1_examples.append((state.clone(), p1_action, p1_legal))
        p2_examples.append((state.clone(), p2_action, p2_legal))

        next_state, turn_log = step(state, p1_action, p2_action)

        event = {
            "type": "turn",
            "game_id": game_id,
            "generation": generation,
            "swiss_round": swiss_round,
            "turn_index": turn_index,
            "p1_agent_id": p1_agent_id,
            "p2_agent_id": p2_agent_id,
            "p1_agent_name": p1_agent.name,
            "p2_agent_name": p2_agent.name,
            "state": state_summary(state),
            "p1_action": action_label(state, 1, p1_action),
            "p2_action": action_label(state, 2, p2_action),
            "p1_mcts": p1_result.as_log_dict(),
            "p2_mcts": p2_result.as_log_dict(),
            "turn_log": turn_log.lines,
        }
        _emit_event(log_file, human_log_file, config, event)

        if config.progress_turns:
            p1_state = event["state"]["p1"]
            p2_state = event["state"]["p2"]
            p1_active = p1_state["active"]
            p2_active = p2_state["active"]
            p1_hp = f"{p1_state['hp']}/{p1_state['max_hp']}"
            p2_hp = f"{p2_state['hp']}/{p2_state['max_hp']}"
            _progress_turn(
                config,
                state.field.turn,
                f"[turn {game_id}:{state.field.turn}] {p1_active} {p1_hp} -> {event['p1_action']} | "
                f"{p2_active} {p2_hp} -> {event['p2_action']}",
            )
            if config.progress_mcts:
                _progress_turn(config, state.field.turn, f"  P1 MCTS: {_format_root_preview(event['p1_mcts'], top_n=config.debug_mcts_top_n)}")
                _progress_turn(config, state.field.turn, f"  P2 MCTS: {_format_root_preview(event['p2_mcts'], top_n=config.debug_mcts_top_n)}")
            for line in turn_log.lines:
                _progress_turn(config, state.field.turn, f"  {line}")

        if config.debug_turns:
            print(f"[game {game_id} turn {state.field.turn}] P1 {event['p1_action']} | P2 {event['p2_action']}", flush=True)
            print(f"  P1 MCTS: {_format_root_preview(event['p1_mcts'], top_n=config.debug_mcts_top_n)}", flush=True)
            print(f"  P2 MCTS: {_format_root_preview(event['p2_mcts'], top_n=config.debug_mcts_top_n)}", flush=True)
            for line in turn_log.lines:
                print(f"  {line}", flush=True)

        state = next_state

    p1_value = _winner_value(state, 1)
    p2_value = _winner_value(state, 2)

    for example_state, action, legal in p1_examples:
        p1_agent.update_policy_toward(example_state, 1, action, list(legal))
        p1_agent.update_value(example_state, 1, p1_value)

    for example_state, action, legal in p2_examples:
        p2_agent.update_policy_toward(example_state, 2, action, list(legal))
        p2_agent.update_value(example_state, 2, p2_value)

    p1_agent.update_team_value(team1, p1_value)
    p2_agent.update_team_value(team2, p2_value)

    result = {
        "game_id": game_id,
        "generation": generation,
        "swiss_round": swiss_round,
        "p1_agent_id": p1_agent_id,
        "p2_agent_id": p2_agent_id,
        "p1_agent_name": p1_agent.name,
        "p2_agent_name": p2_agent.name,
        "winner": state.winner,
        "turns": state.field.turn,
        "p1_value": p1_value,
        "p2_value": p2_value,
        "final": state_summary(state),
    }
    _emit_event(log_file, human_log_file, config, {"type": "game_result", **result})
    winner_text = "draw/unfinished" if state.winner in (None, 0) else f"player {state.winner}"
    _progress(config, f"[game {game_id}] result | winner={winner_text} | turns={state.field.turn} | values P1={p1_value:.3f} P2={p2_value:.3f}")
    return result


def play_training_game(
    agent: LinearPolicyValueAgent,
    team1: list[PokemonSet],
    team2: list[PokemonSet],
    *,
    config: TrainingConfig,
    rng: random.Random,
    game_id: str,
    log_file,
    human_log_file=None,
) -> dict:
    return play_training_game_between_agents(
        agent,
        agent,
        team1,
        team2,
        config=config,
        rng=rng,
        game_id=game_id,
        log_file=log_file,
        human_log_file=human_log_file,
        p1_agent_id=0,
        p2_agent_id=0,
    )


def _initial_population(config: TrainingConfig, rng: random.Random) -> list[LinearPolicyValueAgent]:
    agent_count = max(1, config.agent_count)
    base = LinearPolicyValueAgent(name="g0-a0", elo=config.elo_initial)
    population = [base]
    for agent_id in range(1, agent_count):
        mutant = base.mutate(scale=config.mutation_scale, rng=rng)
        mutant.name = f"g0-a{agent_id}"
        mutant.elo = config.elo_initial
        population.append(mutant)
    return population


def _sort_standings(standings: list[AgentStanding], rng: random.Random) -> list[AgentStanding]:
    shuffled = list(standings)
    rng.shuffle(shuffled)
    return sorted(shuffled, key=lambda s: (-s.points, -s.elo, -s.wins, s.losses, s.agent_id))


def _swiss_pairings(standings: list[AgentStanding], rng: random.Random) -> tuple[list[tuple[int, int]], int | None]:
    ordered = _sort_standings(standings, rng)
    bye_agent_id: int | None = None

    if len(ordered) % 2 == 1:
        bye_candidate = next((s for s in reversed(ordered) if s.byes == 0), ordered[-1])
        bye_agent_id = bye_candidate.agent_id
        ordered = [s for s in ordered if s.agent_id != bye_agent_id]

    pairings: list[tuple[int, int]] = []
    while ordered:
        first = ordered.pop(0)
        opponent_index = None
        for index, candidate in enumerate(ordered):
            if candidate.agent_id not in first.opponents:
                opponent_index = index
                break
        if opponent_index is None:
            opponent_index = 0
        second = ordered.pop(opponent_index)
        pairings.append((first.agent_id, second.agent_id))

    return pairings, bye_agent_id


def _record_result(
    standings: dict[int, AgentStanding],
    population: list[LinearPolicyValueAgent],
    p1_agent_id: int,
    p2_agent_id: int,
    result: dict,
    *,
    k_factor: float,
) -> dict:
    p1 = standings[p1_agent_id]
    p2 = standings[p2_agent_id]
    p1.games += 1
    p2.games += 1
    p1.turns += result["turns"]
    p2.turns += result["turns"]
    p1.opponents.add(p2_agent_id)
    p2.opponents.add(p1_agent_id)

    winner = result["winner"]
    if winner == 1:
        p1.wins += 1
        p2.losses += 1
        p1.points += 1.0
    elif winner == 2:
        p2.wins += 1
        p1.losses += 1
        p2.points += 1.0
    else:
        p1.draws += 1
        p2.draws += 1
        p1.points += 0.5
        p2.points += 0.5

    new_p1_elo, new_p2_elo, elo_event = _apply_elo_update(
        p1.elo,
        p2.elo,
        winner,
        k_factor=k_factor,
    )

    p1.elo = new_p1_elo
    p2.elo = new_p2_elo
    p1.elo_peak = max(p1.elo_peak, p1.elo)
    p2.elo_peak = max(p2.elo_peak, p2.elo)

    population[p1_agent_id].elo = new_p1_elo
    population[p2_agent_id].elo = new_p2_elo

    return {
        "type": "elo_update",
        "game_id": result.get("game_id"),
        "generation": result.get("generation"),
        "swiss_round": result.get("swiss_round"),
        "p1_agent_id": p1_agent_id,
        "p2_agent_id": p2_agent_id,
        "winner": winner,
        **elo_event,
    }


def _standings_event(generation: int, swiss_round: int | None, standings: dict[int, AgentStanding]) -> dict:
    ordered = sorted(standings.values(), key=lambda s: (-s.points, -s.wins, s.losses, s.agent_id))
    return {
        "type": "swiss_standings",
        "generation": generation,
        "swiss_round": swiss_round,
        "standings": [s.as_dict() for s in ordered],
    }


def _pairings_event(
    generation: int,
    swiss_round: int,
    pairings: list[tuple[int, int]],
    bye_agent_id: int | None,
    standings: dict[int, AgentStanding] | None = None,
) -> dict:
    formatted_pairings = []
    for a, b in pairings:
        entry = {"p1_agent_id": a, "p2_agent_id": b}
        if standings is not None:
            entry["p1_elo"] = round(standings[a].elo, 2)
            entry["p2_elo"] = round(standings[b].elo, 2)
        formatted_pairings.append(entry)

    return {
        "type": "swiss_pairings",
        "generation": generation,
        "swiss_round": swiss_round,
        "pairings": formatted_pairings,
        "bye_agent_id": bye_agent_id,
        "bye_elo": round(standings[bye_agent_id].elo, 2) if standings is not None and bye_agent_id is not None else None,
    }


def _next_generation_population(
    population: list[LinearPolicyValueAgent],
    standings: dict[int, AgentStanding],
    generation: int,
    config: TrainingConfig,
    rng: random.Random,
) -> list[LinearPolicyValueAgent]:
    ranked_ids = [s.agent_id for s in sorted(standings.values(), key=lambda s: (-s.points, -s.elo, -s.wins, s.losses, s.agent_id))]
    elite_count = max(1, min(config.elite_count, len(population)))
    elites = [population[i] for i in ranked_ids[:elite_count]]

    next_population: list[LinearPolicyValueAgent] = []
    for new_id in range(max(1, config.agent_count)):
        parent = elites[new_id % len(elites)]
        if new_id < elite_count:
            child = LinearPolicyValueAgent.from_dict(parent.to_dict())
            child.name = f"g{generation + 1}-a{new_id}-elite-from-{ranked_ids[new_id]}"
        else:
            child = parent.mutate(scale=config.mutation_scale, rng=rng)
            child.name = f"g{generation + 1}-a{new_id}-from-{ranked_ids[new_id % len(elites)]}"
        next_population.append(child)

    return next_population


def _save_population(population: list[LinearPolicyValueAgent], path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps([agent.to_dict() for agent in population], indent=2, sort_keys=True), encoding="utf-8")


def run_generational_training(config: TrainingConfig, *, pool_path: str | Path | None = None) -> LinearPolicyValueAgent:
    rng = random.Random(config.seed)
    pool = load_set_pool(pool_path or default_compendium_path(), expand_variants=True, supported_only=True)

    log_path = Path(config.log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    human_log_path = Path(config.human_log_path) if config.human_log_path else None
    if human_log_path is not None:
        human_log_path.parent.mkdir(parents=True, exist_ok=True)
    model_path = Path(config.model_path)
    model_path.parent.mkdir(parents=True, exist_ok=True)

    population = _initial_population(config, rng)

    _progress(
        config,
        "[training] "
        f"generations={config.generations}, agents={config.agent_count}, swiss_rounds={config.swiss_rounds}, "
        f"games_per_pairing={config.games_per_pairing}, sims={config.mcts_simulations}, depth={config.mcts_depth}, "
        f"team_candidates={config.team_candidate_count}",
    )
    _progress(config, f"[training] logs jsonl={log_path} readable={human_log_path} model={model_path}")

    with log_path.open("w", encoding="utf-8") as log_file:
        human_log_file = human_log_path.open("w", encoding="utf-8") if human_log_path is not None else None
        try:
            for generation in range(config.generations):
                _progress(config, f"[generation {generation}] starting with {len(population)} agents")

                standings = {
                    agent_id: AgentStanding(
                        agent_id=agent_id,
                        name=agent.name,
                        elo_start=agent.elo,
                        elo=agent.elo,
                        elo_peak=agent.elo,
                    )
                    for agent_id, agent in enumerate(population)
                }

                for swiss_round in range(config.swiss_rounds):
                    pairings, bye_agent_id = _swiss_pairings(list(standings.values()), rng)

                    if bye_agent_id is not None:
                        standings[bye_agent_id].byes += 1
                        standings[bye_agent_id].points += 1.0

                    pairings_event = _pairings_event(generation, swiss_round, pairings, bye_agent_id, standings)
                    _emit_event(log_file, human_log_file, config, pairings_event)
                    if config.progress or config.verbose:
                        formatted_pairings = ", ".join(
                            f"{a}({standings[a].elo:.1f}) vs {b}({standings[b].elo:.1f})"
                            for a, b in pairings
                        )
                        bye_text = f", bye={bye_agent_id}({standings[bye_agent_id].elo:.1f})" if bye_agent_id is not None else ""
                        print(f"[generation {generation} round {swiss_round}] pairings: {formatted_pairings}{bye_text}", flush=True)

                    for pairing_index, (a_id, b_id) in enumerate(pairings):
                        for game_in_pairing in range(config.games_per_pairing):
                            if (swiss_round + pairing_index + game_in_pairing) % 2 == 0:
                                p1_id, p2_id = a_id, b_id
                            else:
                                p1_id, p2_id = b_id, a_id

                            _progress(
                                config,
                                f"[generation {generation} round {swiss_round}] game {pairing_index}-{game_in_pairing}: "
                                f"agent {p1_id} vs agent {p2_id}",
                            )

                            team1, p1_team_score, _ = _choose_team(pool, population[p1_id], config, rng)
                            team2, p2_team_score, _ = _choose_team(pool, population[p2_id], config, rng)

                            result = play_training_game_between_agents(
                                population[p1_id],
                                population[p2_id],
                                team1,
                                team2,
                                config=config,
                                rng=rng,
                                game_id=f"g{generation}-r{swiss_round}-p{pairing_index}-{game_in_pairing}",
                                log_file=log_file,
                                human_log_file=human_log_file,
                                p1_agent_id=p1_id,
                                p2_agent_id=p2_id,
                                generation=generation,
                                swiss_round=swiss_round,
                                p1_team_score=p1_team_score,
                                p2_team_score=p2_team_score,
                            )
                            elo_event = _record_result(
                                standings,
                                population,
                                p1_id,
                                p2_id,
                                result,
                                k_factor=config.elo_k_factor,
                            )
                            _emit_event(log_file, human_log_file, config, elo_event)
                            if config.progress or config.verbose:
                                print(
                                    f"[elo {result['game_id']}] agent {p1_id}: {elo_event['p1_old_elo']} -> {elo_event['p1_new_elo']} "
                                    f"({elo_event['p1_elo_delta']:+}); "
                                    f"agent {p2_id}: {elo_event['p2_old_elo']} -> {elo_event['p2_new_elo']} "
                                    f"({elo_event['p2_elo_delta']:+})",
                                    flush=True,
                                )

                    standings_event = _standings_event(generation, swiss_round, standings)
                    _emit_event(log_file, human_log_file, config, standings_event)
                    if config.progress or config.verbose:
                        print(f"[generation {generation} round {swiss_round}] standings:", flush=True)
                        for row in standings_event["standings"]:
                            print(f"  {_standing_line(row)}", flush=True)

                final_standings_event = _standings_event(generation, None, standings)
                summary = {
                    "type": "generation_summary",
                    "generation": generation,
                    "agents": len(population),
                    "swiss_rounds": config.swiss_rounds,
                    "games": sum(s.games for s in standings.values()) // 2,
                    "standings": final_standings_event["standings"],
                    "best_agent_id": final_standings_event["standings"][0]["agent_id"] if final_standings_event["standings"] else None,
                    "best_points": final_standings_event["standings"][0]["points"] if final_standings_event["standings"] else 0,
                    "best_elo": final_standings_event["standings"][0]["elo"] if final_standings_event["standings"] else config.elo_initial,
                    "avg_elo": (
                        sum(row["elo"] for row in final_standings_event["standings"]) / len(final_standings_event["standings"])
                        if final_standings_event["standings"]
                        else config.elo_initial
                    ),
                }
                _emit_event(log_file, human_log_file, config, summary)
                if config.progress or config.verbose:
                    print(
                        f"[generation {generation}] complete | best_agent={summary['best_agent_id']} "
                        f"points={summary['best_points']} best_elo={summary.get('best_elo')} avg_elo={summary.get('avg_elo')}",
                        flush=True,
                    )
                log_file.flush()

                best_agent_id = summary["best_agent_id"]
                if best_agent_id is not None:
                    population[best_agent_id].save(model_path)

                population = _next_generation_population(population, standings, generation, config, rng)
        finally:
            if human_log_file is not None:
                human_log_file.close()

    _save_population(population, config.population_path)
    return population[0]
