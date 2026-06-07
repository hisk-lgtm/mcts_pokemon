from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse

from battle_engine.training import TrainingConfig, run_generational_training


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generations", type=int, default=2)
    parser.add_argument("--agents", type=int, default=4)
    parser.add_argument("--swiss-rounds", type=int, default=3)
    parser.add_argument("--games-per-pairing", type=int, default=1)
    parser.add_argument("--elite-count", type=int, default=1)
    parser.add_argument("--mutation-scale", type=float, default=0.01)
    parser.add_argument("--elo-initial", type=float, default=1000.0)
    parser.add_argument("--elo-k", type=float, default=32.0)
    parser.add_argument("--team-candidates", type=int, default=32)
    parser.add_argument("--team-temperature", type=float, default=0.15)
    parser.add_argument("--games", type=int, default=2, help="Legacy single-agent setting; not used by Swiss mode.")
    parser.add_argument("--sims", type=int, default=16)
    parser.add_argument("--depth", type=int, default=12)
    parser.add_argument("--max-turns", type=int, default=40)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--verbose", action="store_true", help="Alias for detailed generation/round console output.")
    parser.add_argument("--progress", action="store_true", help="Print readable runtime progress while training.")
    parser.add_argument("--progress-turns", action="store_true", help="Print compact turn-by-turn runtime output.")
    parser.add_argument("--progress-every", type=int, default=1, help="Only print every N turns when --progress-turns is enabled.")
    parser.add_argument("--progress-mcts", action="store_true", help="Include compact MCTS root stats in turn progress output.")
    parser.add_argument("--debug-turns", action="store_true", help="Very noisy turn-by-turn debug output.")
    parser.add_argument("--debug-teams", action="store_true", help="Very noisy team debug output.")
    parser.add_argument("--debug-mcts-top", type=int, default=3)
    parser.add_argument("--log-path", default="training_logs/generational_training.jsonl")
    parser.add_argument("--human-log-path", default="training_logs/generational_training.log")
    parser.add_argument("--human-log-top", type=int, default=5)
    parser.add_argument("--model-path", default="training_logs/latest_agent.json")
    parser.add_argument("--population-path", default="training_logs/latest_population.json")
    args = parser.parse_args()

    config = TrainingConfig(
        generations=args.generations,
        games_per_generation=args.games,
        mcts_simulations=args.sims,
        mcts_depth=args.depth,
        max_turns=args.max_turns,
        seed=args.seed,
        agent_count=args.agents,
        swiss_rounds=args.swiss_rounds,
        games_per_pairing=args.games_per_pairing,
        elite_count=args.elite_count,
        mutation_scale=args.mutation_scale,
        elo_initial=args.elo_initial,
        elo_k_factor=args.elo_k,
        team_candidate_count=args.team_candidates,
        team_temperature=args.team_temperature,
        verbose=args.verbose,
        progress=args.progress,
        progress_turns=args.progress_turns,
        progress_every=args.progress_every,
        progress_mcts=args.progress_mcts,
        debug_turns=args.debug_turns,
        debug_teams=args.debug_teams,
        debug_mcts_top_n=args.debug_mcts_top,
        log_path=args.log_path,
        human_log_path=args.human_log_path,
        human_log_top_n=args.human_log_top,
        model_path=args.model_path,
        population_path=args.population_path,
    )
    agent = run_generational_training(config)
    print(f"Saved model to {args.model_path}")
    print(f"Saved JSONL logs to {args.log_path}")
    print(f"Saved readable logs to {args.human_log_path}")
    print(f"Saved population to {args.population_path}")
    print(f"Policy weights: {len(agent.policy_weights)}")
    print(f"Value weights: {len(agent.value_weights)}")
    print(f"Returned next-generation seed agent Elo: {agent.elo:.2f}")


if __name__ == "__main__":
    main()
