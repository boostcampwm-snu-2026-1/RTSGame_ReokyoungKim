import { useEffect, useState } from 'react'
import { getCatalog, generate } from './api'
import PromptInput from './components/PromptInput'
import ConfigSummary from './components/ConfigSummary'
import MiniMap from './components/MiniMap'
import SimPlayback from './components/SimPlayback'
import JsonView from './components/JsonView'

export default function App() {
  const [catalog, setCatalog] = useState({ scenarios: [], maps: [] })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)

  useEffect(() => {
    getCatalog()
      .then(setCatalog)
      .catch((e) => console.warn('catalog load failed', e))
  }, [])

  async function handleGenerate(query) {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await generate(query)
      if (res.error || !res.config) {
        setError(res.error || 'No config was generated for this prompt.')
      } else {
        setResult(res)
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const config = result?.config
  const mapMeta = config
    ? catalog.maps.find(
        (m) => m.name && config.information?.map_name &&
          config.information.map_name.toLowerCase().includes(m.name.toLowerCase().split(' ')[0]),
      )
    : null

  return (
    <div className="app">
      <header className="header">
        <h1>RTSGame Minigame Generator</h1>
      </header>

      <PromptInput
        loading={loading}
        scenarios={catalog.scenarios}
        onGenerate={handleGenerate}
      />

      {error && <div className="error">⚠️ {error}</div>}

      {loading && <div className="loading">생성 중… (DB 매칭 → 스크립트 작성)</div>}

      {result && config && (
        <div className="result">
          <div className="result-top">
            <ConfigSummary config={config} scenario={result.scenario} />
            <MiniMap config={config} mapMeta={mapMeta} />
          </div>
          <SimPlayback config={config} mapMeta={mapMeta} />
          <JsonView config={config} scenario={result.scenario} />
        </div>
      )}
    </div>
  )
}
