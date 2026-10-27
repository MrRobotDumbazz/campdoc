import { MockClient } from './mock'
import type { ApiClient } from './types'

class FetchClient implements ApiClient {
  async datasets() {
    const res = await fetch('/api/datasets')
    if (!res.ok) throw new Error(await errorMessage(res))
    return res.json()
  }

  async ask(campaignId: string, question: string) {
    const res = await fetch('/api/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ campaign_id: campaignId, question }),
    })
    if (!res.ok) throw new Error(await errorMessage(res))
    return res.json()
  }

  async investigation(id: string) {
    const res = await fetch(`/api/investigations/${id}`)
    if (!res.ok) throw new Error(await errorMessage(res))
    return res.json()
  }

  async simulate(investigationId: string, fixIdx: number, seed: number) {
    const res = await fetch(`/api/investigations/${investigationId}/fixes/${fixIdx}/simulate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ seed }),
    })
    if (!res.ok) throw new Error(await errorMessage(res))
    return res.json()
  }

  async report(investigationId: string) {
    const res = await fetch(`/api/investigations/${investigationId}/report.md`)
    if (!res.ok) throw new Error(await errorMessage(res))
    return res.text()
  }
}

async function errorMessage(res: Response): Promise<string> {
  try {
    const body = await res.json()
    return body.error ?? body.detail ?? res.statusText
  } catch {
    return res.statusText
  }
}

export function createApiClient(): ApiClient {
  return import.meta.env.VITE_LIVE_API === '1' ? new FetchClient() : new MockClient()
}
