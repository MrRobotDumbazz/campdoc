import type {
  ApiClient,
  Dataset,
  Finding,
  Investigation,
  SimulateResponse,
  TraceStep,
} from './types'

interface InvestigationRecord {
  question: string
  campaignId: string
  createdAt: number
  findings: Finding[]
}

const DATASETS: Dataset[] = [
  { campaign_id: 'camp_q4_retail', name: 'Q4 Retail — Delivery Drop', healthy: false },
  { campaign_id: 'camp_saas_ua', name: 'SaaS UA — Win Rate Collapse', healthy: false },
  { campaign_id: 'camp_app_inst', name: 'App Installs — eCPM Spike', healthy: false },
  { campaign_id: 'camp_brand', name: 'Brand Awareness — Control', healthy: true },
]

const FINDINGS: Record<string, Finding[]> = {
  camp_q4_retail: [
    {
      cause: 'Частотная перегрузка: frequency cap отсутствует, до 12+ показов/день на пользователя при норме 5',
      evidence: [
        { tool: 'query_delivery', ref: 'delivery_daily.csv#rows 2026-10-18..24', summary: 'Средняя частота 11.8/день, у 60% пользователей 10+ показов' },
        { tool: 'query_bid_samples', ref: 'bid_samples.jsonl#sampled 5k', summary: 'Ставка выигрывает аукцион, но повторные показы дешевеют — прироста уникальных юзеров нет' },
        { tool: 'compare_to_benchmark', ref: 'benchmark q4_retail_sector', summary: 'Частота выше секторной нормы в 2.4x, CTR ниже нормы на 38%' },
      ],
      confidence: 0.86,
      proposed_changes: ['frequency_cap: 5', 'bid_delta_pct: -10'],
    },
    {
      cause: 'Суженная гео-настройка: 92% бюджета в 2 регионах из 18 доступных',
      evidence: [
        { tool: 'get_campaign_settings', ref: 'settings.json#geo', summary: 'geo: ["US-CA","US-NY"], остальные 16 регионов выключены' },
        { tool: 'query_delivery', ref: 'delivery_daily.csv#geo_breakdown', summary: 'Аукционов из других регионов достаточно, охват недобирается' },
      ],
      confidence: 0.71,
      proposed_changes: ['geo_widen: ["US-TX","US-FL","US-IL"]'],
    },
  ],
  camp_saas_ua: [
    {
      cause: 'Ставка ниже медианы конкурентов: win rate 14% против 41% у бенчмарка',
      evidence: [
        { tool: 'query_bid_samples', ref: 'bid_samples.jsonl#sampled 8k', summary: 'Медиана выигрышных ставок конкурентов $2.85, наша ставка $2.10' },
        { tool: 'compare_to_benchmark', ref: 'benchmark b2b_saas', summary: 'Win rate ниже секторного на 27 п.п., spend в норме' },
      ],
      confidence: 0.91,
      proposed_changes: ['bid: 2.85'],
    },
  ],
  camp_app_inst: [
    {
      cause: 'Дневной бюджет исчерпывается к 11:00 — потеря вечернего трафика с лучшей конверсией',
      evidence: [
        { tool: 'query_delivery', ref: 'delivery_hourly.csv#2026-10-20..26', summary: 'Spend достигает daily cap к 11:00, показы после 12:00 — нули' },
        { tool: 'get_campaign_settings', ref: 'settings.json#pacing', summary: 'pacing: asap при дневном капе $500' },
        { tool: 'query_bid_samples', ref: 'bid_samples.jsonl#daypart_analysis', summary: 'Вечерние слоты 18-23 имеют конверсию в 1.7x выше средней' },
      ],
      confidence: 0.83,
      proposed_changes: ['pacing: even', 'dayparts: ["18-23"]'],
    },
  ],
}

const GENERIC_FINDINGS: Finding[] = [
  {
    cause: 'Кампания здорова: метрики в пределах секторной нормы',
    evidence: [
      { tool: 'compare_to_benchmark', ref: 'benchmark sector_avg', summary: 'Все ключевые метрики в пределах ±5% от нормы' },
    ],
    confidence: 0.94,
    proposed_changes: [],
  },
]

interface TraceTemplateEntry {
  step: string
  tool: string | null
  inputSummary: string
  outputSummary: string
  atMs: number
}

function buildTraceTemplate(question: string, findingsCount: number): TraceTemplateEntry[] {
  return [
    { step: 'plan', tool: null, inputSummary: question, outputSummary: 'План: delivery → bid samples → settings → benchmark', atMs: 0 },
    { step: 'query_delivery', tool: 'query_delivery', inputSummary: 'daily rows, last 7 days', outputSummary: '213k строк, аномалия частоты в 2 сегментах', atMs: 1100 },
    { step: 'query_bid_samples', tool: 'query_bid_samples', inputSummary: 'sampled bid log', outputSummary: '5 214 записей, win rate 14%', atMs: 2400 },
    { step: 'get_campaign_settings', tool: 'get_campaign_settings', inputSummary: 'campaign settings', outputSummary: 'geo: 2 региона, pacing: asap', atMs: 3500 },
    { step: 'compare_to_benchmark', tool: 'compare_to_benchmark', inputSummary: 'sector benchmark', outputSummary: '3 метрики вне нормы', atMs: 4700 },
    { step: 'analyze', tool: null, inputSummary: `${findingsCount} candidate causes`, outputSummary: `${findingsCount} finding(s) с evidence`, atMs: 5900 },
    { step: 'verify', tool: null, inputSummary: 'claims from findings', outputSummary: 'groundedness check passed', atMs: 7100 },
  ]
}

function mulberry32(seed: number): () => number {
  let a = seed >>> 0
  return () => {
    a |= 0
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

const BASE_METRICS: Record<string, { impressions: number; spend: number; win_rate: number; ecpm: number }> = {
  camp_q4_retail: { impressions: 1_240_000, spend: 8_900, win_rate: 0.62, ecpm: 7.2 },
  camp_saas_ua: { impressions: 410_000, spend: 5_200, win_rate: 0.14, ecpm: 12.7 },
  camp_app_inst: { impressions: 780_000, spend: 4_600, win_rate: 0.48, ecpm: 5.9 },
  camp_brand: { impressions: 2_100_000, spend: 11_400, win_rate: 0.55, ecpm: 5.4 },
}

const investigations = new Map<string, InvestigationRecord>()
let counter = 0

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v))
}

function fmt(n: number, digits = 2): number {
  const p = 10 ** digits
  return Math.round(n * p) / p
}

export class MockClient implements ApiClient {
  async datasets(): Promise<Dataset[]> {
    return DATASETS
  }

  async ask(campaignId: string, question: string): Promise<{ investigation_id: string }> {
    const id = `inv_${Date.now().toString(36)}_${++counter}`
    const findings = FINDINGS[campaignId] ?? GENERIC_FINDINGS
    investigations.set(id, { question, campaignId, createdAt: Date.now(), findings })
    return { investigation_id: id }
  }

  async investigation(id: string): Promise<Investigation> {
    const rec = investigations.get(id)
    if (!rec) {
      throw new Error(`investigation ${id} not found`)
    }
    const elapsed = Date.now() - rec.createdAt
    const template = buildTraceTemplate(rec.question, rec.findings.length)
    const trace: TraceStep[] = template
      .filter((t) => elapsed >= t.atMs)
      .map((t) => ({
        ts: new Date(rec.createdAt + t.atMs).toISOString(),
        step: t.step,
        tool: t.tool,
        input_summary: t.inputSummary,
        output_summary: t.outputSummary,
      }))
    const done = elapsed >= 8200
    const claimsTotal = rec.findings.reduce((acc, f) => acc + f.evidence.length, 0)
    return {
      status: done ? 'done' : 'running',
      question: rec.question,
      trace,
      findings: done ? rec.findings : [],
      verifier: done
        ? { claims_total: claimsTotal, claims_grounded: claimsTotal, removed: [] }
        : { claims_total: 0, claims_grounded: 0, removed: [] },
    }
  }

  async simulate(investigationId: string, fixIdx: number, seed: number): Promise<SimulateResponse> {
    const rec = investigations.get(investigationId)
    if (!rec) {
      throw new Error(`investigation ${investigationId} not found`)
    }
    const finding = rec.findings[fixIdx]
    if (!finding) {
      throw new Error(`fix ${fixIdx} not found`)
    }
    const before = { ...(BASE_METRICS[rec.campaignId] ?? BASE_METRICS.camp_brand) }
    const rng = mulberry32(seed + fixIdx * 977)
    const lift = 0.08 + rng() * 0.22
    const after = {
      impressions: Math.round(before.impressions * (1 + lift)),
      spend: fmt(before.spend * (1 + rng() * 0.06)),
      win_rate: fmt(clamp(before.win_rate * (1 + rng() * 0.15), 0, 1), 4),
      ecpm: fmt(before.ecpm * (1 - rng() * 0.04)),
    }
    const delta = {
      impressions: after.impressions - before.impressions,
      spend: fmt(after.spend - before.spend),
      win_rate: fmt(after.win_rate - before.win_rate, 4),
      ecpm: fmt(after.ecpm - before.ecpm),
    }
    const thresholdPct = 5.0
    const deltaPct = (delta.impressions / before.impressions) * 100
    return {
      before,
      after,
      delta,
      verified: deltaPct >= thresholdPct,
      threshold_pct: thresholdPct,
      violated_constraints: [],
      notes: ['Симуляция на выборке bid-запросов; прогноз, не гарантия', `seed=${seed}, детерминированный реплей`],
    }
  }

  async report(investigationId: string): Promise<string> {
    const rec = investigations.get(investigationId)
    if (!rec) {
      throw new Error(`investigation ${investigationId} not found`)
    }
    const claimsTotal = rec.findings.reduce((a, f) => a + f.evidence.length, 0)
    const lines: string[] = [
      '# Campaign Doctor — отчёт по расследованию',
      '',
      `**Вопрос:** ${rec.question}`,
      '',
      '## Findings',
      '',
    ]
    rec.findings.forEach((f, i) => {
      lines.push(`### ${i + 1}. ${f.cause}`)
      lines.push(`- Confidence: ${(f.confidence * 100).toFixed(0)}%`)
      lines.push('- Evidence:')
      f.evidence.forEach((e) => lines.push(`  - \`${e.tool}\` → ${e.ref}: ${e.summary}`))
      if (f.proposed_changes.length > 0) {
        lines.push(`- Proposed changes: ${f.proposed_changes.map((c) => `\`${c}\``).join(', ')}`)
      }
      lines.push('')
    })
    lines.push('## Verifier')
    lines.push('')
    lines.push(`Grounded claims: ${claimsTotal}/${claimsTotal}, removed: 0`)
    lines.push('')
    return lines.join('\n')
  }
}
