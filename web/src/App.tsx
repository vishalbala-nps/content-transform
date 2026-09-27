import { useCallback, useEffect, useRef, useState } from "react"
import { LoaderCircle } from "lucide-react"

import { BriefPanel } from "@/components/brief-panel"
import { JobHistory } from "@/components/job-history"
import { JobProgress } from "@/components/job-progress"
import { OutputPanel } from "@/components/output-panel"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  createJob,
  isFinished,
  listFormats,
  listJobs,
  watchJob,
} from "@/lib/api"
import type { FormatInfo, Job, JobSummary } from "@/lib/types"

// The open job lives in the URL (?job=<id>), so a refresh, a reopened tab or
// a shared link shows the same job, finished or still running.
function jobIdFromUrl(): string | null {
  return new URLSearchParams(window.location.search).get("job")
}

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

export function App() {
  const [text, setText] = useState("")
  const [formats, setFormats] = useState<FormatInfo[]>([])
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [jobId, setJobId] = useState<string | null>(jobIdFromUrl)
  const [job, setJob] = useState<Job | null>(null)
  const [reconnecting, setReconnecting] = useState(false)
  const [history, setHistory] = useState<JobSummary[]>([])
  // Opening an existing job (a link or the history list) fills the form with
  // its input. A job just submitted already matches the form.
  const fillForm = useRef(jobId !== null)

  // History is a convenience: if it fails to load, the rest of the page still works.
  const refreshHistory = useCallback(() => {
    listJobs()
      .then(setHistory)
      .catch(() => {})
  }, [])

  useEffect(() => {
    listFormats()
      .then((list) => {
        setFormats(list)
        // An opened job may already have chosen the formats.
        setSelected((prev) =>
          prev.size > 0 ? prev : new Set(list.map((f) => f.name))
        )
      })
      .catch((err) => setError(`Could not load formats: ${err.message}`))
    refreshHistory()
  }, [refreshHistory])

  useEffect(() => {
    function onPopState() {
      fillForm.current = true
      setError(null)
      setJobId(jobIdFromUrl())
    }
    window.addEventListener("popstate", onPopState)
    return () => window.removeEventListener("popstate", onPopState)
  }, [])

  useEffect(() => {
    if (!jobId) return
    return watchJob(jobId, {
      onUpdate: (j) => {
        setReconnecting(false)
        setJob(j)
        if (fillForm.current) {
          fillForm.current = false
          setText(j.source.markdown)
          setSelected(new Set(j.formats))
        }
        if (isFinished(j)) refreshHistory()
      },
      onLost: () => setReconnecting(true),
      onFail: () => {
        setReconnecting(false)
        setError("Could not load this job.")
      },
    })
  }, [jobId, refreshHistory])

  // Until the first event for a newly opened job arrives, show nothing rather
  // than the previous job.
  const current = job && job.id === jobId ? job : null
  const busy = submitting || (current !== null && !isFinished(current))

  function openJob(id: string, fill: boolean) {
    if (id === jobId) return
    fillForm.current = fill
    setError(null)
    window.history.pushState(null, "", `?job=${id}`)
    setJobId(id)
  }

  function toggle(name: string, on: boolean) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (on) next.add(name)
      else next.delete(name)
      return next
    })
  }

  async function run() {
    if (!text.trim()) {
      setError("Paste some text first.")
      return
    }
    if (selected.size === 0) {
      setError("Choose at least one format.")
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      // Keep the server's order, which is the order the formats are listed in.
      const names = formats.map((f) => f.name).filter((n) => selected.has(n))
      const created = await createJob(text, names)
      setJob(created)
      openJob(created.id, false)
      refreshHistory()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="mx-auto max-w-6xl space-y-6 px-4 py-8">
      <h1 className="text-xl font-semibold">Content Transform</h1>

      <div className="space-y-2">
        <Label htmlFor="source">Source text</Label>
        <Textarea
          id="source"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Paste an article, report or advisory…"
          className="min-h-56"
        />
      </div>

      <fieldset className="space-y-2">
        <legend className="text-sm font-medium">Formats</legend>
        <div className="flex flex-wrap gap-x-6 gap-y-2">
          {formats.map((f) => (
            <div key={f.name} className="flex items-center gap-2">
              <Checkbox
                id={`format-${f.name}`}
                checked={selected.has(f.name)}
                onCheckedChange={(on) => toggle(f.name, on === true)}
              />
              <Label htmlFor={`format-${f.name}`} className="font-normal">
                {f.label}
              </Label>
            </div>
          ))}
        </div>
      </fieldset>

      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          <Button onClick={run} disabled={busy || selected.size === 0}>
            {busy && <LoaderCircle className="animate-spin" />}
            Generate
          </Button>
          <span role="status" className="text-sm text-muted-foreground">
            {reconnecting
              ? "Lost the connection to the server, reconnecting…"
              : current && statusText(current)}
          </span>
          {error && (
            <span role="alert" className="text-sm text-destructive">
              {error}
            </span>
          )}
        </div>
        {current && <JobProgress steps={current.steps} />}
        {current?.error && (
          <p role="alert" className="text-sm text-destructive">
            {current.error}
          </p>
        )}
      </div>

      {current?.brief && (
        <div className="grid items-start gap-6 lg:grid-cols-2">
          <BriefPanel brief={current.brief} source={current.source} />
          <div className="space-y-6">
            {current.outputs.map((o) => (
              <OutputPanel key={o.name} result={o} />
            ))}
          </div>
        </div>
      )}

      <JobHistory
        jobs={history}
        currentId={jobId}
        onOpen={(id) => openJob(id, true)}
      />
    </main>
  )
}

export default App
