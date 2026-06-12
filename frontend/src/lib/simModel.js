// Pure simulation model for the playback view — no React, no canvas.
// Extracted from SimPlayback so the stat-driven logic can be unit-tested.
import UNIT_STATS from '../data/unitStats.json'

export const TILE = 512
export const SIM_FPS = 30 // BAR runs the sim at ~30 frames/sec

// DPS in the stat table is the in-engine burst value; the commander's d-gun
// (~111k) would one-shot the whole map, so cap it to keep playback watchable.
export const DPS_CAP = 800

// Fallbacks when a code is missing from the stat table.
const DEFAULT_MOBILE = { hp: 100, dps: 35, range: TILE * 0.7, speed: 60, struct: false }
const DEFAULT_STRUCT = { hp: 600, dps: 0, range: 0, speed: 0, struct: true }
const STRUCT_HINTS = ['lab', 'vp', 'ap', 'hp', 'llt', 'hlt', 'tower', 'nano', 'solar', 'fus', 'mex', 'estor', 'mstor', 'wind', 'tide', 'geo', 'rad']

// Look up real stats by unit code (armcom, armwar, ...). Falls back to sane
// defaults; treats codes ending in common structure suffixes as buildings.
export function statFor(code = '') {
  const s = UNIT_STATS[code]
  if (s) {
    return {
      name: s.name,
      hp: s.hp || 100,
      dps: Math.min(s.dps || 0, DPS_CAP),
      range: s.range || (s.struct ? 0 : TILE * 0.7),
      speed: s.struct ? 0 : s.speed || 60,
      struct: !!s.struct,
    }
  }
  const looksStruct = STRUCT_HINTS.some((h) => code.toLowerCase().includes(h))
  return { name: code, ...(looksStruct ? DEFAULT_STRUCT : DEFAULT_MOBILE) }
}

// World size in pixels: from map size (tiles*512), else inferred from unit coords.
export function worldSize(config, mapMeta) {
  if (mapMeta?.size) return [mapMeta.size[0] * TILE, mapMeta.size[1] * TILE]
  let mx = 0, my = 0
  for (const units of Object.values(config.unit_placement || {})) {
    if (!Array.isArray(units)) continue
    for (const u of units) {
      const p = u?.[1]
      if (Array.isArray(p)) { mx = Math.max(mx, p[0]); my = Math.max(my, p[1]) }
    }
  }
  return [Math.max(mx * 1.1, TILE), Math.max(my * 1.1, TILE)]
}

// Detect a wave-spawner gadget config inside `customize`.
export function findSpawner(customize = {}) {
  for (const cfg of Object.values(customize)) {
    if (cfg && typeof cfg === 'object' &&
        ('waveIntervalFrames' in cfg || ('unitName' in cfg && 'startCount' in cfg))) {
      return cfg
    }
  }
  return null
}

// Parse the victory time (in seconds) from an end_condition block, or null.
export function victoryTime(end = {}) {
  const vc = end.victory_condition
  if (!Array.isArray(vc)) return null
  const mapping = vc[1]
  if (mapping && mapping.time) {
    const expr = Array.isArray(mapping.time) ? mapping.time[0] : mapping.time
    const m = String(expr).match(/(\d+)/)
    if (m) return parseInt(m[1], 10)
  }
  return null
}

export function makeUnit(team, code, x, y) {
  const st = statFor(code)
  return {
    team, code, name: st.name,
    x, y,
    hp: st.hp, maxHp: st.hp,
    dps: st.dps, range: st.range, speed: st.speed,
    struct: st.struct,
    firing: false,
  }
}

export function buildUnits(config) {
  const out = []
  for (const [team, units] of Object.entries(config.unit_placement || {})) {
    if (!Array.isArray(units)) continue
    for (const u of units) {
      const code = u?.[0]
      const p = u?.[1]
      if (!Array.isArray(p)) continue
      out.push(makeUnit(team, code, p[0], p[1]))
    }
  }
  return out
}
