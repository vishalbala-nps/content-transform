import { useState, type ReactNode } from "react"
import { LoaderCircle, Sparkles } from "lucide-react"

import { FormatPicker } from "@/components/format-picker"
import { JobSettingsFields } from "@/components/job-settings"
import { SourceInput, type SourceKind } from "@/components/source-input"
import { Button } from "@/components/ui/button"
import { createJob, createJobFromFile, createJobFromUrl } from "@/lib/api"
import { LANGUAGES } from "@/lib/settings"
import type { BrandKit, FormatInfo, Job, JobSettings } from "@/lib/types"

// The form for a new job: a source, the formats, the settings. Its draft is
// held by App, so it survives a visit to another view.

export interface JobDraft {
  source: SourceKind // the tab showing, which is the one the job uses
  text: string
  file: File | null
  url: string
  // Formats chosen, by name. Null until the user or a reused job chooses:
  // every format.
  selected: Set<string> | null
  settings: JobSettings
}

function Section({
  step,
  title,
  children,
}: {
  step: number
  title: string
  children: ReactNode
}) {
  return (
    <section className="space-y-3" aria-label={title}>
      <h2 className="flex items-center gap-2 text-sm font-medium">
        <span
          aria-hidden
          className="flex size-5 items-center justify-center rounded-full bg-foreground text-[11px] text-background tabular-nums"
        >
          {step}
        </span>
        {title}
      </h2>
      {children}
    </section>
  )
}

export function NewJobView({
  draft,
  onDraftChange,
  formats,
  formatsError,
  sourceTypes,
  kits,
  onKitsChange,
  onCreated,
}: {
  draft: JobDraft
  onDraftChange: (change: (draft: JobDraft) => JobDraft) => void
  formats: FormatInfo[]
  formatsError: string | null
  sourceTypes: string[]
  kits: BrandKit[]
  onKitsChange: (update: (kits: BrandKit[]) => BrandKit[]) => void
  onCreated: (job: Job) => void
}) {
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { text, file, url, settings } = draft
  // Without the upload list, the file tab is hidden: fall back to text.
  const source =
    draft.source === "file" && sourceTypes.length === 0 ? "text" : draft.source
  const selected = draft.selected ?? new Set(formats.map((f) => f.name))

  // An opened job may name a kit deleted since; the job is made without it
  // rather than refused.
  const kit = kits.find((k) => k.kit_id === settings.brand_kit_id) ?? null
  const effectiveSettings: JobSettings = kit
    ? settings
    : { ...settings, brand_kit_id: null }

  function update(change: Partial<JobDraft>) {
    setError(null)
    onDraftChange((d) => ({ ...d, ...change }))
  }

  // Another job may be running: the new one queues behind it.
  async function run() {
    if (submitting) return
    const link = url.trim()
    const missing =
      source === "text" && !text.trim()
        ? "Paste some text first."
        : source === "file" && !file
          ? "Choose a file first."
          : source === "url" && !link
            ? "Enter a link first."
            : null
    if (missing) {
      setError(missing)
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
      const created =
        source === "file" && file
          ? await createJobFromFile(file, names, effectiveSettings)
          : source === "url"
            ? await createJobFromUrl(link, names, effectiveSettings)
            : await createJob(text, names, effectiveSettings)
      onCreated(created)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSubmitting(false)
    }
  }

  const summary = [
    `${selected.size} format${selected.size === 1 ? "" : "s"}`,
    LANGUAGES[settings.language].name,
    kit ? kit.org_name : "house style",
  ].join(" · ")
  const message = error ?? formatsError

  return (
    <div className="mx-auto max-w-4xl">
      <div className="space-y-8 pb-6">
        <div className="space-y-1">
          <h1 className="text-xl font-semibold">New job</h1>
          <p className="max-w-prose text-sm text-muted-foreground">
            Give Spectra one source. It reads it once into a brief, writes each
            format you choose from that brief, and checks every passage against
            the source.
          </p>
        </div>

        <Section step={1} title="Source">
          <SourceInput
            kind={source}
            onKindChange={(k) => update({ source: k })}
            text={text}
            onTextChange={(t) => update({ text: t })}
            file={file}
            onFileChange={(f) => update({ file: f })}
            url={url}
            onUrlChange={(u) => update({ url: u })}
            fileTypes={sourceTypes}
            onSubmit={run}
          />
        </Section>

        <Section step={2} title="Formats">
          <FormatPicker
            formats={formats}
            selected={selected}
            onChange={(s) => update({ selected: s })}
          />
        </Section>

        <Section step={3} title="Settings">
          <JobSettingsFields
            value={effectiveSettings}
            onChange={(s) => update({ settings: s })}
            kits={kits}
            onKitsChange={onKitsChange}
          />
        </Section>
      </div>

      {/* Stays in reach however long the form is. */}
      <div className="sticky bottom-0 -mx-4 flex flex-wrap items-center gap-x-4 gap-y-2 border-t bg-background/95 px-4 py-3 backdrop-blur md:-mx-6 md:px-6">
        <Button onClick={run} disabled={submitting || selected.size === 0}>
          {submitting ? (
            <LoaderCircle className="animate-spin" />
          ) : (
            <Sparkles />
          )}
          Generate
        </Button>
        {message ? (
          <span role="alert" className="text-sm text-destructive">
            {message}
          </span>
        ) : (
          <span className="text-sm text-muted-foreground">{summary}</span>
        )}
      </div>
    </div>
  )
}
