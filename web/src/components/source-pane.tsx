import { useEffect, useRef, useState } from "react"

import { BriefPanel } from "@/components/brief-panel"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { HIGHLIGHT, pathLabel, type Selection } from "@/lib/grounding"
import { cn } from "@/lib/utils"
import type { ContentBrief, SourceDocument } from "@/lib/types"

// What the outputs were written from: the source's blocks, and the brief in a
// second tab. Sticks beside the outputs on wide screens. Selecting a passage
// highlights the blocks and brief items it rests on and scrolls to the first.

function SourceBlocks({
  source,
  highlight,
}: {
  source: SourceDocument
  highlight: Set<string>
}) {
  return (
    <ol className="space-y-2 text-sm leading-relaxed">
      {source.blocks.map((b) => {
        const on = highlight.has(b.id)
        return (
          <li
            key={b.id}
            data-highlight={on || undefined}
            className={cn("px-1.5 py-0.5", on && HIGHLIGHT)}
          >
            <span className="mr-2 font-mono text-xs text-muted-foreground">
              {b.id}
              {b.page != null && ` · p.${b.page}`}
            </span>
            <span
              className={cn(
                "whitespace-pre-wrap",
                b.type === "heading" && "font-semibold"
              )}
            >
              {b.text}
            </span>
          </li>
        )
      })}
    </ol>
  )
}

export function SourcePane({
  source,
  brief,
  selection,
}: {
  source: SourceDocument
  brief: ContentBrief
  selection: Selection | null
}) {
  const [tab, setTab] = useState("source")
  const scroller = useRef<HTMLDivElement>(null)
  const blocks = new Set(selection?.passage.blocks)
  const items = new Set(selection?.passage.items)

  // Scroll within the pane only, so the page itself does not jump.
  useEffect(() => {
    const pane = scroller.current
    const first = pane?.querySelector<HTMLElement>(
      `[data-state="active"] [data-highlight]`
    )
    if (!pane || !first) return
    const top =
      first.getBoundingClientRect().top -
      pane.getBoundingClientRect().top +
      pane.scrollTop
    pane.scrollTo({ top: Math.max(0, top - 24), behavior: "smooth" })
  }, [selection, tab])

  const title = selection
    ? `Showing what ${selection.label} › ${pathLabel(selection.passage.path)} rests on`
    : `${source.blocks.length} blocks · select a passage to trace it`

  return (
    <Card className="lg:sticky lg:top-[calc(var(--header-height)+1rem)]">
      <Tabs value={tab} onValueChange={setTab} className="gap-0">
        <CardHeader className="gap-2">
          <TabsList>
            <TabsTrigger value="source">Source</TabsTrigger>
            <TabsTrigger value="brief">Brief</TabsTrigger>
          </TabsList>
          <p className="text-xs text-muted-foreground">{title}</p>
        </CardHeader>
        <CardContent
          ref={scroller}
          className="relative mt-4 lg:max-h-[calc(100svh-var(--header-height)-9rem)] lg:overflow-y-auto"
        >
          <TabsContent value="source">
            <SourceBlocks source={source} highlight={blocks} />
          </TabsContent>
          <TabsContent value="brief">
            <BriefPanel brief={brief} source={source} highlight={items} />
          </TabsContent>
        </CardContent>
      </Tabs>
    </Card>
  )
}
