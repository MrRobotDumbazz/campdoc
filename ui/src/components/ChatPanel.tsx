import { useCallback, useEffect, useRef, useState } from 'react'
import type { ApiClient, Dataset, Investigation } from '../api/types'
import SimView from './SimView'
import type { SimState } from './SimView'

export type ChatMessage =
  | { role: 'user'; text: string }
  | { role: 'bot'; investigationId: string }

type BotMessage = Extract<ChatMessage, { role: 'bot' }>

interface Props {
  client: ApiClient
  campaign: Dataset
  initialMessages: ChatMessage[]
  investigations: Record<string, Investigation>
  errors: Record<string, string>
  simulations: Record<string, SimState>
  onMessagesChange: (campaignId: string, messages: ChatMessage[]) => void
  onInvestigationData: (id: string, investigation: Investigation) => void
  onInvestigationError: (id: string, error: string) => void
  onSimulationChange: (key: string, state: SimState) => void
}

const SUGGESTIONS = [
  'Почему упали показы за последнюю неделю?',
  'Что сломалось в этой кампании?',
  'Сравни с бенчмарком сектора',
]

export default function ChatPanel({
  client,
  campaign,
  initialMessages,
  investigations,
  errors,
  simulations,
  onMessagesChange,
  onInvestigationData,
  onInvestigationError,
  onSimulationChange,
}: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages)
  const [input, setInput] = useState('')
  const [asking, setAsking] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  const pendingIds = messages
    .filter((m): m is BotMessage => m.role === 'bot')
    .map((m) => m.investigationId)
    .filter((id) => investigations[id]?.status === undefined || investigations[id].status === 'running')

  useEffect(() => {
    if (pendingIds.length === 0) return
    let cancelled = false
    const timer = setTimeout(() => {
      pendingIds.forEach((id) => {
        client
          .investigation(id)
          .then((inv) => {
            if (!cancelled) onInvestigationData(id, inv)
          })
          .catch((e: unknown) => {
            if (!cancelled) onInvestigationError(id, e instanceof Error ? e.message : String(e))
          })
      })
    }, 600)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [pendingIds.join(','), client, onInvestigationData, onInvestigationError])

  useEffect(() => {
    onMessagesChange(campaign.campaign_id, messages)
  }, [campaign.campaign_id, messages, onMessagesChange])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const runSim = useCallback(
    async (investigationId: string, fixIdx: number) => {
      const key = `${investigationId}:${fixIdx}`
      const seed = Math.floor(Math.random() * 1_000_000)
      onSimulationChange(key, { status: 'loading', seed })
      try {
        const result = await client.simulate(investigationId, fixIdx, seed)
        onSimulationChange(key, { status: 'done', seed, result })
      } catch (e) {
        onSimulationChange(key, {
          status: 'error',
          seed,
          error: e instanceof Error ? e.message : String(e),
        })
      }
    },
    [client, onSimulationChange],
  )

  const downloadReport = useCallback(
    async (investigationId: string) => {
      const md = await client.report(investigationId)
      const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `report-${investigationId}.md`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    },
    [client],
  )

  async function send(question: string) {
    const q = question.trim()
    if (!q || asking) return
    setAsking(true)
    setError(null)
    setMessages((m) => [...m, { role: 'user', text: q }])
    setInput('')
    try {
      const { investigation_id } = await client.ask(campaign.campaign_id, q)
      setMessages((m) => [...m, { role: 'bot', investigationId: investigation_id }])
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setAsking(false)
    }
  }

  return (
    <div className="chat-panel">
      <div className="chat-header">
        <span className={`health-dot ${campaign.healthy ? 'ok' : 'bad'}`} />
        {campaign.name}
        <span className="campaign-id">{campaign.campaign_id}</span>
      </div>
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-hint">
            Задайте вопрос по кампании — агент проведёт расследование и покажет находки с evidence.
          </div>
        )}
        {messages.map((m, i) =>
          m.role === 'user' ? (
            <div key={i} className="msg user">
              <div className="msg-bubble">{m.text}</div>
            </div>
          ) : (
            <InvestigationBubble
              key={m.investigationId}
              investigationId={m.investigationId}
              investigation={investigations[m.investigationId] ?? null}
              error={errors[m.investigationId]}
              simulations={simulations}
              onRunSim={runSim}
              onDownloadReport={downloadReport}
            />
          ),
        )}
        <div ref={bottomRef} />
      </div>
      {error && <div className="error-box">{error}</div>}
      <div className="chat-input-row">
        <div className="suggestions">
          {SUGGESTIONS.map((s) => (
            <button key={s} className="chip" onClick={() => send(s)} disabled={asking}>
              {s}
            </button>
          ))}
        </div>
        <form
          className="chat-input-form"
          onSubmit={(e) => {
            e.preventDefault()
            send(input)
          }}
        >
          <input
            className="chat-input"
            value={input}
            placeholder="Спросите агента…"
            onChange={(e) => setInput(e.target.value)}
            disabled={asking}
          />
          <button className="send-btn" type="submit" disabled={asking || !input.trim()}>
            {asking ? '…' : 'Отправить'}
          </button>
        </form>
      </div>
    </div>
  )
}

function InvestigationBubble({
  investigationId,
  investigation,
  error,
  simulations,
  onRunSim,
  onDownloadReport,
}: {
  investigationId: string
  investigation: Investigation | null
  error?: string
  simulations: Record<string, SimState>
  onRunSim: (investigationId: string, fixIdx: number) => void
  onDownloadReport: (investigationId: string) => Promise<void>
}) {
  const [reportBusy, setReportBusy] = useState(false)
  const [reportError, setReportError] = useState<string | null>(null)

  async function handleDownload() {
    setReportBusy(true)
    setReportError(null)
    try {
      await onDownloadReport(investigationId)
    } catch (e) {
      setReportError(e instanceof Error ? e.message : String(e))
    } finally {
      setReportBusy(false)
    }
  }

  if (error) {
    return (
      <div className="msg bot">
        <div className="msg-bubble error-box tight">Ошибка расследования: {error}</div>
      </div>
    )
  }

  if (!investigation || investigation.status === 'running') {
    const steps = investigation?.trace ?? []
    const last = steps[steps.length - 1]
    return (
      <div className="msg bot">
        <div className="msg-bubble running">
          <span className="spinner" />
          Агент расследует… {last ? `${last.step}: ${last.output_summary}` : 'старт'}
        </div>
      </div>
    )
  }

  if (investigation.status === 'error') {
    return (
      <div className="msg bot">
        <div className="msg-bubble error-box tight">Расследование завершилось с ошибкой</div>
      </div>
    )
  }

  const v = investigation.verifier
  return (
    <div className="msg bot">
      <div className="msg-bubble done">
        <details className="trace-details">
          <summary>Trace ({investigation.trace.length} шагов)</summary>
          <ol className="trace-list">
            {investigation.trace.map((t, i) => (
              <li key={i}>
                <span className="trace-step">{t.step}</span>
                {t.tool && <span className="trace-tool">{t.tool}</span>}
                <span className="trace-out">{t.output_summary}</span>
              </li>
            ))}
          </ol>
        </details>
        {investigation.findings.length === 0 && <div className="no-findings">Находок нет.</div>}
        {investigation.findings.map((f, idx) => (
          <div key={idx} className="finding">
            <div className="finding-cause">
              <span className="finding-idx">#{idx + 1}</span> {f.cause}
            </div>
            <div className="confidence-row">
              <div className="confidence-bar">
                <div className="confidence-fill" style={{ width: `${f.confidence * 100}%` }} />
              </div>
              <span className="confidence-num">{(f.confidence * 100).toFixed(0)}%</span>
            </div>
            <ul className="evidence-list">
              {f.evidence.map((e, i) => (
                <li key={i}>
                  <span className="evidence-tool">{e.tool}</span> <span className="evidence-ref">{e.ref}</span>
                  <div className="evidence-summary">{e.summary}</div>
                </li>
              ))}
            </ul>
            {f.proposed_changes.length > 0 && (
              <div className="changes">
                Proposed:{' '}
                {f.proposed_changes.map((c) => (
                  <code key={c}>{c}</code>
                ))}
              </div>
            )}
            {f.proposed_changes.length > 0 && (
              <div className="sim-slot">
                {simulations[`${investigationId}:${idx}`] ? (
                  <SimView
                    state={simulations[`${investigationId}:${idx}`]}
                    onRerun={() => onRunSim(investigationId, idx)}
                  />
                ) : (
                  <button className="sim-btn" onClick={() => onRunSim(investigationId, idx)}>
                    ▶ Симулировать фикс
                  </button>
                )}
              </div>
            )}
          </div>
        ))}
        <div className="report-row">
          <div className={`verifier ${v.claims_grounded < v.claims_total ? 'warn' : 'ok'}`}>
            Verifier: {v.claims_grounded}/{v.claims_total} claims grounded
            {v.removed.length > 0 && `, removed: ${v.removed.length}`}
          </div>
          <button className="sim-btn small" onClick={handleDownload} disabled={reportBusy}>
            ⬇ {reportBusy ? 'Готовим…' : 'Отчёт .md'}
          </button>
        </div>
        {reportError && <div className="error-box tight">{reportError}</div>}
      </div>
    </div>
  )
}
