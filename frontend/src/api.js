// All calls go through the Vite proxy (/api -> http://localhost:8000).
const BASE = '/api'

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
