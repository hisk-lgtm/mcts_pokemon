#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import {createRequire} from 'node:module';

function jsonOut(payload) {
  process.stdout.write(JSON.stringify(payload, null, 2) + '\n');
}

function exists(p) {
  try {
    return !!p && fs.existsSync(p);
  } catch {
    return false;
  }
}

function resolveShowdownRoot() {
  return process.env.SHOWDOWN_ROOT || '';
}

function checkPayload() {
  const showdownRoot = resolveShowdownRoot();
  const packageJson = showdownRoot ? path.join(showdownRoot, 'package.json') : '';
  const simDir = showdownRoot ? path.join(showdownRoot, 'sim') : '';
  const distSimIndex = showdownRoot ? path.join(showdownRoot, 'dist', 'sim', 'index.js') : '';

  const rootOk = exists(showdownRoot);
  const packageOk = exists(packageJson);
  const simOk = exists(simDir);
  const distOk = exists(distSimIndex);

  return {
    available: rootOk && packageOk && simOk && distOk,
    node: process.version,
    showdown_root: showdownRoot || null,
    package_json_found: packageOk,
    sim_dir_found: simOk,
    dist_sim_index_found: distOk,
    reason: rootOk
      ? (packageOk && simOk && distOk
          ? 'Local Showdown-like checkout found. Battle stepping bridge can be invoked.'
          : 'SHOWDOWN_ROOT exists but does not look like a built Pokemon Showdown checkout.')
      : 'Set SHOWDOWN_ROOT to a local Pokemon Showdown or PokeMMO-aware fork checkout.',
  };
}

function check() {
  jsonOut(checkPayload());
}

function readStdin() {
  return new Promise((resolve, reject) => {
    let data = '';
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', chunk => {
      data += chunk;
    });
    process.stdin.on('end', () => resolve(data));
    process.stdin.on('error', reject);
  });
}

function toPRNGSeed(seed) {
  if (Array.isArray(seed)) return seed.join(',');
  if (typeof seed === 'string' && seed.includes(',')) return seed;
  const value = Number.isFinite(Number(seed)) ? Number(seed) : 1;
  // Showdown accepts four 16-bit Gen 5 seed parts.
  return [
    value & 0xFFFF,
    (value >>> 16) & 0xFFFF,
    (value * 1103515245 + 12345) & 0xFFFF,
    ((value * 1664525 + 1013904223) >>> 16) & 0xFFFF,
  ].join(',');
}

function normalizeStats(stats, fallback) {
  const out = {};
  for (const stat of ['hp', 'atk', 'def', 'spa', 'spd', 'spe']) {
    out[stat] = Number(stats?.[stat] ?? fallback);
  }
  return out;
}

function toShowdownSet(set) {
  return {
    name: set.name || set.species,
    species: set.species,
    item: set.item || '',
    ability: set.ability || '',
    moves: set.moves || [],
    nature: set.nature || 'Hardy',
    gender: set.gender || '',
    level: Number(set.level || 100),
    evs: normalizeStats(set.evs, 0),
    ivs: normalizeStats(set.ivs, 31),
  };
}

function teamPreviewChoice(teamLength) {
  return Array.from({length: teamLength}, (_, i) => String(i + 1)).join('');
}

function actionToChoice(action) {
  if (!action) return null;
  const index = Number(action.index);
  if (!Number.isInteger(index) || index < 0) {
    throw new Error(`Invalid action index: ${JSON.stringify(action)}`);
  }
  if (action.kind === 'move') return `move ${index + 1}`;
  if (action.kind === 'switch') return `switch ${index + 1}`;
  throw new Error(`Invalid action kind: ${JSON.stringify(action)}`);
}

function writeChoice(stream, side, action) {
  const choice = actionToChoice(action);
  if (choice) stream.write(`>${side} ${choice}`);
}

function safeName(effectOrId) {
  if (!effectOrId) return '';
  if (typeof effectOrId === 'string') return effectOrId;
  return effectOrId.name || effectOrId.id || String(effectOrId);
}

function summarizePokemon(mon, active) {
  return {
    species: safeName(mon.species) || safeName(mon.baseSpecies) || mon.name,
    name: mon.name,
    hp: mon.hp,
    max_hp: mon.maxhp,
    fainted: !!mon.fainted || mon.hp <= 0,
    status: mon.status || null,
    item: mon.item || '',
    ability: mon.ability || '',
    active: !!active,
    boosts: {...mon.boosts},
    moves: mon.moveSlots.map(slot => ({
      id: slot.id,
      move: slot.move,
      pp: slot.pp,
      maxpp: slot.maxpp,
      disabled: !!slot.disabled,
    })),
  };
}

function summarizeSide(side) {
  const activeMon = side.active?.[0] || null;
  const activeIndex = activeMon ? side.pokemon.indexOf(activeMon) : -1;
  return {
    name: side.name,
    active: activeMon ? (safeName(activeMon.species) || activeMon.name) : null,
    active_index: activeIndex,
    needs_replacement: !!side.activeRequest?.forceSwitch?.[0],
    alive_count: side.pokemon.filter(mon => !mon.fainted && mon.hp > 0).length,
    side_conditions: Object.fromEntries(Object.keys(side.sideConditions || {}).map(id => [id, true])),
    mons: side.pokemon.map(mon => summarizePokemon(mon, mon === activeMon)),
  };
}

function battleWinner(battle) {
  if (!battle.ended) return null;
  if (!battle.winner) return 0;
  if (battle.winner === battle.sides[0].name) return 1;
  if (battle.winner === battle.sides[1].name) return 2;
  return battle.winner;
}

function legalActionsFromRequest(side) {
  const request = side.activeRequest;
  if (!request) return [];

  const actions = [];
  const active = request.active?.[0];
  if (active?.moves) {
    active.moves.forEach((move, index) => {
      if (!move.disabled) actions.push({kind: 'move', index, move: move.move, id: move.id});
    });
  }

  const forceSwitch = !!request.forceSwitch?.[0];
  const canSwitch = forceSwitch || !!active;
  if (canSwitch && request.side?.pokemon) {
    request.side.pokemon.forEach((mon, index) => {
      const isActive = !!mon.active;
      const fainted = typeof mon.condition === 'string' && mon.condition.startsWith('0 ');
      if (!isActive && !fainted) actions.push({kind: 'switch', index, species: mon.details.split(',')[0]});
    });
  }

  return actions;
}

function stateSummary(battle, format, seed, historyLength) {
  return {
    backend: 'showdown',
    format,
    seed,
    showdown_seed: battle.prngSeed,
    turn: battle.turn,
    ended: !!battle.ended,
    winner: battleWinner(battle),
    weather: battle.field?.weather || null,
    terrain: battle.field?.terrain || null,
    history_length: historyLength,
    p1: summarizeSide(battle.sides[0]),
    p2: summarizeSide(battle.sides[1]),
  };
}

function loadShowdown(showdownRoot) {
  const simIndex = path.join(showdownRoot, 'dist', 'sim', 'index.js');
  const requireFromShowdown = createRequire(path.join(showdownRoot, 'package.json'));
  return requireFromShowdown(simIndex);
}

function runBattle(payload) {
  const availability = checkPayload();
  if (!availability.available) {
    return {ok: false, ...availability};
  }

  const showdownRoot = resolveShowdownRoot();
  const {BattleStream, Teams} = loadShowdown(showdownRoot);

  const format = payload.format || payload.format_id || 'gen5ou';
  const seed = toPRNGSeed(payload.seed ?? 1);
  const team1 = (payload.team1 || []).map(toShowdownSet);
  const team2 = (payload.team2 || []).map(toShowdownSet);
  const history = payload.actions || payload.history || [];

  if (!team1.length || !team2.length) {
    throw new Error('Payload must include non-empty team1 and team2 arrays.');
  }

  const stream = new BattleStream({debug: !!payload.debug, noCatch: true});
  stream.write(
    `>start ${JSON.stringify({formatid: format, seed})}\n` +
    `>player p1 ${JSON.stringify({name: 'p1', team: Teams.pack(team1)})}\n` +
    `>player p2 ${JSON.stringify({name: 'p2', team: Teams.pack(team2)})}`
  );

  if (stream.battle?.sides?.[0]?.activeRequest?.teamPreview) {
    stream.write(`>p1 team ${teamPreviewChoice(team1.length)}\n>p2 team ${teamPreviewChoice(team2.length)}`);
  }

  for (const event of history) {
    const lines = [];
    const p1Choice = actionToChoice(event.p1);
    const p2Choice = actionToChoice(event.p2);
    if (p1Choice) lines.push(`>p1 ${p1Choice}`);
    if (p2Choice) lines.push(`>p2 ${p2Choice}`);
    if (lines.length) stream.write(lines.join('\n'));
  }

  const battle = stream.battle;
  if (!battle) throw new Error('BattleStream did not create a battle.');

  return {
    ok: true,
    available: true,
    state_summary: stateSummary(battle, format, payload.seed ?? 1, history.length),
    winner: battleWinner(battle),
    log_lines: [...battle.log],
    requests: {
      p1: battle.sides[0].activeRequest || null,
      p2: battle.sides[1].activeRequest || null,
    },
    legal_actions: {
      p1: legalActionsFromRequest(battle.sides[0]),
      p2: legalActionsFromRequest(battle.sides[1]),
    },
    needs_replacement: {
      p1: !!battle.sides[0].activeRequest?.forceSwitch?.[0],
      p2: !!battle.sides[1].activeRequest?.forceSwitch?.[0],
    },
    raw: {
      input_log: [...battle.inputLog],
      prng_seed: battle.prngSeed,
    },
  };
}

async function main() {
  if (process.argv.includes('--check')) {
    check();
    return;
  }

  try {
    const stdin = await readStdin();
    const payload = stdin.trim() ? JSON.parse(stdin) : {};
    const result = runBattle(payload);
    jsonOut(result);
    process.exit(result.ok ? 0 : 2);
  } catch (error) {
    jsonOut({
      ok: false,
      available: false,
      reason: error?.message || String(error),
      stack: process.env.SHOWDOWN_BRIDGE_DEBUG ? error?.stack : undefined,
    });
    process.exit(1);
  }
}

void main();
