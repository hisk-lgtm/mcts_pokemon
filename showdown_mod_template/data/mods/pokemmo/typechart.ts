export const TypeChart: import('../../../sim/dex-data').ModdedTypeDataTable = {
	// This is the Gen 5 chart encoded as a mod override.
	// damageTaken values follow Pokémon Showdown convention:
	// 0 = neutral, 1 = super effective, 2 = resisted, 3 = immune.

	normal: {
		inherit: true,
		damageTaken: {
			Normal: 0, Fire: 0, Water: 0, Electric: 0, Grass: 0, Ice: 0,
			Fighting: 1, Poison: 0, Ground: 0, Flying: 0, Psychic: 0, Bug: 0,
			Rock: 0, Ghost: 3, Dragon: 0, Dark: 0, Steel: 0,
		},
	},
	fire: {
		inherit: true,
		damageTaken: {
			Normal: 0, Fire: 2, Water: 1, Electric: 0, Grass: 2, Ice: 2,
			Fighting: 0, Poison: 0, Ground: 1, Flying: 0, Psychic: 0, Bug: 2,
			Rock: 1, Ghost: 0, Dragon: 0, Dark: 0, Steel: 2,
		},
	},
	water: {
		inherit: true,
		damageTaken: {
			Normal: 0, Fire: 2, Water: 2, Electric: 1, Grass: 1, Ice: 2,
			Fighting: 0, Poison: 0, Ground: 0, Flying: 0, Psychic: 0, Bug: 0,
			Rock: 0, Ghost: 0, Dragon: 0, Dark: 0, Steel: 2,
		},
	},
	electric: {
		inherit: true,
		damageTaken: {
			Normal: 0, Fire: 0, Water: 0, Electric: 2, Grass: 0, Ice: 0,
			Fighting: 0, Poison: 0, Ground: 1, Flying: 2, Psychic: 0, Bug: 0,
			Rock: 0, Ghost: 0, Dragon: 0, Dark: 0, Steel: 2,
		},
	},
	grass: {
		inherit: true,
		damageTaken: {
			Normal: 0, Fire: 1, Water: 2, Electric: 2, Grass: 2, Ice: 1,
			Fighting: 0, Poison: 1, Ground: 2, Flying: 1, Psychic: 0, Bug: 1,
			Rock: 0, Ghost: 0, Dragon: 0, Dark: 0, Steel: 0,
		},
	},
	ice: {
		inherit: true,
		damageTaken: {
			Normal: 0, Fire: 1, Water: 0, Electric: 0, Grass: 0, Ice: 2,
			Fighting: 1, Poison: 0, Ground: 0, Flying: 0, Psychic: 0, Bug: 0,
			Rock: 1, Ghost: 0, Dragon: 0, Dark: 0, Steel: 1,
		},
	},
	fighting: {
		inherit: true,
		damageTaken: {
			Normal: 0, Fire: 0, Water: 0, Electric: 0, Grass: 0, Ice: 0,
			Fighting: 0, Poison: 0, Ground: 0, Flying: 1, Psychic: 1, Bug: 2,
			Rock: 2, Ghost: 0, Dragon: 0, Dark: 2, Steel: 0,
		},
	},
	poison: {
		inherit: true,
		damageTaken: {
			Normal: 0, Fire: 0, Water: 0, Electric: 0, Grass: 2, Ice: 0,
			Fighting: 2, Poison: 2, Ground: 1, Flying: 0, Psychic: 1, Bug: 2,
			Rock: 0, Ghost: 0, Dragon: 0, Dark: 0, Steel: 0,
		},
	},
	ground: {
		inherit: true,
		damageTaken: {
			Normal: 0, Fire: 0, Water: 1, Electric: 3, Grass: 1, Ice: 1,
			Fighting: 0, Poison: 2, Ground: 0, Flying: 0, Psychic: 0, Bug: 0,
			Rock: 2, Ghost: 0, Dragon: 0, Dark: 0, Steel: 0,
		},
	},
	flying: {
		inherit: true,
		damageTaken: {
			Normal: 0, Fire: 0, Water: 0, Electric: 1, Grass: 2, Ice: 1,
			Fighting: 2, Poison: 0, Ground: 3, Flying: 0, Psychic: 0, Bug: 2,
			Rock: 1, Ghost: 0, Dragon: 0, Dark: 0, Steel: 0,
		},
	},
	psychic: {
		inherit: true,
		damageTaken: {
			Normal: 0, Fire: 0, Water: 0, Electric: 0, Grass: 0, Ice: 0,
			Fighting: 2, Poison: 0, Ground: 0, Flying: 0, Psychic: 2, Bug: 1,
			Rock: 0, Ghost: 1, Dragon: 0, Dark: 1, Steel: 0,
		},
	},
	bug: {
		inherit: true,
		damageTaken: {
			Normal: 0, Fire: 1, Water: 0, Electric: 0, Grass: 2, Ice: 0,
			Fighting: 2, Poison: 0, Ground: 2, Flying: 1, Psychic: 0, Bug: 0,
			Rock: 1, Ghost: 0, Dragon: 0, Dark: 0, Steel: 0,
		},
	},
	rock: {
		inherit: true,
		damageTaken: {
			Normal: 2, Fire: 2, Water: 1, Electric: 0, Grass: 1, Ice: 0,
			Fighting: 1, Poison: 2, Ground: 1, Flying: 2, Psychic: 0, Bug: 0,
			Rock: 0, Ghost: 0, Dragon: 0, Dark: 0, Steel: 1,
		},
	},
	ghost: {
		inherit: true,
		damageTaken: {
			Normal: 3, Fire: 0, Water: 0, Electric: 0, Grass: 0, Ice: 0,
			Fighting: 3, Poison: 2, Ground: 0, Flying: 0, Psychic: 0, Bug: 2,
			Rock: 0, Ghost: 1, Dragon: 0, Dark: 1, Steel: 0,
		},
	},
	dragon: {
		inherit: true,
		damageTaken: {
			Normal: 0, Fire: 2, Water: 2, Electric: 2, Grass: 2, Ice: 1,
			Fighting: 0, Poison: 0, Ground: 0, Flying: 0, Psychic: 0, Bug: 0,
			Rock: 0, Ghost: 0, Dragon: 1, Dark: 0, Steel: 0,
		},
	},
	dark: {
		inherit: true,
		damageTaken: {
			Normal: 0, Fire: 0, Water: 0, Electric: 0, Grass: 0, Ice: 0,
			Fighting: 1, Poison: 0, Ground: 0, Flying: 0, Psychic: 3, Bug: 1,
			Rock: 0, Ghost: 2, Dragon: 0, Dark: 2, Steel: 0,
		},
	},
	steel: {
		inherit: true,
		damageTaken: {
			Normal: 2, Fire: 1, Water: 0, Electric: 0, Grass: 2, Ice: 2,
			Fighting: 1, Poison: 3, Ground: 1, Flying: 2, Psychic: 2, Bug: 2,
			Rock: 2, Ghost: 2, Dragon: 2, Dark: 2, Steel: 2,
		},
	},
	fairy: {
		inherit: true,
		isNonstandard: "Past",
	},
};
