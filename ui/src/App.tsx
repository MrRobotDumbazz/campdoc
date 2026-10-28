import { useCallback, useEffect, useMemo, useState } from 'react'
import { createApiClient } from './api/client'
import type { Dataset, Investigation } from './api/types'
import DatasetPicker from './components/DatasetPicker'
import ChatPanel from './components/ChatPanel'
import type { ChatMessage } from './components/ChatPanel'
import TracePanel from './components/TracePanel'
import type { SimState } from './components/SimView'

export default function App() {
  const client = useMemo(() => createApiClient(), [])
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [histories, setHistories] = useState<Record<string, ChatMessage[]>>({})
  const [investigations, setInvestigations] = useState<Record<string, Investigation>>({})
  const [investigationErrors, setInvestigationErrors] = useState<Record<string, string>>({})
  const [simulations, setSimulations] = useState<Record<string, SimState>>({})
  const [datasetsLoading, setDatasetsLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setDatasetsLoading(true)
    client
      .datasets()
      .then((ds) => {
        if (cancelled) return
        setDatasets(ds)
        const first = ds.find((d) => !d.healthy) ?? ds[0]
        if (first) setSelectedId(first.campaign_id)
      })
      .catch((e: unknown) => {
        if (!cancelled) setLoadError(e instanceof Error ? e.message : String(e))
      })
      .finally(() => {
        if (!cancelled) setDatasetsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [client])

  const handleMessagesChange = useCallback((campaignId: string, msgs: ChatMessage[]) => {
    setHistories((prev) => ({ ...prev, [campaignId]: msgs }))
  }, [])

  const handleInvestigationData = useCallback((id: string, inv: Investigation) => {
    setInvestigations((prev) => ({ ...prev, [id]: inv }))
  }, [])

  const handleInvestigationError = useCallback((id: string, error: string) => {
    setInvestigationErrors((prev) => ({ ...prev, [id]: error }))
  }, [])

  const handleSimulationChange = useCallback((key: string, state: SimState) => {
    setSimulations((prev) => ({ ...prev, [key]: state }))
  }, [])

  const selected = datasets.find((d) => d.campaign_id === selectedId) ?? null
  const liveMode = import.meta.env.VITE_LIVE_API === '1'

  const activeInvestigationId = useMemo(() => {
    if (!selected) return null
    const msgs = histories[selected.campaign_id]
    if (!msgs) return null
    for (let i = msgs.length - 1; i >= 0; i--) {
      const m = msgs[i]
      if (m.role === 'bot') return m.investigationId
    }
    return null
  }, [histories, selected])

  return (
    <div className="app">
      <header className="app-header">
        <div className="logo">
          <span className="logo-mark">⚕</span> Campaign Doctor
        </div>
        <div className={`mode-badge ${liveMode ? 'live' : ''}`}>{liveMode ? 'live api' : 'mock mode'}</div>
      </header>
      <div className="app-body">
        <aside className="sidebar">
          {datasetsLoading && <div className="sidebar-loading"><span className="spinner" /> Загрузка датасетов…</div>}
          {!datasetsLoading && (
            <DatasetPicker datasets={datasets} selectedId={selectedId} onSelect={setSelectedId} />
          )}
          {loadError && <div className="error-box">Не удалось загрузить датасеты: {loadError}</div>}
        </aside>
        <main className="chat-area">
          {selected ? (
            <ChatPanel
              key={selected.campaign_id}
              client={client}
              campaign={selected}
              initialMessages={histories[selected.campaign_id] ?? []}
              investigations={investigations}
              errors={investigationErrors}
              simulations={simulations}
              onMessagesChange={handleMessagesChange}
              onInvestigationData={handleInvestigationData}
              onInvestigationError={handleInvestigationError}
              onSimulationChange={handleSimulationChange}
            />
          ) : (
            <div className="chat-empty">Выберите датасет слева</div>
          )}
        </main>
        <TracePanel
          investigation={activeInvestigationId ? investigations[activeInvestigationId] ?? null : null}
          error={activeInvestigationId ? investigationErrors[activeInvestigationId] : undefined}
        />
      </div>
    </div>
  )
}
