import { useMemo, type ReactNode } from "react"

import { SupportChips } from "@/components/support-chips"
import { HIGHLIGHT, itemId } from "@/lib/grounding"
import { cn } from "@/lib/utils"
import type { ContentBrief, SourceDocument } from "@/lib/types"

// The brief, as a tab beside the source. Items the selected passage rests on
// are highlighted and marked with data-highlight, so the pane can scroll to them.

function Section({
  title,
  highlighted = false,
  children,
}: {
  title: string
  highlighted?: boolean
  children: ReactNode
}) {
  return (
    <section
      data-highlight={highlighted || undefined}
      className={cn(highlighted && cn(HIGHLIGHT, "p-1.5"))}
    >
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
  id,
  highlight,
  render,
}: {
  title: string
  items: T[]
  id: (item: T, index: number) => string
  highlight: Set<string>
  render: (item: T) => ReactNode
}) {
  if (items.length === 0) return null
  return (
    <Section title={title}>
      <ul className="list-disc space-y-1.5 pl-5">
        {items.map((item, i) => {
          const on = highlight.has(id(item, i))
          return (
            <li
              key={i}
              data-highlight={on || undefined}
              className={cn(on && cn(HIGHLIGHT, "px-1"))}
            >
              {render(item)}
            </li>
          )
        })}
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
  highlight,
}: {
  brief: ContentBrief
  source: SourceDocument
  highlight: Set<string> // brief item ids, as in lib/grounding.ts
}) {
  const blocks = useMemo(
    () => new Map(source.blocks.map((b) => [b.id, b.text])),
    [source]
  )
  const profile = brief.source
  const security = brief.security

  return (
    <div className="space-y-5 text-sm leading-relaxed">
      <p className="font-medium">{brief.title}</p>

      <Section title="Source" highlighted={highlight.has("src")}>
        <Facts
          rows={[
            ["Kind", profile.kind.replaceAll("_", " ")],
            ["Origin", profile.origin],
            ["Published", profile.published],
            ["Tone", profile.tone],
          ]}
        />
      </Section>

      <Section title="TL;DR" highlighted={highlight.has("tldr")}>
        <p>{brief.tldr}</p>
      </Section>

      <ItemList
        title="Claims"
        items={brief.claims}
        id={(c) => c.id}
        highlight={highlight}
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
        id={(_, i) => itemId.stat(i)}
        highlight={highlight}
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
        id={(_, i) => itemId.timeline(i)}
        highlight={highlight}
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
        id={(_, i) => itemId.action(i)}
        highlight={highlight}
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
        id={(_, i) => itemId.entity(i)}
        highlight={highlight}
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
        <Section title="Security" highlighted={highlight.has("sec")}>
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
    </div>
  )
}
