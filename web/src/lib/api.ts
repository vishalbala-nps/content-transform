import type {
  FormatInfo,
  FormatResult,
  Job,
  JobSettings,
  JobSummary,
} from "@/lib/types"

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init)
  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    const detail =
      typeof body.detail === "string"
        ? body.detail
        : JSON.stringify(body.detail)
    throw new Error(detail || `HTTP ${res.status}`)
  }
  return body as T
}

export function isFinished(job: Job): boolean {
  return job.status === "done" || job.status === "failed"
}

export function listFormats(): Promise<FormatInfo[]> {
  return request("/api/formats")
}

export function createJob(
  text: string,
  formats: string[],
  settings: JobSettings
): Promise<Job> {
  return request("/api/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, formats, settings }),
  })
}

// Uploads a document; the server picks the ingester from its extension.
export function createJobFromFile(
  file: File,
  formats: string[],
  settings: JobSettings
): Promise<Job> {
  const body = new FormData()
  body.append("file", file)
  for (const f of formats) body.append("formats", f)
  body.append("settings", JSON.stringify(settings))
  return request("/api/jobs/upload", { method: "POST", body })
}

// The server downloads the page (or PDF, DOCX...) at `url` and ingests it.
export function createJobFromUrl(
  url: string,
  formats: string[],
  settings: JobSettings
): Promise<Job> {
  return request("/api/jobs/url", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, formats, settings }),
  })
}

// File extensions an upload may have, e.g. ".docx".
export function listSourceTypes(): Promise<string[]> {
  return request("/api/source-types")
}

// Where one of a job's artifacts downloads from, text or binary alike.
export function artifactUrl(
  jobId: string,
  format: string,
  filename: string
): string {
  return `/api/jobs/${jobId}/files/${encodeURIComponent(format)}/${encodeURIComponent(filename)}`
}

// Revising one passage of a format's output. Each returns the format's new
// result: payload, files, warnings and grounding, already saved on the job.
function revise(
  jobId: string,
  format: string,
  action: "edit" | "accept" | "regenerate",
  body: object
): Promise<FormatResult> {
  return request(
    `/api/jobs/${jobId}/outputs/${encodeURIComponent(format)}/${action}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }
  )
}

// The reviewer's text is trusted: it is not checked against the brief.
export function editPassage(
  jobId: string,
  format: string,
  path: string,
  text: string
): Promise<FormatResult> {
  return revise(jobId, format, "edit", { path, text })
}

// `accepted: false` undoes an earlier accept.
export function acceptPassage(
  jobId: string,
  format: string,
  path: string,
  accepted: boolean
): Promise<FormatResult> {
  return revise(jobId, format, "accept", { path, accepted })
}

// Always asks the model again; the dev cache is skipped.
export function regeneratePassage(
  jobId: string,
  format: string,
  path: string
): Promise<FormatResult> {
  return revise(jobId, format, "regenerate", { path })
}

export function listJobs(): Promise<JobSummary[]> {
  return request("/api/jobs")
}

// Follows a job over SSE. Every event is the job's full state, so a stream
// opened late, or reopened after the server restarts, needs nothing replayed.
// The browser reconnects by itself after a dropped connection; `onLost` is
// called while it does. Returns a function that stops watching.
export function watchJob(
  id: string,
  handlers: {
    onUpdate: (job: Job) => void
    onLost: () => void
    onFail: () => void
  }
): () => void {
  const source = new EventSource(`/api/jobs/${id}/events`)
  source.onmessage = (event) => {
    const job = JSON.parse(event.data) as Job
    handlers.onUpdate(job)
    // The server ends the stream here; close so the browser does not reconnect.
    if (isFinished(job)) source.close()
  }
  source.onerror = () => {
    // CLOSED means the browser gave up (e.g. a 404); otherwise it is retrying.
    if (source.readyState === EventSource.CLOSED) handlers.onFail()
    else handlers.onLost()
  }
  return () => source.close()
}
