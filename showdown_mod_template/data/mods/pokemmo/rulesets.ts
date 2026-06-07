export const Rulesets: import('../../../sim/dex-formats').FormatDataTable = {
	pokemmostandard: {
		effectType: 'ValidatorRule',
		name: 'PokeMMO Standard',
		desc: 'Experimental PokeMMO legality scaffold: no gimmicks, no Fairy type, PokeMMO legality patches pending.',
		ruleset: ['Obtainable', 'Team Preview'],
		banlist: [
			'Dynamax',
			'Gigantamax',
			'Z-Move',
			'Mega Rayquaza Clause',

			// Fairy type is not part of the PokeMMO type chart.
			'Fairy',

			// Fill current PokeMMO OU bans here.
		],
	},
};
