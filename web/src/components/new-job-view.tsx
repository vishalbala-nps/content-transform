import { useRef, useState } from "react"
import { FileUp, LoaderCircle, X } from "lucide-react"

import { JobSettingsFields } from "@/components/job-settings"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { createJob, createJobFromFile, createJobFromUrl } from "@/lib/api"
import type { BrandKit, FormatInfo, Job, JobSettings } from "@/lib/types"

// The form for a new job: a source, the formats, the settings. Its draft is
// held by App, so it survives a visit to another view.

export interface JobDraft {
  text: string
  // A chosen file, else a link, replaces the pasted text as the source.
  // Choosing one clears the other.
  file: File | null
  url: string
  // Formats chosen, by name. Null until the user or a reused job chooses:
  // every format.
  selected: Set<string> | null
  settings: JobSettings
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
  onKitsChange: (kits: BrandKit[]) => void
  onCreated: (job: Job) => void
}) {
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  const { text, file, url, settings } = draft
  const selected = draft.selected ?? new Set(formats.map((f) => f.name))

  // An opened job may name a kit deleted since; the job is made without it
  // rather than refused.
  const effectiveSettings: JobSettings = kits.some(
    (k) => k.kit_id === settings.brand_kit_id
  )
    ? settings
    : { ...settings, brand_kit_id: null }

  function update(change: Partial<JobDraft>) {
    onDraftChange((d) => ({ ...d, ...change }))
  }

  function toggle(name: string, on: boolean) {
    const next = new Set(selected)
    if (on) next.add(name)
    else next.delete(name)
    update({ selected: next })
  }

  // Another job may be running: the new one queues behind it.
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
      onCreated(created)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="space-y-1">
        <h1 className="text-xl font-semibold">New job</h1>
        <p className="text-sm text-muted-foreground">
          Give Spectra one source. It reads it once into a brief, writes each
          format you choose from that brief, and checks every passage against
          the source.
        </p>
      </div>

      <div className="space-y-2">
        <Label htmlFor="source">Source text</Label>
        <Textarea
          id="source"
          value={text}
          onChange={(e) => update({ text: e.target.value })}
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
                  update({ file: e.target.files?.[0] ?? null, url: "" })
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
                    onClick={() => update({ file: null })}
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
              update({ url: e.target.value, file: null })
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
        onChange={(s) => update({ settings: s })}
        kits={kits}
        onKitsChange={onKitsChange}
      />

      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={run} disabled={submitting || selected.size === 0}>
          {submitting && <LoaderCircle className="animate-spin" />}
          Generate
        </Button>
        {(error ?? formatsError) && (
          <span role="alert" className="text-sm text-destructive">
            {error ?? formatsError}
          </span>
        )}
      </div>
    </div>
  )
}
