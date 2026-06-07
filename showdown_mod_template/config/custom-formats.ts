import type { FormatList } from '../sim/dex-formats';

export const Formats: FormatList = [
	{
		section: "PokeMMO",
	},
	{
		name: "[PokeMMO] OU",
		desc: "Experimental PokeMMO OU scaffold: Gen 8 behavior baseline, Gen 5 type chart, no gimmicks, PokeMMO legality patches.",
		mod: "pokemmo",
		gameType: "singles",
		ruleset: [
			"PokeMMO Standard",
			"Sleep Clause Mod",
			"Species Clause",
			"OHKO Clause",
			"Evasion Moves Clause",
			"Dynamax Clause",
		],
		banlist: [
			// Fill from current PokeMMO OU clauses/tier bans later.
		],
	},
];
