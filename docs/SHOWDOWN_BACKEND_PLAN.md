# Showdown Backend Plan

## Decision

Long term, the MCTS/ML system should not depend on the hand-written Python battle engine as the authoritative mechanics source.

The Python engine remains useful as:

- a learning scaffold
- a fast unit-test toy
- a fallback backend
- a place to understand and isolate mechanics

Serious training should eventually use a Pokémon Showdown-style simulator backend.

## Current constraint

Pokémon Showdown itself is open source and documents itself as both a battle website and a JavaScript simulator library/CLI tooling.

PokeMMO Showdown appears to be a public battle server/client tailored for PokeMMO, but the public Reddit announcement thread says the specific PokeMMO Showdown client/server is probably not open source. Its calculator and Pokédex/data may be released separately.

Therefore, this project should not assume the PokeMMO Showdown server source is available.

## Architecture

Add a backend interface:

```txt
BattleBackend
  reset(team1, team2, seed)
  legal_actions(player)
  step(p1_action, p2_action)
  needs_replacement(player)
  replace_fainted(player, new_index)
  clone()
  state_summary()
  winner()
```

Current backends:

```txt
PythonBattleBackend
  wraps our existing Python battle engine

ShowdownBattleBackend
  shells out to a local Node bridge
  does not call public servers
  checks local SHOWDOWN_ROOT
  currently replays battle history into a fresh BattleStream per call
```

## Why a backend interface?

The MCTS/training system should care about:

- legal actions
- resolving turns
- current state summary
- winner/draw state
- readable logs

It should not care whether the physics came from our Python simulator or a Node/Showdown simulator.

## Integration path

### Phase 1: Interface scaffold

- [x] Add `battle_engine/backends/base.py`.
- [x] Add `PythonBattleBackend`.
- [x] Add `ShowdownBattleBackend`.
- [x] Add local Node bridge check script.
- [x] Keep training on Python backend for now.

### Phase 2: Local Showdown checkout

- [x] Clone/build Pokémon Showdown locally outside this repo.
- [x] Verify local Node bridge can import the simulator.
- [x] Run a fixed test battle from the Node bridge.
- [x] Return structured JSON: logs, winner, side state, active Pokémon.
- [x] Return first-pass legal-action metadata for moves: id/name, type, category, base power, accuracy, priority.
- [x] Convert Python `PokemonSet` to Showdown set payload/importable text.
- [x] Convert Python `Action` to Showdown choice strings.
- [ ] Replace stateless replay calls with a persistent worker once correctness is trusted.

### Phase 3: PokeMMO data/mechanics

- [ ] Identify where PokeMMO-specific data can be sourced.
- [ ] Add current PokeMMO OU usage ingestion.
- [ ] Add Jirachi, Porygon-Z, and any current OU-relevant missing species.
- [ ] Confirm whether a PokeMMO-aware Showdown fork/data package is public.
- [ ] If no full fork is public, decide whether to maintain our own data patch layer.

### Phase 4: Agent compatibility

- [x] Add `BattleBackend.clone()` so MCTS can branch simulations safely.
- [x] Teach MCTS to work against `BattleBackend` with `MCTSAgent.search_backend()`.
- [x] Add backend selection CLI flag: `--backend state|python|showdown`.
- [x] Add deterministic smoke tests for Python backend.
- [x] Add Showdown backend smoke tests that are skipped when unavailable.
- [x] Compare Python engine results against Showdown backend on golden cases.
- [x] Add backend self-play recorder that emits JSONL decision samples.
- [x] Add backend-neutral feature extraction for recorded summaries.
- [x] Preserve move metadata in backend actions, JSONL records, and action features.
- [x] Expose active Pokémon types in Python and Showdown summaries.
- [x] Add STAB and type-effectiveness action features.
- [x] Add switch target hazard and matchup features.
- [x] Add rough damage-estimate action features.
- [x] Add trainer that consumes backend JSONL records.
- [x] Add trainer/evaluator diagnostics for feature schema, top weights, ranked actions, and action traces.
- [ ] Decide how much of training can become backend-neutral versus Python-feature-dependent.

### Phase 5: Backend training pipeline

- [x] Record backend self-play decisions as JSONL with legal actions, chosen action, MCTS stats, final winner, and value target.
- [x] Add `backend_features.py` to featurize `state_summary` dictionaries instead of Python-only `BattleState` objects.
- [x] Add a trainer that consumes JSONL records before trying to merge the path into `training.py`.
- [x] Add a backend evaluation harness for random, trained-agent, and MCTS policies.
- [x] Add first-pass move metadata features.
- [x] Add STAB and type-effectiveness features.
- [x] Add first-pass switch target hazard/matchup features.
- [x] Add rough damage-estimate features.
- [x] Add action-ranking explanations and traceable evaluation reports.
- [x] Add material/damage-greedy opponent policy.
- [x] Add raw replay-log export for self-play and evaluation games.
- [x] Add one-command backend experiment runner for self-play, training, evaluation reports, and optional replay logs.
- [x] Add JSONL validation before training and in experiment runs.
- [x] Add experiment comparison CLI for comparing saved experiment folders.
- [ ] Add local HTML/client replay viewing for saved Showdown protocol logs.

## Post-bridge roadmap

The original bridge roadmap is mostly complete. The project has crossed the important seam: Showdown-backed MCTS can generate data, train a backend-neutral agent, and evaluate that agent through the backend interface.

The next roadmap should focus less on “can it run?” and more on “is the training useful, measurable, and scalable?”

### Phase 6: Experiment discipline

Goal: make every training run reproducible and comparable.

- [x] Add `run_backend_experiment.py` to chain self-play, validation, training, evaluation, summaries, and optional replay logs.
- [x] Save `config.json`, `selfplay.jsonl`, validation report, trained agent, metrics, eval reports, and summary files in one experiment folder.
- [x] Add `validate_backend_jsonl.py` / validation module to catch bad records before training.
- [x] Add `compare_experiments.py` to compare experiment folders.
- [ ] Add README examples for the standard experiment workflow.
- [ ] Add a small `experiments/README.md` explaining which generated outputs should stay untracked.
- [ ] Add `.gitignore` entries for large generated experiment data if not already present.

Useful commands:

```powershell
py examples/run_backend_experiment.py `
  --backend python `
  --teams single `
  --games 5 `
  --turns 5 `
  --sims 2 `
  --depth 1 `
  --epochs 3 `
  --eval-opponents first random damage `
  --out-dir experiments/python_single_001

py examples/compare_experiments.py `
  experiments/python_single_001 `
  experiments/python_single_002
```

Acceptance criteria:

```txt
One command produces a complete experiment folder.
Two experiment folders can be compared without manually reading JSON.
Bad JSONL fails before model training.
```

### Phase 7: Better evaluation ladder

Goal: make “agent got better” mean something.

Current evaluator opponents:

- `first`
- `random`
- `damage`
- `mcts`
- `agent`

Next evaluator baselines:

- [ ] `ko-secure`: prefers reliable KOs over maximum damage.
- [ ] `material`: estimates simple post-action material/HP advantage.
- [ ] `hazard-aware`: values hazards and hazard removal.
- [ ] `defensive-switch`: chooses safer switches based on type/hazard risk.
- [ ] `mixed-greedy`: combines damage, KO security, hazards, status, and switch safety.

Acceptance criteria:

```txt
Agent reliably beats first/random on simple teams.
Agent can be measured against damage and mixed-greedy baselines.
MCTS remains the expensive teacher/evaluator baseline.
```

### Phase 8: Team and matchup diversity

Goal: stop training only on toy matchups.

Add curated team pools:

- [ ] `teams/single.json`
- [ ] `teams/balance_basic.json`
- [ ] `teams/offense_basic.json`
- [ ] `teams/hazard_stack.json`
- [ ] `teams/weather_sand.json`
- [ ] `teams/weather_rain.json`
- [ ] `teams/pokemmo_common.json`

Add matchup modes:

- [ ] fixed team pair
- [ ] random pair
- [ ] round robin
- [ ] mirror
- [ ] held-out evaluation teams

Record this metadata in JSONL:

- [ ] `team_id`
- [ ] `team_archetype`
- [ ] `matchup_id`
- [ ] `format`
- [ ] `source`

Acceptance criteria:

```txt
A model can train on one team pool and evaluate on held-out team pools.
Evaluation can distinguish memorization from generalization.
```

### Phase 9: Feature quality upgrades

Goal: make the lightweight agent understand more than direct damage.

Already present:

- [x] HP/alive/weather/hazard/status features.
- [x] Move metadata features.
- [x] STAB and type-effectiveness features.
- [x] Switch hazard and matchup features.
- [x] Rough damage / KO / 2HKO / 3HKO features.

Next features:

- [ ] Speed and turn-order features.
- [ ] “Can KO before taking damage” features.
- [ ] Opponent threat estimate: best visible opposing move damage.
- [ ] Status move utility features.
- [ ] Hazard-setting and hazard-removal move features.
- [ ] Recovery move features.
- [ ] Setup/stat-boosting move features.
- [ ] Pivoting move features.
- [ ] Screen/weather/field-control features.
- [ ] Team-level HP/status/hazard pressure features.

Acceptance criteria:

```txt
Training diagnostics show meaningful nonzero weights on new features.
Evaluation improves against damage/mixed-greedy baselines or reveals clear failure cases.
```

### Phase 10: Better training targets

Goal: train on more information from MCTS, not just the single chosen action.

Current target:

```txt
MCTS chose this action.
```

Better target:

```txt
MCTS produced this visit distribution over legal actions.
```

Tasks:

- [ ] Record MCTS visit counts/probabilities into JSONL.
- [ ] Add policy-distribution training instead of chosen-action-only imitation.
- [ ] Track policy accuracy and chosen-action rank.
- [ ] Add train/validation split.
- [ ] Add early stopping and regularization for the linear trainer.
- [ ] Add value MSE and policy cross-entropy to metrics.

Acceptance criteria:

```txt
Agent learns from MCTS search distributions.
Training metrics can detect overfitting and regression.
Agent approximates low-sim MCTS decisions better than simple baselines.
```

### Phase 11: Larger Showdown self-play batches

Goal: find the point where useful learning starts and the stateless bridge becomes too slow.

Suggested progression:

- [ ] 10 Showdown games, low sims.
- [ ] 50 Showdown games, low sims.
- [ ] 100 Showdown games, low sims.
- [ ] 100 games with mixed teams.
- [ ] 500+ games only after throughput is understood.

Track:

- [ ] seconds/game
- [ ] records/sec
- [ ] average turns/game
- [ ] unresolved rate
- [ ] bridge calls/game
- [ ] evaluation win rates by opponent

Acceptance criteria:

```txt
A 100-game Showdown self-play run completes without crashes.
The resulting model beats first/random reliably and is measurable against damage/mixed-greedy.
```

### Phase 12: Persistent Showdown worker

Goal: make Showdown training fast enough for serious iteration.

Current Showdown backend is correct but slow because it replays battle history into a fresh BattleStream per call.

Target worker commands:

```json
{"cmd": "create", "battle_id": "...", "teams": "..."}
{"cmd": "legal_actions", "battle_id": "...", "player": 1}
{"cmd": "step", "battle_id": "...", "p1": "...", "p2": "..."}
{"cmd": "summary", "battle_id": "..."}
{"cmd": "destroy", "battle_id": "..."}
```

Hard part: MCTS needs branching. Branching requires either cheap replay, true cloning, or multiple worker sessions.

Suggested path:

- [ ] First persistent worker removes process-startup overhead but may still replay for clones.
- [ ] Add performance benchmark comparing stateless and persistent modes.
- [ ] Only attempt true state cloning after the persistent worker is stable.

Acceptance criteria:

```txt
Same correctness tests pass under persistent mode.
Self-play throughput improves measurably.
Crashes are recoverable and do not corrupt experiment output.
```

### Phase 13: Guided MCTS / distillation loop

Goal: make the trained agent useful to search, not just trained by search.

Current loop:

```txt
MCTS -> data -> agent -> evaluation
```

Target loop:

```txt
agent -> MCTS priors/value -> better MCTS -> better data -> better agent
```

Tasks:

- [ ] Let `MCTSAgent.search_backend()` accept backend-trained policy priors.
- [ ] Let `MCTSAgent.search_backend()` accept backend-trained value estimates.
- [ ] Compare guided MCTS vs unguided MCTS at the same sim count.
- [ ] Generate self-play with previous agent version as teacher support.
- [ ] Track model generation IDs in JSONL and experiment config.
- [ ] Evaluate agent N vs agent N-1.

Acceptance criteria:

```txt
Guided low-sim MCTS beats unguided low-sim MCTS.
New model generations show measurable improvement over older generations.
```

### Phase 14: Stronger model architecture

Goal: move beyond linear features only after the data/eval loop is trustworthy.

Possible next models:

- [ ] Regularized linear model improvements.
- [ ] Small MLP over dense backend features.
- [ ] Separate policy/value heads.
- [ ] Gradient-boosted model for value estimation.
- [ ] Sequence/history-aware model later.

Do not start here. A bigger model trained on bad data only becomes a more expensive liar.

Acceptance criteria:

```txt
The linear baseline is stable.
Feature coverage is good.
Experiments are reproducible.
The new model beats the linear model on held-out evaluation.
```

## Do not do

- Do not train against the public PokeMMO Showdown server.
- Do not scrape ladder games as a first step.
- Do not assume PokeMMO Showdown is open source.
- Do not delete the Python engine until the backend adapter has parity tests.
- Do not optimize the worker before measuring whether the stateless bridge is actually the bottleneck.
- Do not jump to a bigger neural model before the JSONL/evaluation loop is clean.

## Updated PokeMMO mechanics target

The current working assumption is:

```txt
Gen 8 behavior + Gen 5 type chart + no gimmicks + PokeMMO legality
```

So the Showdown mod scaffold should inherit from Gen 8, then patch type chart, Fairy removal, gimmick bans, species legality, learnsets, and current usage data.

See:

```txt
docs/POKEMMO_SHOWDOWN_MOD_PLAN.md
showdown_mod_template/
```
