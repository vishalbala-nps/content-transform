import type { ContentBrief, FormatResult, Passage } from "@/lib/types"

// Brief item ids as grounding assigns them. Must match _items() in
// app/verify/grounding.py: claims keep their own id, the rest are numbered
// from 1 by kind, plus "src", "tldr" and "sec" for the parts with no list.
export const itemId = {
  stat: (i: number) => `s${i + 1}`,
  timeline: (i: number) => `t${i + 1}`,
  action: (i: number) => `a${i + 1}`,
  entity: (i: number) => `e${i + 1}`,
}

// Every brief item a passage can rest on, by id, as one line of text.
export function briefItems(brief: ContentBrief): Map<string, string> {
  const items = new Map<string, string>([
    [
      "src",
      `Source: ${[brief.source.kind.replaceAll("_", " "), brief.source.origin, brief.source.published].filter(Boolean).join(", ")}`,
    ],
    ["tldr", brief.tldr],
  ])
  for (const c of brief.claims) items.set(c.id, c.text)
  brief.stats.forEach((s, i) =>
    items.set(itemId.stat(i), `${s.value}: ${s.label}`)
  )
  brief.timeline.forEach((t, i) =>
    items.set(itemId.timeline(i), `${t.when}: ${t.event}`)
  )
  brief.actions.forEach((a, i) => items.set(itemId.action(i), a.text))
  brief.entities.forEach((e, i) =>
    items.set(itemId.entity(i), `${e.name}: ${e.role}`)
  )
  if (brief.security) items.set("sec", "Security details")
  return items
}

// "slides[2].notes" -> "Slides 3 › notes": readable without knowing the format.
export function pathLabel(path: string): string {
  const label = path
    .split(".")
    .map((part) =>
      part
        .replace(/\[(\d+)\]/g, (_, i) => ` ${Number(i) + 1}`)
        .replaceAll("_", " ")
    )
    .join(" › ")
  return label.charAt(0).toUpperCase() + label.slice(1)
}

// What Delete removes: the nearest list entry holding the passage, e.g.
// "slides[2].notes" -> "slides[2]" (the whole slide), "tweets[0]" -> itself.
// Null for a field outside any list, which is required. Must match
// list_entry() in app/verify/grounding.py.
export function listEntry(path: string): string | null {
  const cut = path.lastIndexOf("]")
  return cut >= 0 ? path.slice(0, cut + 1) : null
}

// What the selected passage rests on, in the source and brief panes. Not
// amber: amber means "needs review", this means "look here".
export const HIGHLIGHT =
  "rounded-sm bg-sky-100 ring-1 ring-sky-400 dark:bg-sky-950 dark:ring-sky-700"

// Needs review: has reasons that a reviewer has not accepted.
export function isFlagged(p: Passage): boolean {
  return p.reasons.length > 0 && p.review !== "accepted"
}

// The passage the reviewer has open: stored as a format and path, since a
// revision replaces the passage itself.
export interface SelectionKey {
  format: string
  path: string
}

// The same, resolved against the current job.
export interface Selection {
  format: string
  label: string // the format's UI label
  passage: Passage
}

export function resolveSelection(
  key: SelectionKey | null,
  outputs: FormatResult[]
): Selection | null {
  const output = outputs.find((o) => o.name === key?.format)
  const passage = output?.grounding?.passages.find((p) => p.path === key?.path)
  return output && passage
    ? { format: output.name, label: output.label, passage }
    : null
}
