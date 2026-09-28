import { useMemo, type ReactNode } from "react"

import { PassageActions } from "@/components/passage-actions"
import { Badge } from "@/components/ui/badge"
import { briefItems, isFlagged, pathLabel } from "@/lib/grounding"
import { cn } from "@/lib/utils"
import type { ContentBrief, FormatResult, Passage } from "@/lib/types"

// A format's output as the passages grounding checked, in payload order.
// Flagged passages are amber with their reasons; for a partly supported one
// only the unsupported words are marked. An accepted flag keeps its reasons,
// struck through. Selecting a passage lists the brief items it rests on,
// highlights them and their blocks in the source pane, and offers the
// reviewer's actions: edit, regenerate, accept, delete (passage-actions.tsx).

const AMBER = "bg-amber-100 dark:bg-amber-950/60"

const REVIEW_LABELS: Record<NonNullable<Passage["review"]>, string> = {
  accepted: "accepted",
  edited: "edited · not checked",
  regenerated: "regenerated",
}

function PassageText({ passage }: { passage: Passage }) {
  const { text, quote } = passage
  // Grounding only keeps a quote that is a verbatim substring of the passage.
  // An accepted flag is no longer marked.
  const at = quote && isFlagged(passage) ? text.indexOf(quote) : -1
  if (at < 0) return <span className="whitespace-pre-wrap">{text}</span>
  return (
    <span className="whitespace-pre-wrap">
      {text.slice(0, at)}
      <mark
        className={cn(AMBER, "rounded-sm text-inherit ring-1 ring-amber-500")}
      >
        {quote}
      </mark>
      {text.slice(at + quote!.length)}
    </span>
  )
}

function RestsOn({
  passage,
  items,
}: {
  passage: Passage
  items: Map<string, string>
}): ReactNode {
  if (passage.review === "edited") {
    return <p>Edited by the reviewer; not checked against the brief.</p>
  }
  if (passage.verdict === "not_factual") {
    return <p>Not a factual statement, so nothing to trace.</p>
  }
  if (passage.items.length === 0) {
    return <p>Rests on no brief item.</p>
  }
  return (
    <ul className="space-y-1">
      {passage.items.map((id) => (
        <li key={id}>
          <Badge variant="secondary" className="mr-1.5 font-mono">
            {id}
          </Badge>
          {items.get(id) ?? "(not in this brief)"}
        </li>
      ))}
    </ul>
  )
}

export function PassageList({
  jobId,
  format,
  passages,
  brief,
  selectedPath,
  onSelect,
  onRevised,
}: {
  jobId: string
  format: string
  passages: Passage[]
  brief: ContentBrief
  selectedPath: string | null
  onSelect: (path: string | null) => void
  onRevised: (result: FormatResult) => void
}) {
  const items = useMemo(() => briefItems(brief), [brief])

  return (
    <ol className="space-y-1.5">
      {passages.map((p) => {
        const flagged = isFlagged(p)
        const selected = p.path === selectedPath
        return (
          <li
            key={p.path}
            className={cn(
              "rounded-md border border-transparent",
              flagged && "border-l-2 border-l-amber-500",
              flagged && !p.quote && AMBER,
              selected && "border-ring ring-1 ring-ring"
            )}
          >
            <button
              type="button"
              aria-pressed={selected}
              onClick={() => onSelect(selected ? null : p.path)}
              className="w-full cursor-pointer rounded-md px-2.5 py-1.5 text-left hover:bg-muted/60 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
            >
              <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                {pathLabel(p.path)}
                {p.review && (
                  <Badge variant="outline" className="h-4 px-1.5 text-[10px]">
                    {REVIEW_LABELS[p.review]}
                  </Badge>
                )}
              </span>
              <span
                className={cn(
                  p.verdict === "not_factual" && "text-muted-foreground"
                )}
              >
                <PassageText passage={p} />
              </span>
              {p.reasons.length > 0 && (
                <span
                  className={cn(
                    "mt-1 block text-xs",
                    flagged
                      ? "text-amber-700 dark:text-amber-400"
                      : "text-muted-foreground line-through"
                  )}
                >
                  {p.reasons.map((r) => (
                    <span key={r} className="block">
                      {r}
                    </span>
                  ))}
                </span>
              )}
            </button>
            {selected && (
              <div className="space-y-3 border-t px-2.5 py-2 text-xs text-muted-foreground">
                <div>
                  <p className="mb-1 font-medium text-foreground">Rests on</p>
                  <RestsOn passage={p} items={items} />
                </div>
                <PassageActions
                  jobId={jobId}
                  format={format}
                  passage={p}
                  onRevised={onRevised}
                  // Its path now belongs to the next entry, if any: deselect.
                  onDeleted={() => onSelect(null)}
                />
              </div>
            )}
          </li>
        )
      })}
    </ol>
  )
}
