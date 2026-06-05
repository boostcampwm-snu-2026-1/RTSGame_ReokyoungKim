import { useEffect, useRef } from 'react'

const TILE = 512
const TEAM_COLORS = { 1: '#3b82f6', 2: '#ef4444' }
const MAX = 360

export default function MiniMap({ config, mapMeta }) {
  const canvasRef = useRef(null)
  const placement = config.unit_placement || {}

  // World size in pixels: from map size (tiles * 512), else inferred from units.
  let worldW = mapMeta?.size ? mapMeta.size[0] * TILE : 0
  let worldH = mapMeta?.size ? mapMeta.size[1] * TILE : 0
  if (!worldW || !worldH) {
    let maxX = 0, maxY = 0
    for (const units of Object.values(placement)) {
      if (!Array.isArray(units)) continue
      for (const entry of units) {
        const pos = entry?.[1]
        if (Array.isArray(pos)) {
          maxX = Math.max(maxX, pos[0])
          maxY = Math.max(maxY, pos[1])
        }
      }
    }
    worldW = Math.max(maxX * 1.1, TILE)
    worldH = Math.max(maxY * 1.1, TILE)
  }

  const scale = Math.min(MAX / worldW, MAX / worldH)
  const cw = Math.max(120, Math.round(worldW * scale))
  const ch = Math.max(120, Math.round(worldH * scale))

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    ctx.clearRect(0, 0, cw, ch)

    // background + grid
    ctx.fillStyle = '#0f172a'
    ctx.fillRect(0, 0, cw, ch)
    ctx.strokeStyle = 'rgba(148,163,184,0.15)'
    ctx.lineWidth = 1
    const tilePx = TILE * scale
    for (let x = 0; x <= cw; x += tilePx) {
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, ch); ctx.stroke()
    }
    for (let y = 0; y <= ch; y += tilePx) {
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(cw, y); ctx.stroke()
    }

    // units
    for (const [team, units] of Object.entries(placement)) {
      if (!Array.isArray(units)) continue
      ctx.fillStyle = TEAM_COLORS[team] || '#a3a3a3'
      for (const entry of units) {
        const pos = entry?.[1]
        if (!Array.isArray(pos)) continue
        const px = pos[0] * scale
        const py = pos[1] * scale
        ctx.globalAlpha = 0.85
        ctx.beginPath()
        ctx.arc(px, py, 4, 0, Math.PI * 2)
        ctx.fill()
      }
    }
    ctx.globalAlpha = 1
  }, [config, mapMeta, cw, ch, scale])

  return (
    <div className="card minimap">
      <h2>미니맵</h2>
      <canvas ref={canvasRef} width={cw} height={ch} className="minimap-canvas" />
      <div className="legend">
        <span><i className="dot" style={{ background: TEAM_COLORS[1] }} /> 팀 1</span>
        <span><i className="dot" style={{ background: TEAM_COLORS[2] }} /> 팀 2</span>
        <span className="muted">
          {mapMeta?.size ? `맵 ${mapMeta.size[0]}×${mapMeta.size[1]} 타일` : '맵 크기 추정값'}
        </span>
      </div>
    </div>
  )
}
