function formatCondition(cond) {
  // Expected shape: [op, { key: [exprs...] }]  e.g. ["and", { time: [">= 1200"] }]
  if (!Array.isArray(cond)) {
    if (typeof cond === 'string') return [cond]
    return []
  }
  const [op, mapping] = cond
  const lines = []
  if (mapping && typeof mapping === 'object') {
    for (const [key, exprs] of Object.entries(mapping)) {
      const arr = Array.isArray(exprs) ? exprs : [exprs]
      arr.forEach((e) => lines.push(`${key}: ${e}`))
    }
  }
  return lines.length > 1 ? lines.map((l) => `(${op}) ${l}`) : lines
}

export default function ConfigSummary({ config, scenario }) {
  const info = config.information || {}
  const end = config.end_condition || {}
  const placement = config.unit_placement || {}
  const customize = config.customize || {}

  const descriptions = Array.isArray(info.description)
    ? info.description
    : info.description
      ? [info.description]
      : []

  const teamCounts = Object.entries(placement).map(([team, units]) => ({
    team,
    count: Array.isArray(units) ? units.length : 0,
  }))

  return (
    <div className="card summary">
      <h2>요약</h2>

      <div className="kv">
        <span className="k">매칭된 시나리오</span>
        <span className="v badge">{scenario}</span>
      </div>
      <div className="kv">
        <span className="k">맵</span>
        <span className="v">{info.map_name || '—'}</span>
      </div>
      <div className="kv">
        <span className="k">포맷 / 난이도</span>
        <span className="v">{info.match_format || '—'} · {info.difficulty || 'normal'}</span>
      </div>
      <div className="kv">
        <span className="k">전장의 안개</span>
        <span className="v">{info.fog_of_war ? 'ON' : 'OFF'}</span>
      </div>

      {descriptions.length > 0 && (
        <div className="block">
          <div className="block-title">설명</div>
          <ul className="desc-list">
            {descriptions.map((d, i) => (
              <li key={i}>{d}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="block">
        <div className="block-title">승리 조건</div>
        <ul className="cond-list win">
          {formatCondition(end.victory_condition).map((l, i) => <li key={i}>{l}</li>)}
          {!end.victory_condition && end.victory && <li>{end.victory}</li>}
        </ul>
        <div className="block-title">패배 조건</div>
        <ul className="cond-list lose">
          {formatCondition(end.defeat_condition).map((l, i) => <li key={i}>{l}</li>)}
          {!end.defeat_condition && end.defeat && <li>{end.defeat}</li>}
        </ul>
      </div>

      <div className="block">
        <div className="block-title">유닛 배치</div>
        <div className="team-counts">
          {teamCounts.map(({ team, count }) => (
            <span key={team} className={`team-pill team-${team}`}>
              팀 {team}: {count}기
            </span>
          ))}
        </div>
      </div>

      {Object.keys(customize).length > 0 && (
        <div className="block">
          <div className="block-title">Gadget (DB 기존 rule)</div>
          <div className="gadgets">
            {Object.keys(customize).map((g) => (
              <span key={g} className="gadget-pill">{g}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
