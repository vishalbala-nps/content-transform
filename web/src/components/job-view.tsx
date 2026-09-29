import { useEffect, useState } from "react"
import { CopyPlus, LoaderCircle } from "lucide-react"

import { JobProgress } from "@/components/job-progress"
import { OutputPanel } from "@/components/output-panel"
import { SourcePane } from "@/components/source-pane"
import { UsageMeter } from "@/components/usage-meter"
import { Button } from "@/components/ui/button"
import { watchJob } from "@/lib/api"
import { resolveSelection, type SelectionKey } from "@/lib/grounding"
import type { FormatResult, Job } from "@/lib/types"

// One job, finished or still running: its progress and usage, then the
// source beside the outputs once the brief exists. Mounted once per job id
// (App keys it), so opening another job starts from a clean slate.

function statusText(job: Job): string {
  switch (job.status) {
    case "queued":
      return "Queued…"
    case "running":
      return "Working… you can close this tab and come back."
    case "failed":
      return "Failed"
    case "done": {
      const failed = job.outputs.filter((o) => o.error).length
      return `${job.brief?.claims.length ?? 0} claims · ${job.outputs.length - failed} of ${job.formats.length} formats generated`
    }
  }
}

// As the server titles jobs in its list (`_title` in app/api/routes.py): the
// brief's title, else the source's, else its first block.
function jobTitle(job: Job): string {
  if (job.brief) return job.brief.title
  const meta = job.source.meta.title
  const first =
    typeof meta === "string" && meta ? meta : (job.source.blocks[0]?.text ?? "")
  return first.length <= 80 ? first : first.slice(0, 79) + "…"
}

export function JobView({
  id,
  initial,
  onReuse,
}: {
  id: string
  initial: Job | null // the job as just created, shown until its first event
  onReuse: (job: Job) => void // start a new job from this one's input
}) {
  const [job, setJob] = useState<Job | null>(initial)
  const [reconnecting, setReconnecting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // The passage being traced to the source.
  const [selection, setSelection] = useState<SelectionKey | null>(null)

  useEffect(
    () =>
      watchJob(id, {
        onUpdate: (j) => {
          setReconnecting(false)
          setJob(j)
        },
        onLost: () => setReconnecting(true),
        onFail: () => {
          setReconnecting(false)
          setError("Could not load this job.")
        },
      }),
    [id]
  )

  if (!job) {
    return error ? (
      <p role="alert" className="text-sm text-destructive">
        {error}
      </p>
    ) : (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <LoaderCircle className="size-4 animate-spin" />
        Loading…
      </p>
    )
  }

  const traced = resolveSelection(selection, job.outputs)

  // A revised passage comes back as its format's whole new result. The job
  // row already holds it; a finished job has no event stream to send it.
  function replaceOutput(result: FormatResult) {
    setJob(
      (j) =>
        j && {
          ...j,
          outputs: j.outputs.map((o) => (o.name === result.name ? result : o)),
        }
    )
  }

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <h1 className="min-w-0 text-xl font-semibold">{jobTitle(job)}</h1>
          <Button variant="outline" size="sm" onClick={() => onReuse(job)}>
            <CopyPlus />
            New job from this
          </Button>
        </div>
        <p role="status" className="text-sm text-muted-foreground">
          {reconnecting
            ? "Lost the connection to the server, reconnecting…"
            : statusText(job)}
        </p>
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        <JobProgress steps={job.steps} />
        <UsageMeter job={job} />
        {job.error && (
          <p role="alert" className="text-sm text-destructive">
            {job.error}
          </p>
        )}
      </div>

      {job.brief && (
        <div className="grid items-start gap-6 lg:grid-cols-2">
          <SourcePane
            source={job.source}
            brief={job.brief}
            selection={traced}
          />
          <div className="space-y-6">
            {job.outputs.map((o) => (
              <OutputPanel
                key={o.name}
                jobId={job.id}
                result={o}
                brief={job.brief!}
                language={job.config.language}
                selectedPath={
                  selection?.format === o.name ? selection.path : null
                }
                onSelect={(path) =>
                  setSelection(path === null ? null : { format: o.name, path })
                }
                onRevised={replaceOutput}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
