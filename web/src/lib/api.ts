import type { FormatInfo, Job, JobSummary } from "@/lib/types"

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

export function createJob(text: string, formats: string[]): Promise<Job> {
  return request("/api/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, formats }),
  })
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
