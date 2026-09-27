# Roadmap

Built in vertical slices. Every slice ends with something openable in a
browser. No slice is "build the persistence layer".

Mark the current slice here so a fresh session knows where it is.

**Current slice: S2**

---

## S0 — Walking skeleton
Paste text into a box, one hardcoded LinkedIn prompt, one Gemini call, text on
screen. No database, no schemas, no job queue, no registry.

Exists to prove the key works and to give the architecture something real to
be refactored out of.

**Done when:** text in, post out, in a browser.

## S1 — The spine
Introduce `SourceDocument` and `ContentBrief` as real Pydantic models.
Text in -> brief -> LinkedIn post. Render the brief in the UI as its own panel.

**Done when:** the brief is visible and the LinkedIn post is generated only
from the brief, never from the raw text.

- **S1a — spine, static page.** Done.
- **S1b — React + Vite + Tailwind + shadcn/ui.** Done. Same API; FastAPI
  serves `web/dist`, Vite dev proxies `/api`.

## S2 — Registry and fan-out
Add X thread and Executive Summary as registered adapters. Multi-select in the
UI. Parallel generation with bounded concurrency and 429 backoff.

**Done when:** adding format #3 required zero edits to format #1.

Also land the eval harness this slice — see below.

## S3 — Jobs, persistence, progress
Move generation behind the `jobs` table. SSE progress. Job history. Results
survive a page refresh and a server restart.

**Done when:** you can close the tab mid-job and come back to a finished one.

## S4 — Ingestion
One ingester per sitting: PDF and DOCX (Docling), HTML (trafilatura), images
(PaddleOCR plus a vision caption). Each plugs into the ingest registry.

**Done when:** a screenshot of a CERT-In advisory produces a usable brief.

## S5 — Renderers  ← highest value slice
Advisory -> branded PDF (WeasyPrint). Presentation -> real .pptx with speaker
notes (python-pptx). Download buttons in the UI.

This is where the project stops looking like a chat wrapper. Budget two
sittings; do not rush it.

**Done when:** a judge can download a .pptx and open it in PowerPoint.

## S6 — Infographic
Write three or four SVG templates **by hand first** (stat grid, timeline,
comparison, process flow), then write the schema and prompt to fill them.
Doing it the other way round produces schemas the templates cannot render.

**Done when:** an infographic PNG downloads and looks deliberate.

## S7 — Grounding and review
Claim-to-block linking. Amber highlight for unsupported sentences.
Regenerate one section or one slide without re-running the whole job.
Source and output side by side.

## S8 — Parameters, brand kit, i18n, polish
Full `GenerationConfig` surface in the UI. Brand kit consumed by renderers.
Indian language output via post-schema translation. Cost and token meter.
Pre-cached flagship demo document.

---

## Eval harness — land at S2, not at the end

`evals/fixtures/` holds five source documents. `python -m evals.run_evals`
runs every format over every fixture and writes to a timestamped folder.

Roughly sixty lines. Without it, six weeks of prompt work is you re-reading
LinkedIn posts by hand with no idea whether last night's change helped.

## Demo safety

- Pre-cache one flagship document's complete output set as static files.
- Keep the Ollama fallback working; campus wifi fails.
- Never demo with the dev LLM cache enabled.
