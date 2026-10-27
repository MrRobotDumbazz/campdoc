import type { Metrics, SimulateResponse } from '../api/types'

export interface SimState {
  status: 'loading' | 'done' | 'error'
  seed: number
  result?: SimulateResponse
  error?: string
}

interface Props {
  state: SimState
  onRerun: () => void
}

const METRICS: { key: keyof Metrics; label: string; fmt: (v: number) => string }[] = [
  { key: 'impressions', label: 'Impressions', fmt: (v) => v.toLocaleString('ru-RU') },
  { key: 'spend', label: 'Spend', fmt: (v) => `$${v.toFixed(2)}` },
  { key: 'win_rate', label: 'Win rate', fmt: (v) => `${(v * 100).toFixed(1)}%` },
  { key: 'ecpm', label: 'eCPM', fmt: (v) => `$${v.toFixed(2)}` },
]

function fmtDelta(v: number, fmt: (n: number) => string): string {
  return `${v > 0 ? '+' : ''}${fmt(v)}`
}

export default function SimView({ state, onRerun }: Props) {
  if (state.status === 'loading') {
    return (
      <div className="sim-box loading">
        <span className="spinner" /> Симуляция (seed {state.seed})…
      </div>
    )
  }

  if (state.status === 'error' || !state.result) {
    return (
      <div className="sim-box">
        <div className="error-box tight">Ошибка симуляции: {state.error}</div>
        <button className="sim-btn" onClick={onRerun}>
          Повторить
        </button>
      </div>
    )
  }

  const r = state.result
  return (
    <div className="sim-box">
      <div className="sim-head">
        <span className={`sim-badge ${r.verified ? 'verified' : 'unverified'}`}>
          {r.verified ? 'verified' : 'unverified'}
        </span>
        <span className="sim-threshold">
          порог Δ≥{r.threshold_pct}%
        </span>
        <button className="sim-btn small" onClick={onRerun}>
          новый seed
        </button>
      </div>
      <div className="sim-table">
        <div className="sim-th">Метрика</div>
        <div className="sim-th">Before</div>
        <div className="sim-th">After</div>
        <div className="sim-th">Δ</div>
        {METRICS.flatMap((m) => [
          <div key={`n-${m.key}`} className="sim-metric-name">
            {m.label}
          </div>,
          <div key={`b-${m.key}`}>{m.fmt(r.before[m.key])}</div>,
          <div key={`a-${m.key}`}>{m.fmt(r.after[m.key])}</div>,
          <div key={`d-${m.key}`} className="sim-delta">
            {fmtDelta(r.delta[m.key], m.fmt)}
          </div>,
        ])}
      </div>
      {r.violated_constraints.length > 0 && (
        <ul className="sim-violations">
          {r.violated_constraints.map((c) => (
            <li key={c}>constraint нарушен: {c}</li>
          ))}
        </ul>
      )}
      <ul className="sim-notes">
        {r.notes.map((n) => (
          <li key={n}>{n}</li>
        ))}
      </ul>
    </div>
  )
}
