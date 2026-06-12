import { describe, it, expect } from 'vitest'
import {
  DPS_CAP, statFor, victoryTime, findSpawner, buildUnits,
} from './simModel'

describe('statFor', () => {
  it('returns real engine stats for a known unit', () => {
    const s = statFor('armwar') // Centurion
    expect(s.name).toBe('Centurion')
    expect(s.hp).toBe(1590)
    expect(s.struct).toBe(false)
  })

  it('caps absurd burst DPS (commander d-gun) at DPS_CAP', () => {
    // armcom's raw DPS is ~111498; it must be clamped so it does not one-shot the map.
    expect(statFor('armcom').dps).toBe(DPS_CAP)
  })

  it('treats speed-0 / building-category units as structures', () => {
    const s = statFor('armllt') // Sentry turret, speed 0
    expect(s.struct).toBe(true)
    expect(s.speed).toBe(0)
  })

  it('falls back to mobile defaults for an unknown code', () => {
    const s = statFor('totallymadeup')
    expect(s.struct).toBe(false)
    expect(s.dps).toBe(35)
  })

  it('falls back to structure defaults for an unknown structure-like code', () => {
    expect(statFor('xyz_llt_thing').struct).toBe(true)
  })
})

describe('victoryTime', () => {
  it('parses the time threshold from an end_condition', () => {
    expect(victoryTime({ victory_condition: ['and', { time: ['>= 1200'] }] })).toBe(1200)
  })

  it('returns null when there is no time condition', () => {
    expect(victoryTime({ victory_condition: ['or', { 1: ['armcom == 0'] }] })).toBeNull()
    expect(victoryTime({})).toBeNull()
  })
})

describe('findSpawner', () => {
  it('detects a wave-spawner gadget config', () => {
    const spawner = { waveIntervalFrames: 1800, unitName: 'armpw', startCount: 4 }
    expect(findSpawner({ enemy_wave_spawner: spawner })).toBe(spawner)
  })

  it('returns null when no spawner is present', () => {
    expect(findSpawner({ prioritize_target: { mode: 'closest' } })).toBeNull()
    expect(findSpawner({})).toBeNull()
  })
})

describe('buildUnits', () => {
  it('flattens unit_placement into stat-carrying units', () => {
    const units = buildUnits({
      unit_placement: { 1: [['armcom', [100, 200]]], 2: [['armwar', [300, 400]]] },
    })
    expect(units).toHaveLength(2)
    expect(units[0]).toMatchObject({ team: '1', code: 'armcom', x: 100, y: 200 })
    expect(units[0].maxHp).toBe(units[0].hp)
    expect(units[1]).toMatchObject({ team: '2', code: 'armwar' })
  })

  it('skips malformed entries without coordinates', () => {
    expect(buildUnits({ unit_placement: { 1: [['armcom']] } })).toHaveLength(0)
  })
})
