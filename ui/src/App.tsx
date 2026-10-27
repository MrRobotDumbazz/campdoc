import { useEffect, useMemo, useState } from 'react'
import { createApiClient } from './api/client'
import type { Dataset } from './api/types'
import DatasetPicker from './components/DatasetPicker'
import ChatPanel from './components/ChatPanel'
import type { ChatMessage } from './components/ChatPanel'

export default function App() {
  const client = useMemo(() => createApiClient(), [])
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [histories, setHistories] = useState<Record<string, ChatMessage[]>>({})
  const [loadError, setLoadError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
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
    return () => {
      cancelled = true
    }
  }, [client])

  const selected = datasets.find((d) => d.campaign_id === selectedId) ?? null

  return (
    <div className="app">
      <header className="app-header">
        <div className="logo">
          <span className="logo-mark">⚕</span> Campaign Doctor
        </div>
        <div className="mode-badge">mock mode</div>
      </header>
      <div className="app-body">
        <aside className="sidebar">
          <DatasetPicker datasets={datasets} selectedId={selectedId} onSelect={setSelectedId} />
          {loadError && <div className="error-box">Не удалось загрузить датасеты: {loadError}</div>}
        </aside>
        <main className="chat-area">
          {selected ? (
            <ChatPanel
              key={selected.campaign_id}
              client={client}
              campaign={selected}
              initialMessages={histories[selected.campaign_id] ?? []}
              onMessagesChange={(msgs) =>
                setHistories((h) => ({ ...h, [selected.campaign_id]: msgs }))
              }
            />
          ) : (
            <div className="chat-empty">Выберите датасет слева</div>
          )}
        </main>
      </div>
    </div>
  )
}
