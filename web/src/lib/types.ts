// Mirrors app/ingest/base.py (SourceDocument) and app/understand/schemas.py
// (ContentBrief). Those are the frozen contracts; keep this file in step.

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

export interface GenerateResponse {
  source: SourceDocument
  brief: ContentBrief
  post: string
}
