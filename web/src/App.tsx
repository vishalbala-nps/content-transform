import { useCallback, useEffect, useState, type CSSProperties } from "react"

import { AppHeader } from "@/components/app-header"
import { AppSidebar } from "@/components/app-sidebar"
import { BrandKitsView } from "@/components/brand-kits-view"
import { JobView } from "@/components/job-view"
import { NewJobView, type JobDraft } from "@/components/new-job-view"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"
import {
  listBrandKits,
  listFormats,
  listJobs,
  listSourceTypes,
} from "@/lib/api"
import { DEFAULT_SETTINGS, settingsFromConfig } from "@/lib/settings"
import { sameView, viewFromUrl, viewHref, type View } from "@/lib/view"
import type { BrandKit, FormatInfo, Job, JobSummary } from "@/lib/types"

// The shell: a title bar, the sidebar, and one view in the main pane, chosen
// by the URL (lib/view.ts). Data more than one view needs (formats, brand
// kits, the job list) and the new job's draft live here, so switching views
// loses nothing.

const EMPTY_DRAFT: JobDraft = {
  text: "",
  file: null,
  url: "",
  selected: null,
  settings: DEFAULT_SETTINGS,
}

// While any listed job is queued or running, the list is re-read this often,
// so statuses and titles in the sidebar keep up.
const HISTORY_POLL_MS = 2000

export function App() {
  const [view, setView] = useState<View>(viewFromUrl)
  const [formats, setFormats] = useState<FormatInfo[]>([])
  const [formatsError, setFormatsError] = useState<string | null>(null)
  const [sourceTypes, setSourceTypes] = useState<string[]>([])
  const [kits, setKits] = useState<BrandKit[]>([])
  const [history, setHistory] = useState<JobSummary[]>([])
  const [draft, setDraft] = useState<JobDraft>(EMPTY_DRAFT)
  // A job just submitted, shown until its first event arrives.
  const [created, setCreated] = useState<Job | null>(null)

  // History is a convenience: if it fails to load, the rest of the page still works.
  const refreshHistory = useCallback(() => {
    listJobs()
      .then(setHistory)
      .catch(() => {})
  }, [])

  useEffect(() => {
    listFormats()
      .then(setFormats)
      .catch((err) => setFormatsError(`Could not load formats: ${err.message}`))
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
    if (!history.some((j) => j.status === "queued" || j.status === "running"))
      return
    const timer = setTimeout(refreshHistory, HISTORY_POLL_MS)
    return () => clearTimeout(timer)
  }, [history, refreshHistory])

  useEffect(() => {
    const onPopState = () => setView(viewFromUrl())
    window.addEventListener("popstate", onPopState)
    return () => window.removeEventListener("popstate", onPopState)
  }, [])

  useEffect(() => {
    const title =
      view.kind === "new"
        ? "New job"
        : view.kind === "kits"
          ? "Brand kits"
          : (history.find((j) => j.id === view.id)?.title ?? "Job")
    document.title = `${title} · Spectra`
  }, [view, history])

  function navigate(to: View) {
    if (sameView(to, view)) return
    window.history.pushState(null, "", viewHref(to))
    setView(to)
    window.scrollTo(0, 0)
  }

  // The source is used up; formats and settings carry over to the next job.
  function onCreated(job: Job) {
    setCreated(job)
    setDraft((d) => ({ ...d, text: "", file: null, url: "" }))
    navigate({ kind: "job", id: job.id })
    refreshHistory()
  }

  // A file or link job comes back as the text it was read into, which is
  // what its brief was made from.
  function reuse(job: Job) {
    setDraft({
      text: job.source.markdown,
      file: null,
      url: "",
      selected: new Set(job.formats),
      settings: settingsFromConfig(job.config),
    })
    navigate({ kind: "new" })
  }

  return (
    <SidebarProvider
      className="flex-col"
      style={{ "--header-height": "3.5rem" } as CSSProperties}
    >
      <AppHeader onNavigate={navigate} />
      <div className="flex flex-1">
        <AppSidebar view={view} jobs={history} onNavigate={navigate} />
        <SidebarInset className="min-w-0 p-4 md:p-6">
          {view.kind === "new" && (
            <NewJobView
              draft={draft}
              onDraftChange={setDraft}
              formats={formats}
              formatsError={formatsError}
              sourceTypes={sourceTypes}
              kits={kits}
              onKitsChange={setKits}
              onCreated={onCreated}
            />
          )}
          {view.kind === "job" && (
            <JobView
              key={view.id}
              id={view.id}
              initial={created?.id === view.id ? created : null}
              onReuse={reuse}
            />
          )}
          {view.kind === "kits" && (
            <BrandKitsView kits={kits} onKitsChange={setKits} />
          )}
        </SidebarInset>
      </div>
    </SidebarProvider>
  )
}

export default App
