import { useEffect, useState } from 'react'
import { getCatalog, generate, launch } from './api'
import PromptInput from './components/PromptInput'
import ConfigSummary from './components/ConfigSummary'
import MiniMap from './components/MiniMap'
import SimPlayback from './components/SimPlayback'
import JsonView from './components/JsonView'

// Map backend error codes / raw messages to friendly Korean text.
function friendlyError(err) {
  const map = {
    no_matching_scenario: '비슷한 시나리오를 찾지 못했어요. 프롬프트를 조금 더 구체적으로 적어보세요.',
    failed_to_load_scenario: '시나리오 데이터를 불러오지 못했어요. 잠시 후 다시 시도해주세요.',
  }
  if (map[err]) return map[err]
  if (typeof err === 'string' && /failed to fetch|networkerror|load failed/i.test(err)) {
    return '백엔드에 연결하지 못했어요. 서버가 실행 중인지 확인해주세요 (localhost:8000).'
  }
  return `생성에 실패했어요: ${err}`
}

export default function App() {
  const [catalog, setCatalog] = useState({ scenarios: [], maps: [] })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)
  const [lastQuery, setLastQuery] = useState('')
  const [launching, setLaunching] = useState(false)
  const [launchMsg, setLaunchMsg] = useState(null)

  useEffect(() => {
    getCatalog()
      .then(setCatalog)
      .catch((e) => console.warn('catalog load failed', e))
  }, [])

  async function handleLaunch() {
    if (!config) return
    setLaunching(true)
    setLaunchMsg(null)
    try {
      const res = await launch(config)
      if (res.launched) {
        const g = res.gadgets?.length ? ` · 룰: ${res.gadgets.join(', ')}` : ''
        setLaunchMsg({ ok: true, text: `BAR 실행 요청됨 (맵: ${res.map}${g}). 게임 창이 곧 뜹니다.` })
      } else {
        setLaunchMsg({ ok: false, text: `실행 실패: ${res.error || '알 수 없는 오류'}` })
      }
    } catch (e) {
      // Most common cause on the deployed site: launch is routed to the user's
      // local backend, which isn't running.
      setLaunchMsg({
        ok: false,
        text: `로컬 백엔드에 연결하지 못했어요. 내 PC에서 start_local.bat을 실행해 켜두세요. (${e.message})`,
      })
    } finally {
      setLaunching(false)
    }
  }

  async function handleGenerate(query) {
    setLastQuery(query)
    setLoading(true)
    setError(null)
    setResult(null)
    setLaunchMsg(null)
    try {
      const res = await generate(query)
      if (res.error || !res.config) {
        setError(friendlyError(res.error || 'no_matching_scenario'))
      } else {
        setResult(res)
      }
    } catch (e) {
      setError(friendlyError(e.message))
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

      {error && !loading && (
        <div className="error">
          <span>⚠️ {error}</span>
          {lastQuery && (
            <button className="btn retry" onClick={() => handleGenerate(lastQuery)}>
              다시 시도
            </button>
          )}
        </div>
      )}

      {loading && (
        <div className="loading">
          <span className="spinner" aria-hidden="true" />
          생성 중… (DB 매칭 → 스크립트 작성)
        </div>
      )}

      {result && config && (
        <div className="result">
          <div className="result-top">
            <ConfigSummary config={config} scenario={result.scenario} />
            <MiniMap config={config} mapMeta={mapMeta} />
          </div>

          <div className="launch-bar">
            <button className="btn primary" onClick={handleLaunch} disabled={launching}>
              {launching ? '⏳ 실행 중…' : '🎮 BAR에서 실행'}
            </button>
            <span className="muted">실제 Beyond All Reason 엔진으로 이 시나리오를 띄웁니다.</span>
            {launchMsg && (
              <span className={launchMsg.ok ? 'launch-ok' : 'launch-err'}>
                {launchMsg.ok ? '✅ ' : '⚠️ '}{launchMsg.text}
              </span>
            )}
          </div>

          <SimPlayback config={config} mapMeta={mapMeta} />
          <JsonView config={config} scenario={result.scenario} />
        </div>
      )}
    </div>
  )
}
