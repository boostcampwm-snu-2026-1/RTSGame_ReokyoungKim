import { useState } from 'react'

const EXAMPLES = [
  '중앙 기지를 20분간 사방의 적 웨이브로부터 방어하라',
  '제한 시간 내에 적 방어선을 뚫고 목표 건물을 파괴하라',
  '자원이 제한된 상태에서 목표 건물을 건설하며 버텨라',
]

export default function PromptInput({ loading, scenarios, onGenerate }) {
  const [query, setQuery] = useState('')

  function submit(e) {
    e.preventDefault()
    const q = query.trim()
    if (q && !loading) onGenerate(q)
  }

  return (
    <form className="prompt" onSubmit={submit}>
      <textarea
        className="prompt-input"
        placeholder="만들고 싶은 미니게임을 설명하세요…"
        value={query}
        rows={3}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) submit(e)
        }}
      />
      <div className="prompt-row">
        <div className="examples">
          {EXAMPLES.map((ex) => (
            <button
              type="button"
              key={ex}
              className="chip"
              onClick={() => setQuery(ex)}
              disabled={loading}
            >
              {ex}
            </button>
          ))}
        </div>
        <button className="generate-btn" type="submit" disabled={loading || !query.trim()}>
          {loading ? '생성 중…' : '생성 (⌘/Ctrl+Enter)'}
        </button>
      </div>
    </form>
  )
}
