# PokeMMO Showdown Mod Template

This template is meant to be copied into a local Pokémon Showdown checkout.

Target mechanics model:

- Gen 8 move / ability / item behavior as the baseline.
- Gen 5 type chart.
- No Fairy type.
- No gimmick mechanics: Dynamax, Gigantamax, Z-Moves, Mega Evolution, Terastallization.
- PokeMMO legality, usage, clauses, and PvP-specific balance patches layered on top.

This is a scaffold, not a finished PokeMMO simulator.

## Install into a local Showdown checkout

From this project root:

```bash
python scripts/install_showdown_mod.py --showdown-root /path/to/pokemon-showdown
```

Dry run:

```bash
python scripts/install_showdown_mod.py --showdown-root /path/to/pokemon-showdown --dry-run
```

Then check the copied files:

```bash
python scripts/check_pokemmo_mod.py --showdown-root /path/to/pokemon-showdown
```

## Important

The template deliberately avoids calling any public Showdown or PokeMMO Showdown server.

You still need to wire this into a local battle runner before training against it.
