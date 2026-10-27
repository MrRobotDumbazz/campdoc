import { useEffect, useRef } from 'react'
import type { Investigation } from '../api/types'

interface Props {
  investigation: Investigation | null
  error?: string
}

function fmtTime(ts: string): string {
  return new Date(ts).toLocaleTimeString('ru-RU', { hour12: false })
}

export default function TracePanel({ investigation, error }: Props) {
  const listRef = useRef<HTMLDivElement>(null)
  const count = investigation?.trace.length ?? 0

  useEffect(() => {
    const el = listRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [count])

  return (
    <aside className="trace-panel">
      <div className="trace-panel-header">
        Live trace
        {investigation && (
          <span className={`status-badge ${investigation.status}`}>{investigation.status}</span>
        )}
      </div>
      {error && <div className="error-box tight">{error}</div>}
      {!investigation && (
        <div className="trace-empty">
          Запустите расследование — шаги агента появятся здесь в реальном времени.
        </div>
      )}
      {investigation && (
        <div className="trace-steps" ref={listRef}>
          {investigation.trace.map((t, i) => (
            <div key={i} className="trace-row">
              <div className="trace-row-head">
                <span className="trace-ts">{fmtTime(t.ts)}</span>
                <span className="trace-name">{t.step}</span>
                {t.tool && <span className="trace-tool-chip">{t.tool}</span>}
              </div>
              <div className="trace-io">
                <span className="trace-in">{t.input_summary}</span>
                <span className="trace-arrow">→</span>
                <span className="trace-out2">{t.output_summary}</span>
              </div>
            </div>
          ))}
          {investigation.status === 'running' && (
            <div className="trace-row pending">
              <span className="spinner" />
              выполняется…
            </div>
          )}
        </div>
      )}
    </aside>
  )
}
