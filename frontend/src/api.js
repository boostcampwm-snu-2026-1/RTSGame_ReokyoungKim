// In dev, calls go through the Vite proxy (/api -> http://localhost:8000).
// In production set VITE_API_BASE to the deployed backend origin
// (e.g. https://rtsgame-backend.onrender.com) at build time.
const BASE = import.meta.env.VITE_API_BASE ?? '/api'

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
  const res = await fetch(`${BASE}/launch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ config, mode }),
  })
  if (!res.ok) throw new Error(`launch failed: ${res.status}`)
  return res.json()
}
