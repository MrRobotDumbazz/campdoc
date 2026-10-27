import { useEffect, useRef, useState } from 'react'
import type { ApiClient, Dataset, Investigation } from '../api/types'

export type ChatMessage =
  | { role: 'user'; text: string }
  | { role: 'bot'; investigationId: string }

interface Props {
  client: ApiClient
  campaign: Dataset
  initialMessages: ChatMessage[]
  onMessagesChange: (messages: ChatMessage[]) => void
}

const SUGGESTIONS = [
  'Почему упали показы за последнюю неделю?',
  'Что сломалось в этой кампании?',
  'Сравни с бенчмарком сектора',
]

export default function ChatPanel({ client, campaign, initialMessages, onMessagesChange }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages)
  const [input, setInput] = useState('')
  const [asking, setAsking] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    onMessagesChange(messages)
  }, [messages, onMessagesChange])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

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
            <InvestigationMessage key={m.investigationId} client={client} investigationId={m.investigationId} />
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

function InvestigationMessage({ client, investigationId }: { client: ApiClient; investigationId: string }) {
  const [investigation, setInvestigation] = useState<Investigation | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | null = null

    async function poll() {
      try {
        const inv = await client.investigation(investigationId)
        if (cancelled) return
        setInvestigation(inv)
        if (inv.status === 'running') {
          timer = setTimeout(poll, 800)
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e))
      }
    }

    poll()
    return () => {
      cancelled = true
      if (timer) clearTimeout(timer)
    }
  }, [client, investigationId])

  if (error) {
    return (
      <div className="msg bot">
        <div className="msg-bubble error-box">Ошибка расследования: {error}</div>
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
          <span className="step-count">шаг {steps.length}/7</span>
        </div>
      </div>
    )
  }

  if (investigation.status === 'error') {
    return (
      <div className="msg bot">
        <div className="msg-bubble error-box">Расследование завершилось с ошибкой</div>
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
          </div>
        ))}
        <div className={`verifier ${v.claims_grounded < v.claims_total ? 'warn' : 'ok'}`}>
          Verifier: {v.claims_grounded}/{v.claims_total} claims grounded
          {v.removed.length > 0 && `, removed: ${v.removed.length}`}
        </div>
      </div>
    </div>
  )
}
