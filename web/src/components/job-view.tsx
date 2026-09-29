import { useEffect, useState, type ReactNode } from "react"
import { CopyPlus, LoaderCircle } from "lucide-react"
import { Tabs as TabsPrimitive } from "radix-ui"

import { FormatTabList } from "@/components/format-tabs"
import { JobProgress } from "@/components/job-progress"
import { OutputPanel } from "@/components/output-panel"
import { SourcePane } from "@/components/source-pane"
import { UsageMeter } from "@/components/usage-meter"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { useNow } from "@/hooks/use-now"
import { getMe, watchJob } from "@/lib/api"
import { resolveSelection, type SelectionKey } from "@/lib/grounding"
import { choiceLabel, LANGUAGES } from "@/lib/settings"
import { ago, fullTime } from "@/lib/time"
import { formatFromUrl, replaceFormatInUrl } from "@/lib/view"
import type { GenerationConfig, Job, Step } from "@/lib/types"

// One job, finished or still running. Its stage is read from the job, never
// stored: until the brief exists, the steps and their progress; from then
// on, the source and brief beside the outputs, one format at a time, with
// each format's progress on its pill. Mounted once per job id (App keys it),
// so opening another job starts from a clean slate.

function statusText(job: Job): string {
  switch (job.status) {
    case "queued":
      return "Queued"
    case "running": {
      if (!job.brief) return "Reading the source into a brief…"
      const done = job.outputs.length
      return `Writing formats: ${done} of ${job.formats.length} done…`
    }
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

function Setting({ name, children }: { name: string; children: ReactNode }) {
  return (
    <Badge variant="outline" className="max-w-full gap-1 font-normal">
      <span className="text-muted-foreground">{name}</span>
      {children}
    </Badge>
  )
}

// What the job was made with, so a past job can be read without opening
// "New job from this".
function SettingsSummary({ config }: { config: GenerationConfig }) {
  const kit = config.brand_kit
  const language = LANGUAGES[config.language]
  return (
    <ul className="flex flex-wrap gap-1.5" aria-label="Settings">
      <li>
        <Setting name="Audience">
          {choiceLabel("audience", config.audience)}
        </Setting>
      </li>
      <li>
        <Setting name="Objective">
          {choiceLabel("objective", config.objective)}
        </Setting>
      </li>
      <li>
        <Setting name="Tone">{choiceLabel("tone", config.tone)}</Setting>
      </li>
      <li>
        <Setting name="Detail">
          {choiceLabel("detail_level", config.detail_level)}
        </Setting>
      </li>
      <li>
        <Setting name="Language">
          {config.language === "en"
            ? language.name
            : `${language.native} · ${language.name}`}
        </Setting>
      </li>
      <li>
        <Setting name="Brand">
          {kit ? (
            <>
              <span
                aria-hidden
                className="size-2 rounded-full"
                style={{ background: kit.primary }}
              />
              {kit.org_name}
            </>
          ) : (
            "House style"
          )}
        </Setting>
      </li>
      {config.style && (
        <li className="max-w-full">
          <Setting name="Style">
            <span className="truncate" title={config.style}>
              {config.style}
            </span>
          </Setting>
        </li>
      )}
    </ul>
  )
}

// A format with no result yet: waiting its turn, being written, or cut short.
function Pending({ step }: { step: Step }) {
  const text = {
    pending: "Waiting its turn.",
    running: "Writing and checking this format…",
    skipped: "Not written: the job stopped before this format.",
    failed: "This format failed.",
    done: "Loading…",
  }[step.status]
  return (
    <Card>
      <CardContent className="flex items-center gap-2 text-sm text-muted-foreground">
        {step.status === "running" && (
          <LoaderCircle className="size-4 animate-spin" />
        )}
        {text}
      </CardContent>
    </Card>
  )
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
  // The format showing, from the URL at first. An unknown one means the first.
  const [format, setFormat] = useState<string | null>(formatFromUrl)
  // The passage being traced to the source.
  const [selection, setSelection] = useState<SelectionKey | null>(null)
  const now = useNow()

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
          // An event stream cannot say why it failed; if the session ended,
          // this answers 401 and the sign-in page takes over.
          getMe().catch(() => {})
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

  const formatSteps = job.steps.filter((s) => job.formats.includes(s.name))
  const shown = job.formats.includes(format ?? "") ? format! : job.formats[0]
  const traced = resolveSelection(selection, job.outputs)
  const active = job.status === "queued" || job.status === "running"

  function showFormat(name: string) {
    setFormat(name)
    // The highlight belonged to a passage no longer on screen.
    setSelection(null)
    replaceFormatInUrl(id, name)
  }

  // A revised passage comes back as its format's whole new result. The job
  // row already holds it; a finished job has no event stream to send it.
  function replaceOutput(result: Job["outputs"][number]) {
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
      <header className="space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 space-y-1">
            <h1 className="text-xl font-semibold">{jobTitle(job)}</h1>
            <p role="status" className="text-sm text-muted-foreground">
              <time dateTime={job.created_at} title={fullTime(job.created_at)}>
                {ago(job.created_at, now)}
              </time>
              {" · "}
              {reconnecting
                ? "Lost the connection to the server, reconnecting…"
                : statusText(job)}
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={() => onReuse(job)}>
            <CopyPlus />
            New job from this
          </Button>
        </div>
        <SettingsSummary config={job.config} />
        <UsageMeter job={job} />
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        {job.error && (
          <p role="alert" className="text-sm text-destructive">
            {job.error}
          </p>
        )}
      </header>

      {!job.brief ? (
        <Card className="max-w-xl">
          <CardHeader>
            <CardTitle>Progress</CardTitle>
            <CardDescription>
              {active
                ? "The brief comes first, then each format. The job keeps running if you close this tab."
                : "The job stopped before its brief was made."}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <JobProgress steps={job.steps} className="flex-col gap-y-2.5" />
          </CardContent>
        </Card>
      ) : (
        <div className="grid items-start gap-6 lg:grid-cols-2 xl:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
          <SourcePane
            source={job.source}
            brief={job.brief}
            selection={traced}
          />
          <TabsPrimitive.Root
            value={shown}
            onValueChange={showFormat}
            // Stacked on a phone, the output comes first: the source is
            // there to trace it.
            className="order-first min-w-0 lg:order-none"
          >
            {/* Stays under the title bar while a long review list scrolls. */}
            <div className="sticky top-(--header-height) z-10 -mx-1 bg-background px-1 py-2">
              <FormatTabList steps={formatSteps} outputs={job.outputs} />
            </div>
            {formatSteps.map((step) => {
              const result = job.outputs.find((o) => o.name === step.name)
              return (
                <TabsPrimitive.Content
                  key={step.name}
                  value={step.name}
                  className="mt-2 outline-none"
                >
                  {result ? (
                    <OutputPanel
                      jobId={job.id}
                      result={result}
                      brief={job.brief!}
                      language={job.config.language}
                      selectedPath={
                        selection?.format === result.name
                          ? selection.path
                          : null
                      }
                      onSelect={(path) =>
                        setSelection(
                          path === null ? null : { format: result.name, path }
                        )
                      }
                      onRevised={replaceOutput}
                    />
                  ) : (
                    <Pending step={step} />
                  )}
                </TabsPrimitive.Content>
              )
            })}
          </TabsPrimitive.Root>
        </div>
      )}
    </div>
  )
}
