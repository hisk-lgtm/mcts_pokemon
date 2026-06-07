# PokeMMO MCTS Battle Engine Starter

This is a deliberately scoped Python battle engine intended for AI experiments, not a full 1:1 PokeMMO clone yet.

The design goal is:

1. Start with a small OU-relevant move/species/item subset.
2. Make the engine deterministic and fast enough for MCTS rollouts.
3. Keep all mechanics data-driven so PokeMMO OU usage data and sample sets can be imported later.
4. Add mechanics only when they matter to the policy/value learner.

## Implemented

- Singles 6v6 structure
- Level 50 stat calculation
- Gen 5-style type chart, no Fairy
- Damage formula approximation with STAB, type effectiveness, weather, burn, crit, random roll, Life Orb, Choice items, Expert Belt, and Rock SpDef boost in sand
- Items: Leftovers, Black Sludge, Life Orb, Choice Band, Choice Specs, Choice Scarf, Expert Belt, Focus Sash, Lum Berry, Sitrus Berry, Rocky Helmet
- Abilities: Sand Stream, Drizzle, Drought, Levitate, Intimidate, Natural Cure, Regenerator, Guts, Technician, Multiscale, Magic Guard, Poison Heal, Iron Barbs, Rough Skin
- Hazards: Stealth Rock, Spikes, Rapid Spin hazard removal
- Status: burn, poison, toxic poison, paralysis
- Boost moves: Swords Dance, Dragon Dance, Calm Mind, Nasty Plot, Bulk Up
- Recovery: Recover, Roost, Soft-Boiled
- Protect
- U-turn / Volt Switch as simplified automatic pivot to the first healthy bench Pokémon
- Knock Off as item removal after damage

## Intentionally not implemented yet

- Full PokeMMO move/ability/item database
- Full accuracy edge cases
- Sleep/freeze/confusion
- Encore/Taunt/Substitute/Trick/Phazing
- Exact PokeMMO custom mechanic differences
- Team preview and hidden-information belief modeling
- PP exhaustion
- Full pivot choice control
- Perfect end-of-turn ordering

## Run tests

```bash
cd pokemmo_mcts_engine_starter
python -m pytest -q
```

## Run demo

```bash
python examples/demo_battle.py
```

## Importing sample sets later

Use `battle_engine.import_sets.parse_showdown_set()` for basic Showdown-style sets.
For the forum compendium, copy sets into text files first, then parse.

The `data/usage_over_4_template.json` file shows the intended shape for usage filtering.


## Variant set parsing

The importer now supports compendium shorthand such as:

```txt
Gyarados @ Leftovers / Lum Berry
Ability: Moxie / Intimidate
EVs: 6 HP / 252 Atk / 252 Spe
Jolly / Adamant Nature
- Ice Fang / Bounce
```

Existing behavior is preserved:

- `parse_showdown_set(block)` returns the leftmost concrete version.
- `parse_showdown_sets_file(path)` returns one leftmost set per block.
- `parse_showdown_set_options(block)` returns the structured option lists.
- `parse_showdown_set_variants(block)` expands a block into every concrete variant.
- `parse_showdown_sets_file(path, expand_variants=True)` expands every block in the file.

Expansion has a default per-set safety cap of 2048 variants. Pass
`max_variants_per_set=None` only if you intentionally want uncapped expansion.


## Move/species coverage report

After changing the compendium set file, run:

```bash
python examples/report_compendium_coverage.py
```

The target is zero missing species and zero missing moves. That means the engine can at least instantiate and click through every imported set, even when some move effects are still simplified.

## Manual battle tester

Run:

```bash
python examples/battle_tester_cli.py --seed 1
```

The tester creates two random six-Pokémon teams from `data/ou_sets_to_import_variants.txt`, prints both teams, then lets you choose both players' actions by number.

This is intentionally a command-line tester first. A GUI is possible later, but the terminal version is easier to debug while the battle engine is still changing.

## Current simulator honesty level

The imported compendium is now covered at the data level, but not every move has exact competitive behavior yet. Some status moves are simplified or logged as unimplemented. That is acceptable for manual smoke testing and early MCTS plumbing, but exact PokeMMO parity still needs validation move by move.


## Battle semantics corrections

The engine now separates a true failed move from a damaging move that resolves for zero damage.

Current working rule:

- Misses, Protect blocks, and no-target failures do not trigger Life Orb recoil.
- Type immunity / "It had no effect" outcomes do trigger Life Orb recoil for damaging moves.
- Protect fails when the opponent hard switches.
- End-of-turn fainting creates a replacement phase. Use `needs_replacement()` and
  `replace_fainted()` before starting the next normal turn.


## Choice item and Trick tests

Choice item behavior now has explicit tests:

- A Pokémon that successfully uses a move while holding Choice Band, Choice Specs,
  or Choice Scarf becomes locked into that move.
- The lock clears when that Pokémon switches out.
- Trick swaps the current held items, not just the original set items.
- If a Choice item is Tricked onto a Pokémon after it has already moved that turn,
  it is not retroactively locked.
- If a Choice item is Tricked onto a Pokémon before it moves, it locks when it
  successfully uses its selected move.

Stat-stage tests also verify that offensive and defensive boosts change damage.


## Sleep, toxic, and weight-based move mechanics

Sleep now uses explicit counters:

- Normal sleep gets a 1-3 move-attempt duration when applied.
- Rest sets sleep duration to exactly 3 move attempts.
- Sleep counters advance only when the sleeping Pokémon attempts to act.
- Switching out resets the current sleep counter to 0 but preserves the sleep status and duration.
- Sleep Talk is allowed while asleep and calls another move from the user's set.

Toxic poison has tests verifying the increasing 1/16, 2/16, 3/16... damage pattern.

Species data now includes `weight_kg`, and Low Kick / Grass Knot, Heavy Slam, and Gyro Ball
use variable base power helpers.


## Volatile and screen mechanics

The engine now includes first-pass implementations for:

- Teleport as a slow self-pivot.
- Counter using double the physical damage received earlier that turn.
- Leech Seed as a target volatile that persists if the seeder switches and clears if the seeded Pokémon switches.
- Reflect and Light Screen as side conditions that double the relevant defensive stat in singles damage calculation.
- Safeguard as a side condition that blocks newly applied status.
- Skill Swap using mutable active abilities that reset on switch.
- Substitute using a substitute HP buffer that disappears on switch.
- Switcheroo using the same item-swap path as Trick.
- Taunt as a volatile status-move blocker that cannot be reapplied while active and clears on switch.
- Trick Room as field speed-order reversal within the same priority bracket.


## Ability mechanics pass

The engine now has first-pass support for the abilities that appear in the current OU set pool.

Functional examples include Adaptability, Analytic, Blaze, Clear Body, Contrary, Defiant,
Drizzle, Drought, Flash Fire, Guts, Infiltrator, Inner Focus, Intimidate, Iron Barbs,
Iron Fist, Levitate, Magic Bounce, Magic Guard, Magnet Pull, Mold Breaker, Moxie,
Multiscale, Natural Cure, Pickpocket, Poison Heal, Reckless, Regenerator, Rough Skin,
Sand Rush, Sand Stream, Serene Grace, Sharpness, Sheer Force, Storm Drain, Sturdy,
Swift Swim, Technician, Thick Fat, and Trace.

Pressure, Steadfast, and some flinch/PP interactions remain intentionally limited until
the engine models PP and flinch as first-class state.


## MCTS and generational ML agents

The first AI layer is intentionally small and inspectable.

- `battle_engine.mcts.MCTSAgent` searches legal actions using sampled opponent actions and rollouts.
- `battle_engine.ml_agent.LinearPolicyValueAgent` is a lightweight policy/value model with readable weights.
- `battle_engine.training.run_generational_training()` runs self-play games, logs MCTS decisions, updates the linear model, mutates between generations, and saves a JSON model.

Example MCTS battle using the original direct `BattleState` path:

```bash
python examples/run_mcts_battle.py --seed 1 --turns 10 --sims 32
```

Example MCTS battle routed through the backend interface:

```bash
python examples/run_mcts_battle.py --backend python --seed 1 --turns 10 --sims 32
```

Example MCTS smoke battle through a local Showdown checkout:

```bash
python examples/run_mcts_battle.py --backend showdown --showdown-root /path/to/pokemon-showdown --seed 1 --turns 2 --sims 1 --depth 0
```

The Showdown backend currently replays battle history through a fresh Node process on each call, so keep `--sims`, `--depth`, and `--turns` low until a persistent worker exists.

Example with verbose damage debugging on the Python engine path:

```bash
python examples/run_mcts_battle.py --seed 1 --turns 3 --sims 8 --debug-damage
```

One-turn damage debug demo:

```bash
python examples/debug_damage_turn.py
```

Generational training:

```bash
python examples/train_generational_agents.py --generations 2 --games 2 --sims 16 --depth 12 --max-turns 40
```

Training writes JSONL logs by default to:

```txt
training_logs/generational_training.jsonl
```

and saves the current linear model to:

```txt
training_logs/latest_agent.json
```

The training logs include per-turn state summaries, selected actions, MCTS root statistics, and normal turn logs. Damage calculation debug logs are opt-in because they are too verbose for normal self-play runs.


## Readable training logs

Training still writes JSONL because that is the safer machine-readable source of truth, but it now also writes a battle-log style text file by default.

```bash
python examples/train_generational_agents.py --generations 1 --games 1 --sims 8 --human-log-path training_logs/readable.log
```

You can also convert an existing JSONL log:

```bash
python examples/format_training_log.py training_logs/generational_training.jsonl --output training_logs/readable.log --top 5
```

The readable log includes:

- game and turn headers
- active Pokémon, HP, status, hazards, field state
- chosen actions
- top MCTS root candidates with visits, mean value, and prior
- normal battle-log messages
- game results and generation summaries

Use the `.log` file when reading behavior. Use the `.jsonl` file when building analysis tools later.


## Teambuilding agent

The ML agent now has a separate teambuilding weight table in addition to battle policy/value weights.

Teambuilding is candidate-based:

1. Generate several random legal six-Pokémon teams from the set pool.
2. Infer role/tag features for each team.
3. Let the agent score the candidate teams.
4. Pick a team using the teambuilding score and `--team-temperature`.
5. After the game, update teambuilding weights toward the game outcome.

Role/tag examples:

- `hazard_setter`
- `hazard_removal`
- `pivot`
- `speed_control`
- `physical_attacker`
- `special_attacker`
- `defensive_backbone`
- `status_spreader`
- `setup`
- `priority`
- `recovery`
- `ground_immune`
- `electric_immune`
- attacking coverage tags such as `coverage:Fire`
- defensive type tags such as `type:Steel`

Training knobs:

```bash
python examples/train_generational_agents.py \
  --agents 8 \
  --swiss-rounds 4 \
  --team-candidates 64 \
  --team-temperature 0.15 \
  --debug-teams
```

`--team-candidates` controls how many candidate teams each agent scores before a match.
`--team-temperature 0` makes teambuilding greedy. Higher values add exploration.
`--debug-teams` prints the selected teams and role counts during training.

The readable training log now includes a `Team Preview` section before each battle, including team scores, members, and inferred tags.


## Elo tracking

Agents now carry a persistent Elo rating across generations. Elo is tournament bookkeeping,
not the direct training objective.

New controls:

```bash
python examples/train_generational_agents.py \
  --agents 8 \
  --swiss-rounds 4 \
  --elo-initial 1000 \
  --elo-k 32
```

Elo rules:

- win = 1.0 score
- draw / unfinished = 0.5 score
- loss = 0.0 score
- byes do not change Elo
- children inherit the parent's current Elo when copied or mutated into the next generation

Elo appears in:

- readable Swiss pairings
- readable standings
- `elo_update` JSONL events
- saved agent JSON
- saved population JSON

This lets you separate two signals:

- Swiss points: who did well in the current generation's bracket
- Elo: a noisier but persistent cross-generation rating estimate


## Runtime console output

Use `--progress` when you want to watch training in the terminal without opening the JSONL or readable log files.

```bash
python examples/train_generational_agents.py \
  --generations 1 \
  --agents 4 \
  --swiss-rounds 2 \
  --sims 8 \
  --team-candidates 16 \
  --progress
```

This prints:

- training configuration and log paths
- generation starts
- Swiss pairings with Elo
- selected teams and role summaries
- game starts and results
- Elo updates
- standings after each Swiss round
- generation summary

For compact turn-by-turn output:

```bash
python examples/train_generational_agents.py \
  --generations 1 \
  --agents 2 \
  --swiss-rounds 1 \
  --sims 4 \
  --progress \
  --progress-turns
```

To avoid flooding the terminal:

```bash
python examples/train_generational_agents.py \
  --progress \
  --progress-turns \
  --progress-every 5
```

To include compact MCTS root summaries in the live turn output:

```bash
python examples/train_generational_agents.py \
  --progress \
  --progress-turns \
  --progress-mcts \
  --debug-mcts-top 3
```

`--debug-turns` and `--debug-teams` still exist, but they are intentionally noisier. Prefer `--progress` for normal monitoring.


## Engine polish checklist

A living mechanics checklist is available at:

```txt
docs/ENGINE_POLISH_CHECKLIST.md
```

Use this before scaling training runs. The goal is to turn every discovered battle discrepancy into a regression test instead of relying on memory.


## Backend adapter scaffold

The project now has a backend interface so the MCTS/training code can eventually swap battle simulators.

Current backend files:

```txt
battle_engine/backends/base.py
battle_engine/backends/python_backend.py
battle_engine/backends/showdown_backend.py
tools/showdown_bridge/run_battle.mjs
docs/SHOWDOWN_BACKEND_PLAN.md
```

Smoke test:

```bash
python examples/backend_smoke.py
```

Check local Showdown wiring:

```bash
python scripts/check_showdown_backend.py --showdown-root /path/to/pokemon-showdown
```

Current status:

- `PythonBattleBackend` wraps the existing Python engine.
- `ShowdownBattleBackend` shells out to the local Node bridge.
- It does not call public servers.
- It exports our `PokemonSet` objects to Showdown-compatible set payloads/importable text.
- The Node bridge can start a local Showdown `BattleStream`, apply teams and choices, and return legal actions, logs, winner, and state summaries.
- `MCTSAgent.search_backend()` can now search through either `PythonBattleBackend` or `ShowdownBattleBackend`.
- `examples/run_mcts_battle.py --backend python|showdown` exercises that path outside pytest.

The next step is to improve performance and parity: add more golden comparisons, then replace the stateless replay bridge with a persistent Node worker.


## PokeMMO Showdown mod template

A reproducible local Showdown mod scaffold is now included:

```txt
showdown_mod_template/
docs/POKEMMO_SHOWDOWN_MOD_PLAN.md
scripts/install_showdown_mod.py
scripts/check_pokemmo_mod.py
```

Current target:

```txt
Gen 8 behavior
Gen 5 type chart
no Fairy type
no gimmicks
PokeMMO legality / usage / tiering patches
```

Install into a local Pokémon Showdown checkout:

```bash
python scripts/install_showdown_mod.py --showdown-root /path/to/pokemon-showdown --dry-run
python scripts/install_showdown_mod.py --showdown-root /path/to/pokemon-showdown
python scripts/check_pokemmo_mod.py --showdown-root /path/to/pokemon-showdown
```


### Showdown lint indentation

Pokémon Showdown's TypeScript lint config expects tabs. The files in `showdown_mod_template/` are tab-normalized. If you already installed an older copy and lint complains about `Expected indentation of 1 tab but found 4 spaces`, reinstall the template with `--force`:

```powershell
py scripts/install_showdown_mod.py --showdown-root "C:\Users\skwil\pycharmprojects\pokemon-showdown" --force
```


### Showdown object brace spacing

Pokémon Showdown lint also expects spaces inside TypeScript object braces. Examples:

```ts
import type { FormatList } from '../sim/dex-formats';

togekiss: { inherit: true, types: ["Normal", "Flying"] },
```

If lint complains about `@stylistic/object-curly-spacing`, reinstall the latest template with `--force`.


### Showdown data table type fixes

Showdown mod data files use lowercase IDs for top-level typechart keys, for example `steel`, while `damageTaken` keys remain capitalized, for example `Ghost: 2`.

Rulesets should be typed as:

```ts
export const Rulesets: import('../../../sim/dex-formats').FormatDataTable = {
```

not with a bare `ModdedFormatData` name.

## Backend self-play records

The first backend-neutral training artifact is a JSONL self-play recorder. It runs MCTS through a `BattleBackend`, records both players' root decisions, and attaches final winner/value labels after each game.

Fast Python backend smoke run:

```bash
python examples/backend_selfplay.py --backend python --teams single --games 1 --turns 2 --sims 2 --depth 1 --out data/backend_selfplay.jsonl
```

Local Showdown backend smoke run:

```bash
python examples/backend_selfplay.py --backend showdown --showdown-root /path/to/pokemon-showdown --teams single --games 1 --turns 1 --sims 1 --depth 0 --out data/showdown_selfplay.jsonl
```

Use low `--sims`, `--depth`, and `--turns` for Showdown until the bridge moves from stateless replay calls to a persistent worker.

Inspect the recorded backend feature vectors:

```bash
python examples/inspect_backend_features.py data/backend_selfplay.jsonl --limit 3 --top 20
```

Train the first backend-neutral linear policy/value agent from those records:

```bash
python examples/train_backend_agent.py data/backend_selfplay.jsonl --out training_logs/backend_agent.json --epochs 3 --learning-rate 0.05
```

Evaluate the saved backend agent against simple baselines:

```bash
python examples/evaluate_backend_agent.py --backend python --agent training_logs/backend_agent.json --teams single --games 20 --opponent random
```

Local Showdown evaluation should stay tiny until the bridge has a persistent worker:

```bash
python examples/evaluate_backend_agent.py --backend showdown --showdown-root /path/to/pokemon-showdown --agent training_logs/backend_agent.json --teams single --games 3 --turns 5 --opponent first
```

This trainer consumes `state_summary`, `legal_actions`, `chosen_action`, and `value_target` records. Legal move actions now preserve first-pass metadata when the backend can provide it: move id/name, type, category, base power, accuracy, priority, and contact. The feature extractor turns that into policy features such as `move_type_rock`, `move_is_physical`, and `move_base_power`, which is the first step beyond raw move-slot imitation. It does not replace the older Python `BattleState` training path yet. The evaluator closes the first backend-training loop: generate JSONL, train a model, load it, act through a backend, and report wins/losses/unresolved games.
