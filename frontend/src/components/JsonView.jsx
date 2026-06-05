import { useState } from 'react'

export default function JsonView({ config, scenario }) {
  const [copied, setCopied] = useState(false)
  const text = JSON.stringify(config, null, 2)

  function download() {
    const blob = new Blob([text], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    const safe = (scenario || 'config').replace(/[^a-z0-9_-]+/gi, '_')
    a.href = url
    a.download = `${safe}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="card json-view">
      <div className="json-head">
        <h2>config (JSON)</h2>
        <div className="json-actions">
          <button className="btn" onClick={copy}>{copied ? '복사됨 ✓' : '복사'}</button>
          <button className="btn primary" onClick={download}>JSON 다운로드</button>
        </div>
      </div>
      <pre className="json-pre">{text}</pre>
    </div>
  )
}
