export interface Dataset {
  campaign_id: string
  name: string
  healthy: boolean
}

export interface TraceStep {
  ts: string
  step: string
  tool: string | null
  input_summary: string
  output_summary: string
}

export interface Evidence {
  tool: string
  ref: string
  summary: string
}

export interface Finding {
  cause: string
  evidence: Evidence[]
  confidence: number
  proposed_changes: string[]
}

export interface Verifier {
  claims_total: number
  claims_grounded: number
  removed: string[]
}

export type InvestigationStatus = 'running' | 'done' | 'error'

export interface Investigation {
  status: InvestigationStatus
  question: string
  trace: TraceStep[]
  findings: Finding[]
  verifier: Verifier
}

export interface Metrics {
  impressions: number
  spend: number
  win_rate: number
  ecpm: number
}

export interface SimulateResponse {
  before: Metrics
  after: Metrics
  delta: Metrics
  verified: boolean
  threshold_pct: number
  violated_constraints: string[]
  notes: string[]
}

export interface ApiClient {
  datasets(): Promise<Dataset[]>
  ask(campaignId: string, question: string): Promise<{ investigation_id: string }>
  investigation(id: string): Promise<Investigation>
  simulate(investigationId: string, fixIdx: number, seed: number): Promise<SimulateResponse>
  report(investigationId: string): Promise<string>
}
