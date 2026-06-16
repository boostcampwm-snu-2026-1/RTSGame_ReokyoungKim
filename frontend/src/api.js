// In dev, calls go through the Vite proxy (/api -> http://localhost:8000).
// In production set VITE_API_BASE to the deployed backend origin
// (e.g. https://rtsgame-backend.onrender.com) at build time.
// Strip any trailing slash so VITE_API_BASE="https://host/" doesn't produce a
// double slash ("//generate") that the backend 404s on.
const BASE = (import.meta.env.VITE_API_BASE ?? '/api').replace(/\/+$/, '')

// /launch opens the real game on the machine running the backend, so it must
// hit a backend with BAR installed. Defaults to the same backend as everything
// else (local single-process). On a cloud deploy set
// VITE_LAUNCH_BASE=http://localhost:8000 to route launch to the user's own
// local backend while generation stays on the cloud.
const LAUNCH_BASE = (import.meta.env.VITE_LAUNCH_BASE ?? BASE).replace(/\/+$/, '')

export async function getCatalog() {
  const res = await fetch(`${BASE}/catalog`)
  if (!res.ok) throw new Error(`catalog failed: ${res.status}`)
  return res.json()
}

export async function generate(query, seed) {
  const res = await fetch(`${BASE}/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, seed }),
  })
  if (!res.ok) throw new Error(`generate failed: ${res.status}`)
  return res.json()
}

// Launch the generated config in the actual BAR client (via the v4 simulator).
export async function launch(config, mode = 'gadget') {
  const res = await fetch(`${LAUNCH_BASE}/launch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ config, mode }),
  })
  if (!res.ok) throw new Error(`launch failed: ${res.status}`)
  return res.json()
}
