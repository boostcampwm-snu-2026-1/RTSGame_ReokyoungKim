import { useEffect, useMemo, useRef, useState } from 'react'

const TILE = 512
const SIM_FPS = 30 // BAR runs the sim at ~30 frames/sec
const MAX = 360
const TEAM_COLORS = { 1: '#3b82f6', 2: '#ef4444' }

// crude structure/mobile classifier from unit code suffixes
const STRUCTURE_HINTS = ['lab', 'solar', 'mex', 'rad', 'llt', 'hlt', 'nano', 'fus', 'estor', 'mstor', 'wind', 'tide', 'geo', 'com']
const isStructure = (code = '') => STRUCTURE_HINTS.some((h) => code.toLowerCase().includes(h))

// ---- read world size (tiles*512) or infer from unit coords ----
function worldSize(config, mapMeta) {
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

// ---- detect a wave spawner gadget in customize ----
function findSpawner(customize = {}) {
  for (const cfg of Object.values(customize)) {
    if (cfg && typeof cfg === 'object' &&
        ('waveIntervalFrames' in cfg || ('unitName' in cfg && 'startCount' in cfg))) {
      return cfg
    }
  }
  return null
}

// ---- parse victory time (seconds) from end_condition ----
function victoryTime(end = {}) {
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

function buildUnits(config) {
  const out = []
  for (const [team, units] of Object.entries(config.unit_placement || {})) {
    if (!Array.isArray(units)) continue
    for (const u of units) {
      const code = u?.[0]
      const p = u?.[1]
      if (!Array.isArray(p)) continue
      const struct = isStructure(code)
      out.push({
        team, code,
        x: p[0], y: p[1],
        hp: struct ? 240 : 100,
        struct,
      })
    }
  }
  return out
}

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
      const due = s.t >= first ? Math.floor((s.t - first) / interval) + 1 : 0
      while (s.wavesSpawned < due && s.wavesSpawned < maxWaves) {
        const count = (spawner.startCount ?? 4) + (spawner.addPerWave ?? 2) * s.wavesSpawned
        // spawn from a random-ish edge (deterministic by wave index)
        const edge = s.wavesSpawned % 4
        for (let i = 0; i < count; i++) {
          const jitter = (i - count / 2) * 60
          let x, y
          if (edge === 0) { x = 0; y = worldH / 2 + jitter }
          else if (edge === 1) { x = worldW; y = worldH / 2 + jitter }
          else if (edge === 2) { x = worldW / 2 + jitter; y = 0 }
          else { x = worldW / 2 + jitter; y = worldH }
          s.units.push({ team, code: spawner.unitName || 'enemy', x, y, hp: 100, struct: false })
        }
        s.wavesSpawned++
      }
    }

    const moveSpeed = Math.max(worldW, worldH) / 45 // cross map in ~45s
    const attackRange = TILE * 0.7
    const dps = 35

    // movement + combat
    for (const u of s.units) {
      // nearest enemy
      let tgt = null, best = Infinity
      for (const e of s.units) {
        if (e.team === u.team || e.hp <= 0) continue
        const d = (e.x - u.x) ** 2 + (e.y - u.y) ** 2
        if (d < best) { best = d; tgt = e }
      }
      const aim = tgt || { x: center[0], y: center[1] }
      const dx = aim.x - u.x, dy = aim.y - u.y
      const dist = Math.hypot(dx, dy) || 1
      if (tgt && dist <= attackRange) {
        tgt.hp -= dps * dt // in range: attack
      } else if (!u.struct) {
        const v = moveSpeed * dt
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
    for (const u of s.units) {
      ctx.fillStyle = TEAM_COLORS[u.team] || '#a3a3a3'
      ctx.globalAlpha = u.struct ? 1 : 0.8
      const r = u.struct ? 4.5 : 3
      if (u.struct) {
        ctx.fillRect(u.x * scale - r, u.y * scale - r, r * 2, r * 2)
      } else {
        ctx.beginPath(); ctx.arc(u.x * scale, u.y * scale, r, 0, Math.PI * 2); ctx.fill()
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
        {spawner && <span className="muted">웨이브 {spawner.unitName}</span>}
      </div>

      {hud.status && (
        <div className={`sim-banner ${hud.status === 'VICTORY' ? 'win' : 'lose'}`}>
          {hud.status === 'VICTORY' ? '🏆 VICTORY (방어 성공/적 소탕)' : '💀 DEFEAT (팀1 전멸)'}
        </div>
      )}
    </div>
  )
}
