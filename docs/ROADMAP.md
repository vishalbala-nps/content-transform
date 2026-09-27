# Roadmap

Built in vertical slices. Every slice ends with something openable in a
browser. No slice is "build the persistence layer".

Mark the current slice here so a fresh session knows where it is.

**Current slice: S4**

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

Done. Executive Summary was added as format #3 with a new module plus its
import and entry in `registry.py`; no other file in `app/`, `web/src/` or
`evals/` changed. Ollama fallback deferred (see DECISIONS).

## S3 — Jobs, persistence, progress
Move generation behind the `jobs` table. SSE progress. Job history. Results
survive a page refresh and a server restart.

**Done when:** you can close the tab mid-job and come back to a finished one.

Done. Checked with curl, a headless browser and by hand in a real browser,
including closing the tab and restarting the server mid-job.
`LLM_CACHE_DELAY_S` makes cached jobs slow enough to test this without quota.

## S4 — Ingestion
One ingester per sitting, each one module plus a line in
`app/ingest/registry.py`. No model calls: these inputs already have text.

- **S4a — upload plumbing + DOCX (python-docx).** Done. Checked with curl,
  a real Ollama job and by hand in the browser.
- **S4b — PDF with a text layer (PyMuPDF).** Done. Blocks carry page
  numbers; a PDF with no text layer is refused with a clear 422. Checked with
  curl, a real Ollama job and by hand in the browser.
- **S4c — HTML (trafilatura) and URL input.** Built. `.html` upload or a link;
  a link to a PDF or DOCX goes through that ingester. Pages that only show an
  "enable JavaScript" notice are refused. Checked with curl and a real Ollama
  job from a CERT-In advisory URL; the URL box still needs a check by hand.
- **Deferred — images and scanned PDFs**, read by a vision model into blocks.
  Needs Gemini quota or a vision model on Ollama; see DECISIONS.

**Done when:** a CERT-In advisory, as a text PDF and as its web page, produces
a brief whose claims cite the right blocks, with page numbers for the PDF.

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
