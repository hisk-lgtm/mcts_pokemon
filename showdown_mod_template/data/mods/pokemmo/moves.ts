export const Moves: import('../../../sim/dex-moves').ModdedMoveDataTable = {
	// PokeMMO has no Fairy type. This placeholder marks Fairy moves as illegal
	// until we confirm any special PokeMMO handling.
	charm: { inherit: true, isNonstandard: "Past" },
	disarmingvoice: { inherit: true, isNonstandard: "Past" },
	drainingkiss: { inherit: true, isNonstandard: "Past" },
	moonblast: { inherit: true, isNonstandard: "Past" },
	playrough: { inherit: true, isNonstandard: "Past" },
	dazzlinggleam: { inherit: true, isNonstandard: "Past" },
	fairywind: { inherit: true, isNonstandard: "Past" },
	mistyterrain: { inherit: true, isNonstandard: "Past" },

	// Gimmick-related moves should remain illegal in PokeMMO.
	maxguard: { inherit: true, isNonstandard: "Past" },
};
