export const Pokedex: import('../../../sim/dex-species').ModdedSpeciesDataTable = {
	// PokeMMO uses the Gen 5 type chart, so Pokémon that gained Fairy typing
	// need explicit pre-Fairy typing patches. This is not exhaustive yet.

	clefairy: { inherit: true, types: ["Normal"] },
	clefable: { inherit: true, types: ["Normal"] },
	jigglypuff: { inherit: true, types: ["Normal"] },
	wigglytuff: { inherit: true, types: ["Normal"] },
	mimejr: { inherit: true, types: ["Psychic"] },
	mrmime: { inherit: true, types: ["Psychic"] },
	togepi: { inherit: true, types: ["Normal"] },
	togetic: { inherit: true, types: ["Normal", "Flying"] },
	togekiss: { inherit: true, types: ["Normal", "Flying"] },
	marill: { inherit: true, types: ["Water"] },
	azumarill: { inherit: true, types: ["Water"] },
	snubbull: { inherit: true, types: ["Normal"] },
	granbull: { inherit: true, types: ["Normal"] },
	ralts: { inherit: true, types: ["Psychic"] },
	kirlia: { inherit: true, types: ["Psychic"] },
	gardevoir: { inherit: true, types: ["Psychic"] },
	mawile: { inherit: true, types: ["Steel"] },
	cottonee: { inherit: true, types: ["Grass"] },
	whimsicott: { inherit: true, types: ["Grass"] },

	// Known OU-relevant omissions from the old local compendium can be patched here
	// once current PokeMMO usage data confirms their sets and legality.
	jirachi: { inherit: true },
	porygonz: { inherit: true },
};
