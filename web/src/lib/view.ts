// What the main pane shows, kept in the URL so a refresh, a reopened tab or
// a shared link shows the same thing. Query strings rather than paths, so
// FastAPI serves the page from `/` without a fallback route.
//   /             a new job
//   ?job=<id>     a job, finished or still running
//   ?view=kits    the brand kits

export type View =
  { kind: "new" } | { kind: "job"; id: string } | { kind: "kits" }

export function viewFromUrl(): View {
  const params = new URLSearchParams(window.location.search)
  const job = params.get("job")
  if (job) return { kind: "job", id: job }
  if (params.get("view") === "kits") return { kind: "kits" }
  return { kind: "new" }
}

export function viewHref(view: View): string {
  switch (view.kind) {
    case "new":
      return "/"
    case "job":
      return `?job=${encodeURIComponent(view.id)}`
    case "kits":
      return "?view=kits"
  }
}

export function sameView(a: View, b: View): boolean {
  return a.kind === b.kind && (a.kind !== "job" || a.id === (b as typeof a).id)
}
