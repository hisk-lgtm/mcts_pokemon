# Engine Polish Checklist

This checklist is for moving the simulator from "MVP usable" toward "close enough to the live PokeMMO battle environment that MCTS training is not learning junk physics."

The rule for this phase: every discovered mechanic discrepancy should become a regression test before or during the fix.

## 0. Reference Sources

- [ ] Pick a primary mechanics reference for PokeMMO-specific behavior.
- [ ] Keep Pokemon Showdown / PokeMMO Showdown behavior as a comparison target, not as unquestioned truth.
- [ ] Add a notes file for confirmed PokeMMO deviations from vanilla Gen 5 / later-gen mechanics.
- [ ] Add monthly OU usage import workflow before serious full-scale training.
- [ ] Replace the old sample compendium pool with current usage-driven set data.
- [ ] Add currently missing relevant OU Pokémon, including known omissions like Jirachi and Porygon-Z.
- [ ] Store the exact source/month for every usage/set dataset used in training.

## 1. Turn Order and Action Semantics

- [x] Choice lock persists until switch.
- [x] Trick / Switcheroo timing with Choice items.
- [x] Free replacement after fainting.
- [x] Protect fails into hard switch.
- [x] Trick Room reverses Speed order inside the same priority bracket.
- [x] Priority still beats Trick Room Speed reversal.
- [x] Second Trick Room use cancels Trick Room.
- [ ] Verify Trick Room duration against PokeMMO battle logs.
- [ ] Verify move order ties: random tie behavior and deterministic seeded tests.
- [ ] Verify Pursuit-on-switch behavior if/when Pursuit is in the move pool.
- [ ] Verify forced switch timing for Roar / Whirlwind / Dragon Tail.
- [ ] Verify U-turn / Volt Switch / Teleport timing and failure cases.
- [ ] Verify Encore / Disable / Taunt interaction ordering if those enter the pool.
- [ ] Add a turn-order trace mode for debugging priority, effective speed, Trick Room, and tie rolls.

## 2. Damage Formula

- [x] Verbose damage debug logs include attacking stat, defending stat, base power, modifiers, and final damage.
- [x] Stat boosts change offensive and defensive damage.
- [x] Screens reduce damage.
- [x] Infiltrator bypasses screens/substitute.
- [x] Variable power moves: Low Kick, Grass Knot, Heavy Slam, Gyro Ball.
- [ ] Validate damage outputs against a trusted PokeMMO calculator for a test matrix.
- [ ] Add golden damage tests for common OU matchups.
- [ ] Confirm critical hit stage rules and crit damage multiplier.
- [ ] Confirm burn modifier timing with Guts and Facade.
- [ ] Confirm weather damage modifiers.
- [ ] Confirm Life Orb / Sheer Force interaction.
- [ ] Confirm Expert Belt, Choice items, Eviolite, Assault Vest, type gems if relevant.
- [ ] Add spread move handling only if doubles ever becomes relevant.

## 3. Status Conditions

- [x] Sleep counter exists.
- [x] Rest sleep duration fixed at 3 move attempts.
- [x] Sleep counter advances only when attempting a move.
- [x] Sleep Talk exception exists.
- [x] Toxic damage increases.
- [x] Burn / poison residual damage.
- [x] Paralysis Speed reduction.
- [ ] Verify exact sleep duration distribution in PokeMMO.
- [ ] Verify wake-up turn move execution behavior.
- [ ] Verify confusion if added.
- [ ] Verify freeze if relevant.
- [ ] Verify status immunities by type, ability, Safeguard, Substitute, and Magic Bounce.
- [ ] Verify Natural Cure, Poison Heal, Magic Guard, Guts, Quick Feet if used.

## 4. Volatile Effects and Field Conditions

- [x] Substitute HP buffer and disappearance on switch.
- [x] Leech Seed persists when seeder switches and clears when seeded Pokémon switches.
- [x] Taunt blocks status moves and clears on switch.
- [x] Reflect / Light Screen / Safeguard.
- [x] Trick Room.
- [ ] Verify exact duration decrement timing for screens, Safeguard, Taunt, and Trick Room.
- [ ] Add Encore if relevant.
- [ ] Add Torment if relevant.
- [ ] Add Perish Song if relevant.
- [ ] Add Future Sight / Doom Desire if relevant.
- [ ] Add Substitute edge cases: sound moves, self-status, multi-hit breaking behavior, Baton Pass if relevant.

## 5. Hazards and Switching

- [x] Stealth Rock.
- [x] Spikes.
- [x] Toxic Spikes.
- [x] Rapid Spin clears user-side hazards.
- [x] Defog clears hazards.
- [ ] Verify grounded logic for Spikes / Toxic Spikes.
- [ ] Verify Flying-type, Levitate, Air Balloon, Magnet Rise interactions.
- [ ] Verify Toxic Spikes absorption by Poison-types.
- [ ] Verify hazard order relative to switch-in abilities and items.
- [ ] Verify Focus Sash / Sturdy after hazard damage.
- [ ] Verify Regenerator and Natural Cure switch timing.
- [ ] Verify Volt Switch / U-turn failure when target is immune or Protects.

## 6. Items

- [x] Choice items.
- [x] Life Orb.
- [x] Leftovers / Black Sludge.
- [x] Focus Sash.
- [x] Rocky Helmet.
- [x] Eviolite.
- [x] Trick / Switcheroo mutable item state.
- [ ] Verify item-removal effects: Knock Off, Trick, Switcheroo.
- [ ] Verify gems / berries / resist berries if used by OU sets.
- [ ] Verify Lum Berry and status berries.
- [ ] Verify Air Balloon if relevant.
- [ ] Verify Shed Shell versus trapping abilities.
- [ ] Verify Assault Vest status-move restriction if Assault Vest is present.
- [ ] Verify Custap / pinch berries if relevant.

## 7. Abilities

- [x] Weather setters: Sand Stream, Drizzle, Drought.
- [x] Speed weather abilities: Sand Rush, Swift Swim.
- [x] Damage abilities: Technician, Adaptability, Sheer Force, Iron Fist, Sharpness, Reckless, Blaze.
- [x] Defensive abilities: Multiscale, Thick Fat, Sturdy, Magic Guard.
- [x] Immunity/absorb abilities: Levitate, Flash Fire, Storm Drain.
- [x] Utility abilities: Intimidate, Moxie, Magic Bounce, Mold Breaker, Trace, Magnet Pull.
- [ ] Implement or verify Neutralizing Gas with a centralized effective-ability layer.
- [ ] Implement Pressure after PP exists.
- [ ] Implement flinch-related abilities after flinch exists.
- [ ] Verify ability suppression and ability reset after Skill Swap / switch.
- [ ] Verify contact abilities: Flame Body, Static, Cursed Body, Pickpocket, Rough Skin, Iron Barbs.
- [ ] Add ability-specific regression tests for every ability appearing in current OU usage over the cutoff.

## 8. Move Coverage

- [x] Importer expands slash variants.
- [x] Current old-compendium move pool has placeholder coverage.
- [ ] Re-scan current usage-based sets for missing moves.
- [ ] Classify every move as exact / approximate / unimplemented.
- [ ] Turn every `unimplemented` competitive move into either a real effect or an explicit documented no-op.
- [ ] Add PP to all moves.
- [ ] Add flinch.
- [ ] Add recoil edge cases.
- [ ] Add multi-hit exact behavior and loaded dice / skill link if relevant.
- [ ] Add sound move behavior if relevant.
- [ ] Add move-specific exceptions: Rapid Spin Speed boost if PokeMMO uses it, Knock Off item power rules, etc.

## 9. Team Data and Usage Data

- [ ] Replace the 2023/old sample compendium as the main pool.
- [ ] Add current OU usage stats ingestion.
- [ ] Add usage cutoff filtering, initially >4%.
- [ ] Store monthly snapshots under `data/usage/YYYY-MM.json`.
- [ ] Add Jirachi and Porygon-Z sets/data when current usage justifies them.
- [ ] Add species/move/item/ability coverage report against the current month.
- [ ] Separate "sample set pool" from "usage-weighted random pool."
- [ ] Weight random team generation by usage later, but keep an unweighted mode for exploration.

## 10. AI Training Reliability

- [x] MCTS root search exists.
- [x] ML policy/value agent exists.
- [x] Swiss tournaments and Elo exist.
- [x] Runtime progress output exists.
- [x] Readable logs exist.
- [x] Teambuilding role features exist.
- [ ] Add true recursive tree MCTS.
- [ ] Add state hashing / transposition cache.
- [ ] Add battle state serialization.
- [ ] Add deterministic replay from logs.
- [ ] Add policy evaluation against fixed baseline agents.
- [ ] Add exploit detection: does the agent repeatedly choose moves that only work because of a simulator bug?
- [ ] Add regression replay suite from suspicious training games.

## 11. Manual Battle Tester

- [x] CLI battle tester exists.
- [ ] Show turn-order details when requested.
- [ ] Show legal action reasons: choice lock, taunt, disabled, trapped.
- [ ] Show field/screen/weather/trick-room timers.
- [ ] Show volatile state: substitute HP, taunt, leech seed, sleep counter.
- [ ] Add replay save/load.
- [ ] Add "compare expected vs actual" notes during manual testing.

## 12. Release Gate Before Serious Training

Before doing serious long training runs:

- [ ] Current-month usage data imported.
- [ ] All >4% usage species have base stats, typing, weight, abilities, items, and moves.
- [ ] No competitive move in the selected pool is silently unimplemented.
- [ ] Damage formula validated against external calculator on at least 50 common interactions.
- [ ] Status / switching / hazards have regression tests.
- [ ] Manual battle tester can complete full games without obvious rule nonsense.
- [ ] Training logs can be replayed or at least audited turn by turn.
- [ ] Baseline fixed agents exist for comparison.
- [ ] Elo is stable enough to detect improvement over random/noisy baselines.
