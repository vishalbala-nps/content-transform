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

export interface FormatResult {
  name: string
  label: string
  artifacts: Artifact[]
  warnings: string[]
  payload: Record<string, unknown> | null
  error: string | null
  grounding: Grounding | null // null on failed formats and older jobs
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
  steps: Step[]
  source: SourceDocument
  brief: ContentBrief | null
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
