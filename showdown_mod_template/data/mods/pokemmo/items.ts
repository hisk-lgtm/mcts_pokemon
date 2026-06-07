export const Items: import('../../../sim/dex-items').ModdedItemDataTable = {
	// Ban gimmick items/forms by legality rules first. Add exact item behavior
	// patches here only when PokeMMO differs from Gen 8.
	blueorb: { inherit: true, isNonstandard: "Past" },
	redorb: { inherit: true, isNonstandard: "Past" },

	// Z-Crystals are not PokeMMO mechanics.
	normaliumz: { inherit: true, isNonstandard: "Past" },
	firiumz: { inherit: true, isNonstandard: "Past" },
	wateriumz: { inherit: true, isNonstandard: "Past" },
	electriumz: { inherit: true, isNonstandard: "Past" },
	grassiumz: { inherit: true, isNonstandard: "Past" },
	iciumz: { inherit: true, isNonstandard: "Past" },
	fightiniumz: { inherit: true, isNonstandard: "Past" },
	poisoniumz: { inherit: true, isNonstandard: "Past" },
	groundiumz: { inherit: true, isNonstandard: "Past" },
	flyiniumz: { inherit: true, isNonstandard: "Past" },
	psychiumz: { inherit: true, isNonstandard: "Past" },
	buginiumz: { inherit: true, isNonstandard: "Past" },
	rockiumz: { inherit: true, isNonstandard: "Past" },
	ghostiumz: { inherit: true, isNonstandard: "Past" },
	dragoniumz: { inherit: true, isNonstandard: "Past" },
	darkiniumz: { inherit: true, isNonstandard: "Past" },
	steeliumz: { inherit: true, isNonstandard: "Past" },
	fairiumz: { inherit: true, isNonstandard: "Past" },
};
