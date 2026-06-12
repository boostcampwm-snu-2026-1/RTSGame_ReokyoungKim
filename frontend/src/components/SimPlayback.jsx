import { useEffect, useMemo, useRef, useState } from 'react'
import {
  TILE, SIM_FPS,
  statFor, worldSize, findSpawner, victoryTime, makeUnit, buildUnits,
} from '../lib/simModel'

const MAX = 360
const TEAM_COLORS = { 1: '#3b82f6', 2: '#ef4444' }

export default function SimPlayback({ config, mapMeta }) {
  const canvasRef = useRef(null)
  const stateRef = useRef(null)
  const rafRef = useRef(0)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(4)
  const [hud, setHud] = useState({ t: 0, a: 0, b: 0, status: null })

  const [worldW, worldH] = useMemo(() => worldSize(config, mapMeta), [config, mapMeta])
  const scale = Math.min(MAX / worldW, MAX / worldH)
  const cw = Math.max(120, Math.round(worldW * scale))
  const ch = Math.max(120, Math.round(worldH * scale))

  const spawner = useMemo(() => findSpawner(config.customize), [config])
  const winTime = useMemo(() => victoryTime(config.end_condition), [config])
  const center = [worldW / 2, worldH / 2]

  function reset() {
    cancelAnimationFrame(rafRef.current)
    setPlaying(false)
    stateRef.current = {
      units: buildUnits(config),
      t: 0,
      wavesSpawned: 0,
      status: null,
    }
    refreshHud()
    draw()
  }

  function refreshHud() {
    const s = stateRef.current
    if (!s) return
    const a = s.units.filter((u) => u.team === '1').length
    const b = s.units.filter((u) => u.team !== '1').length
    setHud({ t: Math.floor(s.t), a, b, status: s.status })
  }

  function step(dt) {
    const s = stateRef.current
    if (!s || s.status) return
    s.t += dt

    // wave spawning (frames -> seconds)
    if (spawner) {
      const interval = (spawner.waveIntervalFrames || 1800) / SIM_FPS
      const first = (spawner.firstWaveFrame ?? spawner.waveIntervalFrames ?? 1800) / SIM_FPS
      const maxWaves = spawner.maxWaves ?? 999
      const team = String(spawner.spawnTeamID ?? 2)
      const code = spawner.unitName || 'enemy'
      const due = s.t >= first ? Math.floor((s.t - first) / interval) + 1 : 0
      while (s.wavesSpawned < due && s.wavesSpawned < maxWaves) {
        const count = (spawner.startCount ?? 4) + (spawner.addPerWave ?? 2) * s.wavesSpawned
        // spawn from a deterministic edge (by wave index)
        const edge = s.wavesSpawned % 4
        for (let i = 0; i < count; i++) {
          const jitter = (i - count / 2) * 60
          let x, y
          if (edge === 0) { x = 0; y = worldH / 2 + jitter }
          else if (edge === 1) { x = worldW; y = worldH / 2 + jitter }
          else if (edge === 2) { x = worldW / 2 + jitter; y = 0 }
          else { x = worldW / 2 + jitter; y = worldH }
          s.units.push(makeUnit(team, code, x, y))
        }
        s.wavesSpawned++
      }
    }

    // movement + combat — each unit uses its own real speed / range / dps
    for (const u of s.units) {
      u.firing = false
      // nearest living enemy
      let tgt = null, best = Infinity
      for (const e of s.units) {
        if (e.team === u.team || e.hp <= 0) continue
        const d = (e.x - u.x) ** 2 + (e.y - u.y) ** 2
        if (d < best) { best = d; tgt = e }
      }
      const aim = tgt || { x: center[0], y: center[1] }
      const dx = aim.x - u.x, dy = aim.y - u.y
      const dist = Math.hypot(dx, dy) || 1
      if (tgt && u.dps > 0 && dist <= u.range) {
        tgt.hp -= u.dps * dt // in range and armed: attack
        u.firing = true
      } else if (!u.struct && u.speed > 0) {
        const v = u.speed * dt
        u.x += (dx / dist) * Math.min(v, dist)
        u.y += (dy / dist) * Math.min(v, dist)
      }
    }
    s.units = s.units.filter((u) => u.hp > 0)

    // win/lose
    const teamA = s.units.filter((u) => u.team === '1').length
    const teamB = s.units.filter((u) => u.team !== '1').length
    const wavesDone = !spawner || s.wavesSpawned >= (spawner.maxWaves ?? 999)
    if (teamA === 0) s.status = 'DEFEAT'
    else if (winTime && s.t >= winTime) s.status = 'VICTORY'
    else if (teamB === 0 && wavesDone) s.status = 'VICTORY'
  }

  function draw() {
    const canvas = canvasRef.current
    const s = stateRef.current
    if (!canvas || !s) return
    const ctx = canvas.getContext('2d')
    ctx.fillStyle = '#0f172a'
    ctx.fillRect(0, 0, cw, ch)
    ctx.strokeStyle = 'rgba(148,163,184,0.12)'
    const tp = TILE * scale
    for (let x = 0; x <= cw; x += tp) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, ch); ctx.stroke() }
    for (let y = 0; y <= ch; y += tp) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(cw, y); ctx.stroke() }

    // attack lines (drawn under the unit dots)
    ctx.lineWidth = 1
    for (const u of s.units) {
      if (!u.firing) continue
      // re-find target purely for the visual line
      let tgt = null, best = Infinity
      for (const e of s.units) {
        if (e.team === u.team || e.hp <= 0) continue
        const d = (e.x - u.x) ** 2 + (e.y - u.y) ** 2
        if (d < best) { best = d; tgt = e }
      }
      if (!tgt) continue
      ctx.strokeStyle = u.team === '1' ? 'rgba(59,130,246,0.35)' : 'rgba(239,68,68,0.35)'
      ctx.beginPath()
      ctx.moveTo(u.x * scale, u.y * scale)
      ctx.lineTo(tgt.x * scale, tgt.y * scale)
      ctx.stroke()
    }

    for (const u of s.units) {
      const px = u.x * scale, py = u.y * scale
      // radius scales with HP: bigger, tankier units read as bigger dots
      const base = u.struct ? 4 : 2.6
      const r = base + Math.min(3, Math.log10(Math.max(u.maxHp, 1)) - 2)
      ctx.fillStyle = TEAM_COLORS[u.team] || '#a3a3a3'
      ctx.globalAlpha = u.struct ? 1 : 0.85
      if (u.struct) {
        ctx.fillRect(px - r, py - r, r * 2, r * 2)
      } else {
        ctx.beginPath(); ctx.arc(px, py, r, 0, Math.PI * 2); ctx.fill()
      }
      // damaged-unit health bar
      ctx.globalAlpha = 1
      if (u.hp < u.maxHp) {
        const w = Math.max(6, r * 2.4), frac = Math.max(0, u.hp / u.maxHp)
        ctx.fillStyle = 'rgba(15,23,42,0.8)'
        ctx.fillRect(px - w / 2, py - r - 4, w, 2)
        ctx.fillStyle = frac > 0.5 ? '#22c55e' : frac > 0.25 ? '#eab308' : '#ef4444'
        ctx.fillRect(px - w / 2, py - r - 4, w * frac, 2)
      }
    }
    ctx.globalAlpha = 1
  }

  // animation loop
  useEffect(() => {
    if (!playing) return
    let last = null
    const loop = (ts) => {
      if (last == null) last = ts
      const dt = Math.min((ts - last) / 1000, 0.05) * speed
      last = ts
      step(dt)
      draw()
      refreshHud()
      if (stateRef.current?.status) { setPlaying(false); return }
      rafRef.current = requestAnimationFrame(loop)
    }
    rafRef.current = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(rafRef.current)
  }, [playing, speed])

  // (re)build when config changes
  useEffect(() => { reset() /* eslint-disable-next-line */ }, [config, mapMeta])

  const mm = Math.floor(hud.t / 60), ss = String(hud.t % 60).padStart(2, '0')

  return (
    <div className="card sim">
      <div className="sim-head">
        <h2>플레이백</h2>
        <div className="sim-controls">
          <button className="btn" onClick={() => setPlaying((p) => !p)}>
            {playing ? '⏸ 일시정지' : '▶ 재생'}
          </button>
          <button className="btn" onClick={reset}>↺ 리셋</button>
          <select className="btn" value={speed} onChange={(e) => setSpeed(Number(e.target.value))}>
            <option value={1}>1×</option>
            <option value={4}>4×</option>
            <option value={10}>10×</option>
          </select>
        </div>
      </div>

      <canvas ref={canvasRef} width={cw} height={ch} className="minimap-canvas" />

      <div className="sim-hud">
        <span>⏱ {mm}:{ss}{winTime ? ` / ${Math.floor(winTime / 60)}:${String(winTime % 60).padStart(2, '0')}` : ''}</span>
        <span style={{ color: TEAM_COLORS[1] }}>팀1 {hud.a}</span>
        <span style={{ color: TEAM_COLORS[2] }}>팀2 {hud.b}</span>
        {spawner && <span className="muted">웨이브 {statFor(spawner.unitName || '').name}</span>}
      </div>
      <div className="muted" style={{ fontSize: '0.75rem', marginTop: 4 }}>
        실제 유닛 스탯(HP·DPS·사거리·속도) 기반 근사 시뮬레이션 — BAR 엔진 결과가 아닙니다.
      </div>

      {hud.status && (
        <div className={`sim-banner ${hud.status === 'VICTORY' ? 'win' : 'lose'}`}>
          {hud.status === 'VICTORY' ? '🏆 VICTORY (방어 성공/적 소탕)' : '💀 DEFEAT (팀1 전멸)'}
        </div>
      )}
    </div>
  )
}
