# PokeMMO Showdown Mod Plan

## Current target

PokeMMO mechanics are best approximated as:

```txt
Gen 8 move / ability / item behavior
Gen 5 type chart
no Fairy type
no gimmicks
PokeMMO legality / learnsets / usage / tiering
```

This means the Showdown mod should start from Gen 8 behavior and patch the type chart and legality layer.

## Why not Gen 5 as the base?

Gen 5 has the right type chart, but too many move, item, and ability behaviors would need to be ported forward.

## Why not Gen 9 as the base?

Gen 9 adds Terastallization and newer move/species/learnset assumptions that PokeMMO does not use. Gen 8 is a cleaner modern baseline.

## Template layout

```txt
showdown_mod_template/
  config/custom-formats.ts
  data/mods/pokemmo/
    scripts.ts
    typechart.ts
    pokedex.ts
    moves.ts
    abilities.ts
    items.ts
    rulesets.ts
    learnsets.ts
```

## Early implementation rules

- `scripts.ts` inherits from Gen 8.
- `typechart.ts` overrides the chart to Gen 5 and marks Fairy as nonstandard.
- `pokedex.ts` patches post-Gen-5 Fairy-type Pokémon back to their older typings.
- `moves.ts` marks Fairy moves and gimmick moves illegal until PokeMMO-specific behavior says otherwise.
- `items.ts` marks Z-Crystals and similar gimmick-only items illegal.
- `rulesets.ts` defines `PokeMMO Standard`.
- `custom-formats.ts` defines `[PokeMMO] OU`.

## Install

```bash
python scripts/install_showdown_mod.py --showdown-root /path/to/pokemon-showdown --dry-run
python scripts/install_showdown_mod.py --showdown-root /path/to/pokemon-showdown
python scripts/check_pokemmo_mod.py --showdown-root /path/to/pokemon-showdown
```

## Next work after scaffold

- [ ] Clone Pokémon Showdown locally.
- [ ] Install the template into the checkout.
- [ ] Run Showdown's build/tests.
- [ ] Add a minimal local battle runner for `[PokeMMO] OU`.
- [ ] Make `tools/showdown_bridge/run_battle.mjs` run one fixed battle.
- [ ] Return battle logs and winner to Python.
- [ ] Teach `ShowdownBattleBackend` to call the real bridge.
- [ ] Add usage import for current PokeMMO OU.
- [ ] Generate coverage report for >4% usage.
- [ ] Patch missing species, moves, abilities, items, and learnsets.
- [ ] Add validation checks for Fairy leaks.
- [ ] Add Jirachi and Porygon-Z usage/set support once current data confirms their role.
