import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import type { JobSummary } from "@/lib/types"

const TIME = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
})

const STATUS_VARIANT = {
  queued: "outline",
  running: "secondary",
  done: "outline",
  failed: "destructive",
} as const

// Recent jobs, newest first. Selecting one opens it as if its link had been followed.
export function JobHistory({
  jobs,
  currentId,
  onOpen,
}: {
  jobs: JobSummary[]
  currentId: string | null
  onOpen: (id: string) => void
}) {
  if (jobs.length === 0) return null
  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent jobs</CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="divide-y text-sm">
          {jobs.map((j) => (
            <li key={j.id}>
              <button
                type="button"
                onClick={() => onOpen(j.id)}
                aria-current={j.id === currentId ? "true" : undefined}
                className={cn(
                  "flex w-full flex-wrap items-center gap-x-3 gap-y-1 px-2 py-2 text-left hover:bg-muted",
                  j.id === currentId && "bg-muted"
                )}
              >
                <span className="min-w-0 flex-1 truncate font-medium">
                  {j.title}
                </span>
                <span className="text-xs text-muted-foreground tabular-nums">
                  {j.formats.length} format{j.formats.length === 1 ? "" : "s"} ·{" "}
                  {TIME.format(new Date(j.created_at))}
                </span>
                <Badge variant={STATUS_VARIANT[j.status]}>{j.status}</Badge>
              </button>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  )
}
