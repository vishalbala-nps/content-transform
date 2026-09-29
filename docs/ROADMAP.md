# Roadmap

Built in vertical slices. Every slice ends with something openable in a
browser. No slice is "build the persistence layer".

Mark the current slice here so a fresh session knows where it is.

**Current slice: S9 (UI polish).** S8 is done; S6 and video are deferred (2026-09-29, see DECISIONS).

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
- **S4c — HTML (trafilatura) and URL input.** Done. `.html` upload or a link;
  a link to a PDF or DOCX goes through that ingester. Pages that only show an
  "enable JavaScript" notice are refused. Checked with curl, a real Ollama job
  from a CERT-In advisory URL and by hand in the browser.
- **Deferred — images and scanned PDFs**, read by a vision model into blocks.
  Needs Gemini quota or a vision model on Ollama; see DECISIONS.

**Done when:** a CERT-In advisory, as a text PDF and as its web page, produces
a brief whose claims cite the right blocks, with page numbers for the PDF.

Done. A real CERT-In advisory PDF and a real CERT-In advisory page both give
briefs whose claims cite the right blocks, checked on qwen3 (every claim
cited; date, severity, products and solution each point at their own block).
`qwen2.5:1.5b` sometimes returns no citations at all; the dev cache then
replays that answer, so test citations with `LLM_CACHE=0`. Still open, see
DECISIONS: pages that need JavaScript (iframe following, headless browser),
failing a job whose brief has no claims, and an eval run for the citation
schema change once evals resume.

## S5 — Renderers  ← highest value slice
Advisory -> branded PDF (WeasyPrint). Presentation -> real .pptx with speaker
notes (python-pptx). Download buttons in the UI.

This is where the project stops looking like a chat wrapper. Budget two
sittings; do not rush it.

- **S5a — file storage, downloads, exec summary PDF.** Done. Binary
  artifacts are saved under `storage/artifacts/`, every artifact downloads
  from its output card, and the executive summary adds a one-page WeasyPrint
  PDF in the house style. Checked with curl, a real Ollama job and by hand
  in the browser.
- **S5b — slide deck (python-pptx).** Done. Title slide, key figures, 4-7
  content slides, speaker notes on every slide, plus a markdown outline.
  Checked with curl, real Ollama jobs (qwen3 and qwen2.5:1.5b), by opening
  the decks in PowerPoint and by hand in the browser.
- **S5c — advisory PDF** for any source. Done. Security advisory, official
  notice, advisory or information bulletin, depending on the source; exact
  values (CVEs, versions, CVSS, IOCs, timeline, figures) are copied from the
  brief by the renderer, which now receives it. Checked with curl, real
  Ollama jobs (qwen3 and qwen2.5:1.5b) and by hand in the browser.

**Done when:** a judge can download a .pptx and open it in PowerPoint.

Done. Decks download from the browser and open in PowerPoint; the executive
summary and the advisory download as PDFs. Open for evals: invented numbers
in speaker notes, and press-release claims stated rather than attributed.

## S6 — Infographic  ← deferred, with video
Deferred again on 2026-09-29 for time: it will be done later, together with
video output. Not dropped: the problem statement asks for infographic
content, and the flagship demo cache captures every format, so a demo built
before S6 would be rebuilt after it.

Write three or four SVG templates **by hand first** (stat grid, timeline,
comparison, process flow), then write the schema and prompt to fill them.
Doing it the other way round produces schemas the templates cannot render.

**Done when:** an infographic PNG downloads and looks deliberate.

## S7 — Grounding and review
Claim-to-block linking. Amber highlight for unsupported sentences.
Regenerate one section or one slide without re-running the whole job.
Source and output side by side.

- **S7a — grounding report.** Done. Every prose field of a format's payload
  is matched to the brief items behind it by one extra model call per
  format, plus a code check for numbers not in the brief. The report is on
  each format result; the output card shows a count for now. Jobs whose
  brief has no claims fail. Checked on Gemini (`gemini-3.5-flash-lite`) with
  two fixtures, directly and through the API: every grounding call validated
  first time (4-11 s each). Of 82 passages on the security advisory, the only
  two flags were both real (the advisory's "thousands of appliances" for the
  source's "an estimated 4,200", and an invented "data exfiltration").
  Hashtags and closing questions came back not_factual. Older jobs load
  without a report.
- **S7b — review UI.** Done. The source's blocks sit beside the outputs,
  with the brief as a second tab. Each output card opens on Review, a list
  of its passages: flagged ones are amber with their reasons, and a partly
  supported one has just the unsupported words marked. A "Flagged only"
  filter narrows the list. Clicking a passage lists the brief items it
  rests on and highlights them, and their blocks, in the left pane, which
  scrolls to them. The Text tab keeps the old view. Checked in headless
  Chrome on the security advisory fixture, at desktop and phone width, and
  on a pre-S7 job, which still shows text only.
- **S7c — act on a passage.** Done. Select a passage to edit it (trusted,
  not re-checked), regenerate it (always a new model call, re-checked) or
  accept its flag. The format's files
  are rebuilt each time, so downloads carry the change. Checked on Gemini
  through the API and in headless Chrome.

Done. Open for evals: the grounding check misses lost qualifiers ("at
least 37" -> "37") and rounded figures in some formats but not others.

## S8 — Parameters, brand kit, i18n, polish
Full `GenerationConfig` surface in the UI. Brand kit consumed by renderers.
Indian language output via post-schema translation. Cost and token meter.

Brand kits are saved on the server. Languages: English, Hindi, Tamil,
Malayalam, Kannada, Telugu. UI polish is not part of S8; it comes later.

- **S8a — settings end to end.** Done. Audience, objective, tone, detail
  and style are chosen in the UI, stored on the job and read by every
  format prompt through one shared section; each format turns the detail
  level into its own targets and warns when one is missed. Evals take
  `--config`. Checked through the API with curl, in headless Chrome, and
  with eval runs at three configs. The executive + warn wording was
  tightened after the first run (14 flagged passages down to 6). Open:
  brief exec summaries of sources with many actions still run past 200
  words.
- **S8b — cost and token meter.** Done. Every model call's tokens and
  estimated cost are recorded per step (brief; each format's writing,
  grounding check and revisions) and shown under the job's progress,
  opening into a table. Evals print a usage line. Checked with uncached
  calls against the model's own token counts, through the API and in
  headless Chrome.
- **S8c — brand kits.** Done. Kits (organisation name, main and text
  colours, font, logo, banned phrases) are saved on the server and managed
  from a dialog beside the settings. A job keeps a copy of its kit. The
  PDFs and the deck take their colours, font, name and logo from it;
  banned phrases go into every format's prompt and are warned on.
  Without a kit the files are byte-identical to before. Checked through
  the API, in PowerPoint, and in headless Chrome.
- **S8d — Indian-language output.** Done. Hindi, Tamil, Malayalam, Kannada
  and Telugu. Each format is written, grounded and reviewed in English,
  then translated; files and their checks use the translation. Code checks
  numbers, digits and script, and retries a bad passage once on the
  stronger model. Fixed labels are translated once into
  `render/labels.json` (for a native speaker to check); PDFs embed bundled
  Noto fonts. Checked with an eval run per language, through the API, in
  headless Chrome, and English output unchanged. Open: Tamil and Telugu
  expand enough to push some posts past their character limits.

Done. Deferred from S8: UI polish.

The pre-cached flagship demo document moved out of S8: it captures every
format's output, so it is built after S6 (see Demo safety).

Evals resumed at the start of S8, since format prompts start reading the
config here. Baseline run `20260928-191922` (Gemini `gemini-3.5-flash-lite`,
cache on): 28/28 facts, 0 invented numbers, 0 IOC leaks, 2 format
warnings, 5 of 382 passages flagged.

## S9 — UI polish  ← current
UI changes and visual refinement, deferred from S8, from the user's
suggestions. The product is named Spectra. The single page becomes a title
bar, a sidebar (New job, Brand kits, the jobs) and one view beside it.

- **S9a — app shell.** Done. Title bar with a light/dark toggle, a sidebar
  that collapses to icons (a sheet on a phone) and one view per URL: `/`,
  `?job=<id>`, `?view=kits`. The New view keeps the old form and the job
  view the old results for now. Opening a job no longer fills the form;
  **New job from this** does. Generate is no longer blocked by a running
  job, which queues. Checked in headless Chrome at desktop and phone width.
- **S9b — New view.** Done. Numbered sections: the source as tabs (paste,
  upload with a drop zone, link), each keeping its own value; formats as
  tiles with what each makes (`OutputAdapter.description`, sent by
  `/api/formats`); settings in three groups (reader, output, brand). A bar
  pinned to the bottom holds Generate and a one-line summary. "New kit…"
  in the brand kit menu opens a one-kit editor dialog and chooses the kit
  it makes. That dialog replaced the old kit manager, so the Brand kits
  page already has Add and click-to-edit. The house style's name is now
  Spectra. Checked in headless Chrome at desktop and phone width.
- **S9c — job view.** Progress and usage until the brief exists, then the
  source and brief beside the outputs, one format at a time, chosen from a
  selector that shows each format's progress, flags and warnings; Copy and
  downloads in the format's header; a summary of the job's settings.
- **S9d — Brand kits page.** Kits listed with swatches, logo, font and
  banned phrases, and a row's menu that deletes after a confirmation. (Add
  and click-to-edit landed in S9b.)

**Done when:** a job goes from New to its review in the new layout, past
jobs and brand kits are reached from the sidebar, and every view works at
desktop and phone width.

## Later — noted 2026-09-29, not scheduled
In no particular order. Each is picked up as its own slice or part of one.

- **S6 infographic, together with video output** (see DECISIONS).
- **Ollama check of S8.** Settings, brand kits and above all translation were
  tested on Gemini only; a small local model may translate these languages
  poorly. The Ollama fallback is the offline plan for a demo.
- **Pre-cached flagship demo**, rebuilt once S6 lands (see Demo safety).
- **Docker Compose.** Named in the stack, not built yet. The image needs
  Pango for WeasyPrint; the Noto fonts are bundled already.
- **Open eval items:** grounding misses lost qualifiers ("at least 37" ->
  "37"); questions to the reader judged partly unsupported instead of
  not_factual; Tamil and Telugu translations running past character limits
  (a smaller English budget for languages that expand); brief exec
  summaries of sources with many actions past 200 words.
- **Translation follow-ups:** a native speaker to read `render/labels.json`;
  one rule for hashtags in translated posts (translated or kept in English).
- **PII scan** of public formats (ARCHITECTURE, `verify/pii.py`, not built).
- **Images and scanned PDFs** read by a vision model (deferred since S4).

---

## Eval harness — land at S2, not at the end

`evals/fixtures/` holds five source documents. `python -m evals.run_evals`
runs every format over every fixture and writes to a timestamped folder.

Roughly sixty lines. Without it, six weeks of prompt work is you re-reading
LinkedIn posts by hand with no idea whether last night's change helped.

## Demo safety

- Pre-cache one flagship document's complete output set as static files.
  Planned after S6 so the set includes the infographic; with S6 deferred, a
  cache built sooner is rebuilt once S6 lands.
- Keep the Ollama fallback working; campus wifi fails.
- Never demo with the dev LLM cache enabled.
