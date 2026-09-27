import { useMemo, type ReactNode } from "react"

import { SupportChips } from "@/components/support-chips"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import type { ContentBrief, SourceDocument } from "@/lib/types"

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h3 className="mb-1.5 text-xs font-medium tracking-wide text-muted-foreground uppercase">
        {title}
      </h3>
      {children}
    </section>
  )
}

function ItemList<T>({
  title,
  items,
  render,
}: {
  title: string
  items: T[]
  render: (item: T) => ReactNode
}) {
  if (items.length === 0) return null
  return (
    <Section title={title}>
      <ul className="list-disc space-y-1.5 pl-5">
        {items.map((item, i) => (
          <li key={i}>{render(item)}</li>
        ))}
      </ul>
    </Section>
  )
}

function Facts({ rows }: { rows: [string, string | null | undefined][] }) {
  const shown = rows.filter(([, v]) => v)
  if (shown.length === 0) return null
  return (
    <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1">
      {shown.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="font-medium">{k}</dt>
          <dd className="break-words">{v}</dd>
        </div>
      ))}
    </dl>
  )
}

export function BriefPanel({
  brief,
  source,
}: {
  brief: ContentBrief
  source: SourceDocument
}) {
  const blocks = useMemo(
    () => new Map(source.blocks.map((b) => [b.id, b.text])),
    [source]
  )
  const profile = brief.source
  const security = brief.security

  return (
    <Card>
      <CardHeader>
        <CardTitle>Content brief</CardTitle>
        <CardDescription>
          {brief.title} · {source.blocks.length} source blocks
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5 text-sm leading-relaxed">
        <Section title="Source">
          <Facts
            rows={[
              ["Kind", profile.kind.replaceAll("_", " ")],
              ["Origin", profile.origin],
              ["Published", profile.published],
              ["Tone", profile.tone],
            ]}
          />
        </Section>

        <Section title="TL;DR">
          <p>{brief.tldr}</p>
        </Section>

        <ItemList
          title="Claims"
          items={brief.claims}
          render={(c) => (
            <>
              {c.text}
              <SupportChips ids={c.support} blocks={blocks} />
            </>
          )}
        />
        <ItemList
          title="Stats"
          items={brief.stats}
          render={(s) => (
            <>
              <strong>{s.value}</strong> {s.label}
              <SupportChips ids={s.support} blocks={blocks} />
            </>
          )}
        />
        <ItemList
          title="Timeline"
          items={brief.timeline}
          render={(t) => (
            <>
              <strong>{t.when}</strong> {t.event}
              <SupportChips ids={t.support} blocks={blocks} />
            </>
          )}
        />
        <ItemList
          title="Actions"
          items={brief.actions}
          render={(a) => (
            <>
              {a.text}
              <SupportChips ids={a.support} blocks={blocks} />
            </>
          )}
        />
        <ItemList
          title="Entities"
          items={brief.entities}
          render={(e) => (
            <>
              <strong>{e.name}</strong>{" "}
              <span className="text-xs text-muted-foreground">
                {e.kind.replaceAll("_", " ")}
              </span>{" "}
              — {e.role}
            </>
          )}
        />

        {security && (
          <Section title="Security">
            <Facts
              rows={[
                [
                  "Severity",
                  [
                    security.severity,
                    security.cvss_score != null
                      ? `CVSS ${security.cvss_score}`
                      : null,
                  ]
                    .filter(Boolean)
                    .join(" · "),
                ],
                ["CVEs", security.cve_ids.join(", ")],
                [
                  "Affected",
                  security.affected_products
                    .map((p) => `${p.name} (${p.versions})`)
                    .join("; "),
                ],
                [
                  "IOCs",
                  security.iocs.map((i) => `${i.kind}: ${i.value}`).join("; "),
                ],
              ]}
            />
          </Section>
        )}
      </CardContent>
    </Card>
  )
}
