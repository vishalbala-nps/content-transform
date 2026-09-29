// Mirrors app/ingest/base.py (SourceDocument), app/understand/schemas.py
// (ContentBrief), app/formats/base.py (Artifact) and the API models in
// app/api/routes.py and app/formats/runner.py. The first three are frozen
// contracts; keep this file in step.

export type Support = string[]

export interface Block {
  id: string
  type: "heading" | "para" | "list" | "table" | "caption"
  text: string
  page: number | null
}

export interface SourceDocument {
  doc_id: string
  markdown: string
  blocks: Block[]
  assets: unknown[]
  meta: Record<string, unknown>
}

export interface Claim {
  id: string
  text: string
  support: Support
}

export interface Entity {
  name: string
  kind:
    | "person"
    | "organisation"
    | "product"
    | "location"
    | "vulnerability"
    | "threat_actor"
    | "other"
  role: string
}

export interface TimelineItem {
  when: string
  event: string
  support: Support
}

export interface Stat {
  value: string
  label: string
  support: Support
}

export interface Action {
  text: string
  support: Support
}

export interface SourceProfile {
  kind:
    | "news_article"
    | "government_memo"
    | "security_advisory"
    | "press_release"
    | "research_report"
    | "opinion"
    | "internal_document"
    | "other"
  origin: string | null
  published: string | null
  tone: "formal" | "neutral" | "informal" | "technical"
}

export interface AffectedProduct {
  name: string
  versions: string
}

export interface IOC {
  kind: "ip" | "domain" | "url" | "hash" | "email" | "file" | "other"
  value: string
}

export interface SecurityDetails {
  cve_ids: string[]
  affected_products: AffectedProduct[]
  severity: "critical" | "high" | "medium" | "low" | "informational" | null
  cvss_score: number | null
  iocs: IOC[]
}

export interface ContentBrief {
  brief_id: string
  doc_id: string
  title: string
  source: SourceProfile
  tldr: string
  claims: Claim[]
  entities: Entity[]
  timeline: TimelineItem[]
  stats: Stat[]
  actions: Action[]
  security: SecurityDetails | null
}

// A text artifact has `text`; a binary one (PDF, PPTX) has `path` instead.
// Either kind downloads from artifactUrl() in lib/api.ts.
export interface Artifact {
  filename: string
  media_type: string
  text: string | null
  parts: string[]
  part_limit: number | null
  path: string | null
}

// Mirrors GenerationConfig and BrandKit in app/formats/base.py (frozen).
export type Audience = "executive" | "technical" | "general_public" | "media"
export type Tone = "formal" | "neutral" | "conversational" | "urgent"
export type Language = "en" | "hi" | "ta" | "ml" | "kn" | "te"
export type DetailLevel = "brief" | "standard" | "detailed"
export type Objective = "inform" | "warn" | "persuade" | "instruct" | "announce"

export interface BrandKit {
  kit_id: string
  org_name: string
  primary: string // "#rrggbb"
  ink: string
  font: string | null
  logo: string | null // storage key
  banned_phrases: string[]
}

export interface GenerationConfig {
  audience: Audience
  tone: Tone
  language: Language
  detail_level: DetailLevel
  objective: Objective
  style: string | null
  brand_kit: BrandKit | null
}

// What a job request chooses (JobSettings in app/api/routes.py).
export interface JobSettings {
  audience: Audience
  tone: Tone
  detail_level: DetailLevel
  objective: Objective
  language: Language // written in English, then translated
  style: string | null
  brand_kit_id: string | null // a saved kit; the job keeps a copy
}

// What a reviewer edits on a saved kit (BrandKitFields in
// app/core/brand_kits.py). The logo is uploaded on its own.
export interface BrandKitFields {
  org_name: string
  primary: string
  ink: string
  font: string | null
  banned_phrases: string[]
}

export interface FormatInfo {
  name: string
  label: string
}

// One prose field of a format's payload, traced to the brief (app/verify/grounding.py).
export interface Passage {
  path: string // "slides[2].notes"
  text: string
  verdict: "supported" | "partial" | "unsupported" | "not_factual" | null
  items: string[] // brief items: "c3", "s1", "src"
  blocks: string[] // source blocks behind those items
  quote: string | null // the unsupported words; null means the whole passage
  new_numbers: string[]
  reasons: string[] // why it needs review; empty when it does not
  // What a reviewer did (app/core/revise.py). Edited text is trusted, not
  // checked; an accepted flag keeps its reasons.
  review: "accepted" | "edited" | "regenerated" | null
}

export interface Grounding {
  passages: Passage[]
  error: string | null // the model check failed; only the number check ran
}

// Model calls and what they cost (app/core/usage.py). Cost is estimated
// from list prices when each call was made.
export interface Usage {
  calls: number // answered by the provider
  cached_calls: number // answered from the dev cache: no tokens, no cost
  input_tokens: number
  cached_input_tokens: number
  output_tokens: number // thinking included
  cost_usd: number
  unpriced_calls: number // calls to a model with no known price; not in cost_usd
}

// A part is null on outputs from before usage was recorded.
export interface FormatUsage {
  generate: Usage | null
  ground: Usage | null
  translate: Usage // translating the payload, for a language other than English
  revise: Usage // regenerated passages, each checked again
}

export interface FormatResult {
  name: string
  label: string
  artifacts: Artifact[]
  warnings: string[]
  payload: Record<string, unknown> | null // English: what is grounded and reviewed
  translation: Record<string, unknown> | null // the payload in the job's language; null for English
  error: string | null
  grounding: Grounding | null // null on failed formats and older jobs
  usage: FormatUsage | null // null on older jobs
}

export type JobStatus = "queued" | "running" | "done" | "failed"

export interface Step {
  name: string // "brief" or a format name
  label: string
  status: "pending" | "running" | "done" | "failed" | "skipped"
}

export interface Job {
  id: string
  status: JobStatus
  created_at: string
  updated_at: string
  formats: string[] // requested, in registry order
  config: GenerationConfig
  steps: Step[]
  source: SourceDocument
  brief: ContentBrief | null
  brief_usage: Usage | null // null on older jobs
  outputs: FormatResult[] // finished formats only
  error: string | null // why the whole job failed
}

export interface JobSummary {
  id: string
  status: JobStatus
  created_at: string
  title: string
  formats: string[]
}
