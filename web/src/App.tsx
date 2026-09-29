import { useCallback, useEffect, useRef, useState } from "react"
import { FileUp, LoaderCircle, X } from "lucide-react"

import { JobHistory } from "@/components/job-history"
import { JobProgress } from "@/components/job-progress"
import { JobSettingsFields } from "@/components/job-settings"
import { OutputPanel } from "@/components/output-panel"
import { SourcePane } from "@/components/source-pane"
import { UsageMeter } from "@/components/usage-meter"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  createJob,
  createJobFromFile,
  createJobFromUrl,
  isFinished,
  listBrandKits,
  listFormats,
  listJobs,
  listSourceTypes,
  watchJob,
} from "@/lib/api"
import { resolveSelection, type SelectionKey } from "@/lib/grounding"
import { DEFAULT_SETTINGS, settingsFromConfig } from "@/lib/settings"
import type {
  BrandKit,
  FormatInfo,
  FormatResult,
  Job,
  JobSettings,
  JobSummary,
} from "@/lib/types"

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
  // A chosen file, else a link, replaces the pasted text as the source.
  // Choosing one clears the other.
  const [file, setFile] = useState<File | null>(null)
  const [url, setUrl] = useState("")
  const [sourceTypes, setSourceTypes] = useState<string[]>([])
  const fileInput = useRef<HTMLInputElement>(null)
  const [formats, setFormats] = useState<FormatInfo[]>([])
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [settings, setSettings] = useState<JobSettings>(DEFAULT_SETTINGS)
  const [kits, setKits] = useState<BrandKit[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [jobId, setJobId] = useState<string | null>(jobIdFromUrl)
  const [job, setJob] = useState<Job | null>(null)
  const [reconnecting, setReconnecting] = useState(false)
  const [history, setHistory] = useState<JobSummary[]>([])
  // The passage being traced to the source. Belongs to one job, so opening
  // another job clears it.
  const [selection, setSelection] = useState<SelectionKey | null>(null)
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
    // Without the list, uploading is hidden and pasting still works.
    listSourceTypes()
      .then(setSourceTypes)
      .catch(() => {})
    // Without the list, jobs still run in the house style.
    listBrandKits()
      .then(setKits)
      .catch(() => {})
    refreshHistory()
  }, [refreshHistory])

  useEffect(() => {
    function onPopState() {
      fillForm.current = true
      setError(null)
      setSelection(null)
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
          setFile(null)
          setUrl("")
          setText(j.source.markdown)
          setSelected(new Set(j.formats))
          setSettings(settingsFromConfig(j.config))
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
  const traced = current && resolveSelection(selection, current.outputs)
  // An opened job may name a kit deleted since; the next job is made
  // without it rather than refused.
  const effectiveSettings: JobSettings = kits.some(
    (k) => k.kit_id === settings.brand_kit_id
  )
    ? settings
    : { ...settings, brand_kit_id: null }

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

  function openJob(id: string, fill: boolean) {
    if (id === jobId) return
    fillForm.current = fill
    setError(null)
    setSelection(null)
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
    const link = url.trim()
    if (!file && !link && !text.trim()) {
      setError("Paste some text, upload a file or enter a link first.")
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
      const created = file
        ? await createJobFromFile(file, names, effectiveSettings)
        : link
          ? await createJobFromUrl(link, names, effectiveSettings)
          : await createJob(text, names, effectiveSettings)
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
          placeholder={
            file
              ? `Using ${file.name}. Remove the file to paste text instead.`
              : url.trim()
                ? `Using ${url.trim()}. Clear the link to paste text instead.`
                : "Paste an article, report or advisory…"
          }
          disabled={file !== null || url.trim() !== ""}
          className="min-h-56"
        />
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
          {sourceTypes.length > 0 && (
            <div className="flex flex-wrap items-center gap-2">
              <input
                ref={fileInput}
                type="file"
                accept={sourceTypes.join(",")}
                className="sr-only"
                tabIndex={-1}
                aria-hidden
                onChange={(e) => {
                  setFile(e.target.files?.[0] ?? null)
                  setUrl("")
                  setError(null)
                  // Lets the same file be chosen again after removing it.
                  e.target.value = ""
                }}
              />
              <Button
                variant="outline"
                size="sm"
                onClick={() => fileInput.current?.click()}
              >
                <FileUp />
                {file ? "Choose another file" : "Or upload a file"}
              </Button>
              {file ? (
                <span className="flex items-center gap-1">
                  {file.name}
                  <Button
                    variant="ghost"
                    size="icon-xs"
                    aria-label="Remove file"
                    onClick={() => setFile(null)}
                  >
                    <X />
                  </Button>
                </span>
              ) : (
                <span className="text-muted-foreground">
                  {sourceTypes.join(", ")}
                </span>
              )}
            </div>
          )}
          <Input
            type="url"
            value={url}
            onChange={(e) => {
              setUrl(e.target.value)
              setFile(null)
              setError(null)
            }}
            placeholder="Or paste a link to a web page or document: https://…"
            aria-label="Source link"
            className="h-7 min-w-64 flex-1"
          />
        </div>
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

      <JobSettingsFields
        value={effectiveSettings}
        onChange={setSettings}
        kits={kits}
        onKitsChange={setKits}
      />

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
        {current && <UsageMeter job={current} />}
        {current?.error && (
          <p role="alert" className="text-sm text-destructive">
            {current.error}
          </p>
        )}
      </div>

      {current?.brief && (
        <div className="grid items-start gap-6 lg:grid-cols-2">
          <SourcePane
            source={current.source}
            brief={current.brief}
            selection={traced}
          />
          <div className="space-y-6">
            {current.outputs.map((o) => (
              <OutputPanel
                key={o.name}
                jobId={current.id}
                result={o}
                brief={current.brief!}
                language={current.config.language}
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

      <JobHistory
        jobs={history}
        currentId={jobId}
        onOpen={(id) => openJob(id, true)}
      />
    </main>
  )
}

export default App
