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
- [ ] Compare Python engine results against Showdown backend on golden cases.
- [ ] Decide how much of training can become backend-neutral versus Python-feature-dependent.

## Do not do

- Do not train against the public PokeMMO Showdown server.
- Do not scrape ladder games as a first step.
- Do not assume PokeMMO Showdown is open source.
- Do not delete the Python engine until the backend adapter has parity tests.


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
