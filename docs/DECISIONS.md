# Decision log

Append a dated entry whenever a scope or stack decision is made or reversed.
Newest at the bottom.

---

**One analysis, many renderings.**
The obvious build is one LLM call per output format straight from the source.
That produces artefacts that disagree with each other, costs N times the input
tokens, and is hard to ground. Instead the source is analysed once into a
`ContentBrief` and every format is generated from that. Consistency across
deliverables falls out for free, and cost stays roughly flat as formats are
added.

**Video output excluded.**
Not for cost — video input is free on the Gemini free tier too. It is excluded
because ASR + scene detection + keyframes + TTS + ffmpeg assembly is about a
week of work and is the most likely thing to be broken on demo day. The
`OutputAdapter` interface supports it; the adapter is roughly three functions
whenever it is worth adding. Frame this as scope discipline, not as a cost
constraint.

**Presentation output kept.**
Briefly considered cutting it alongside video. Reversed: it is one schema, one
generation call and about 150 lines of `python-pptx`, and it produces a
downloadable file. Without it every output in the project is a text box, which
is exactly what every other submission will show.

**Infographic renders, it does not describe.**
"Generate infographic content and layout recommendations" read literally means
more prose about an infographic, which is a weak deliverable. The model fills a
structured schema; hand-written SVG templates do the rendering.

**Gemini free tier as the default provider.**
Zero per-token cost on Flash models, generous context, native multimodal input.
The real constraint is requests per minute, not money — hence bounded
concurrency and backoff in the LLM client. Free-tier content may be used to
improve Google's products; acceptable for this stage, worth stating if asked.

**No Celery, no Redis.**
A broker plus a worker plus a result backend is three moving parts to run and
debug for zero demo value. A `jobs` table with `status` and `steps_json` plus
an asyncio task pool gives retries, progress and restart-survival in about 120
lines.

**No vector database.**
There is no retrieval requirement in this problem statement. The brief is the
context. Adding pgvector would be architecture theatre.

**Schema-constrained generation everywhere.**
Free-text parsing and regex over model output is the usual cause of demo-day
flakiness. Every call fills a JSON schema and is validated with Pydantic, with
one retry that appends the validation error.

**Renderers never call models.**
Keeps layout deterministic and makes the failure modes obvious. If a renderer
seems to need a model call, the schema is underspecified.

**Security as the hero domain.**
The problem statement's own wording (threat intelligence, advisories, incident
reports) points there. A system that understands CVSS and emits a correctly
structured advisory *and also* a tweet thread reads as engineered; a generic
"works on anything" demo reads as shallow.

**2026-09-27 — S0 frontend is a static HTML page, not React + Vite.**
S0 exists to prove the Gemini key and the request path end to end. A single
`web/index.html` served by FastAPI's `StaticFiles` does that with no Node
toolchain. React + Vite + Tailwind + shadcn/ui arrives in S1, when the brief
panel gives the UI enough to justify it. This is a sequencing choice, not a
change to the stack.

**2026-09-27 — Config from environment, no dotenv dependency.**
`uv run --env-file .env` loads `.env` natively, so `app/core/config.py` reads
`os.environ` directly instead of pulling in `python-dotenv` or
`pydantic-settings`. Revisit if config grows beyond a handful of keys.

**2026-09-27 — S1 split into S1a (spine) and S1b (React).**
S1a delivers the roadmap's "done when" on the existing static page: text in,
visible brief, LinkedIn post generated from the brief only. S1b is the React +
Vite + Tailwind + shadcn/ui migration on its own. Doing both at once doubled
the slice. Supersedes the timing (not the stack) in the S0 frontend entry above.

**2026-09-27 — ContentBrief contract settled.**
Filled in the parts ARCHITECTURE left open, and changed three things:
- `angles` is a fixed `Angles` model (`exec`, `technical`, `public`), not
  `dict[str, str]`. Adapters can rely on the keys, and open-ended dicts are a
  weak spot in schema-constrained generation.
- `domain` is one flat `DomainFields` with `kind` plus nullable/empty security
  fields, not a union per domain. Simpler for the model to fill.
- Added `title`; `Stat` and `TimelineItem` carry `support` like `Claim`, since
  numbers and dates are what grounding most needs to check.
The model fills everything except ids; code assigns `brief_id`, `doc_id` and
claim ids, and drops support ids that are not real blocks (an empty `support`
is the "unsupported" signal S7 will use). No `description=` on model-typed
fields and no defaults, because Gemini rejects keys beside a `$ref`.

**2026-09-27 — Format payloads are structured; code joins them.**
The LinkedIn schema was one `post: str`. Gemini intermittently dropped the
newlines inside it, so posts came back as one run-on paragraph. It is now
`hook` / `paragraphs` / `hashtags`, joined in `render()`. Same rule every S2
adapter follows: the model fills structure, code does layout.

**2026-09-27 — `angles` removed from ContentBrief; `source: SourceProfile` added.**
Reverses the `Angles` part of the entry above. Angles were per-audience
framings written at analysis time, which put an audience decision into a layer
that runs before any audience is chosen, and the field was easy to misread as
describing the source. Emphasis for a reader is now the format prompt's job,
driven by `GenerationConfig.audience`; a custom audience ("Other…" with free
text) will live there too, not in the brief.
What the brief was actually missing is provenance. `SourceProfile` records
`kind` (news article, government memo, advisory…), `origin`, `published` and
`tone`. The first three let outputs attribute claims: an informal news
article turned into an exec summary for officials must say "according to
<outlet>", not state it with the weight of a directive. `tone` describes
the source only; the analysis prompt writes all claims neutrally, which is what
makes informal-in, formal-out work.

**2026-09-27 — Default model is `gemini-3.5-flash-lite`.**
`gemini-2.5-flash` hit its free-tier cap after about 20 requests in one day of
S1 development. Flash-Lite allows about 500 requests a day, which dev work and
S2 fan-out need. Checked on both S1 samples: it accepts the ContentBrief schema,
cites valid blocks and fills the source profile correctly. It extracts fewer
claims than 2.5 Flash, and one post attributed a finding to the wrong body.
Revisit once evals exist: the brief is the hardest call, runs once per job,
and may deserve a stronger model than the per-format calls.

**2026-09-27 — Security is an optional extension block, not a flat domain.**
Reverses the flat `DomainFields` above. Every brief carried six security
fields, empty for most sources, which made security look like the core of the
brief. Now `ContentBrief.security: SecurityDetails | None` is null unless the
source is about security, and a future domain is another optional block.
Security stays the hero domain (the advisory format and the IOC policy depend
on structured CVEs, products, severity and IOCs); it is just no longer in the
way for other sources. `mitigations` moved out of security into a general
`actions` list with block support: government memos have directives and
reports have recommendations, and exec summaries need them regardless of domain.

**2026-09-27 — S1b frontend setup.**
Scaffolded with `shadcn init -t vite` (React 19, Vite 8, Tailwind 4, Radix
components, TypeScript). Kept the template's tooling as generated (ESLint,
Prettier, theme provider that follows the system dark mode). Decisions:
- The template uses `cn` (published by shadcn) as its class-merge helper
  instead of `clsx` + `tailwind-merge`; kept, since the shadcn CLI generates
  components against it.
- API types in `web/src/lib/types.ts` are hand-written mirrors of the Pydantic
  contracts. Generating them from FastAPI's OpenAPI schema would add a codegen
  step and a dependency; not worth it while the contracts are frozen. Revisit
  if they start drifting.
- One process in demo: FastAPI serves `web/dist` when it exists. In dev, Vite
  proxies `/api` to FastAPI. No Node server in production.

**2026-09-27 — Ollama fallback deferred past S2.**
S2 adds bounded concurrency, the dev cache and fan-out to `app/core/llm.py`
for Gemini only. The Ollama fallback CLAUDE.md requires is a separate piece of
work and does not block the S2 "done when". It must land before any demo;
until then the app has no offline path.

**2026-09-27 — Eval fixtures are synthetic, and evals score as well as record.**
Five invented source documents in `evals/fixtures/`, one per source kind the
brief distinguishes, with documentation-range IPs and `.example` domains so
IOC checks can run without real threat data. `expectations.json` gives each
fixture its expected classification, verbatim facts the brief must capture,
and IOCs that must never reach a public format. Scoring on top of the
roadmap's "write outputs to a timestamped folder" is what lets a run report
what moved instead of leaving it to reading outputs by eye.

**2026-09-27 — OutputAdapter contract settled.**
Written as `app/formats/base.py`, with four changes from the first sketch in
ARCHITECTURE:
- `schema` is a Pydantic class, not a JSON-schema dict: `complete_json`
  already takes one, and renderers get a validated, typed payload.
- `public: bool` added so the IOC policy (and later the PII scan) keys off a
  property of the format rather than a list of format names.
- `check(payload, artifacts) -> list[str]` added for soft warnings such as
  character limits. Each format owns its limits, so evals score a new format
  without being edited.
- `Artifact` is defined, text-only for now (`text`, plus `parts` and
  `part_limit` for threads). S5 will make `text` optional and add a storage
  path for binary artefacts; that change is expected, not a surprise.
`GenerationConfig` lives beside the adapter contract with defaults on every
field; prompts start reading it when the S8 controls exist.

**2026-09-27 — S2 fan-out: retry policy, API shape, format isolation.**
- Measured on the free tier: after about ten calls in ten seconds, requests
  are held until the 20 s deadline (504 DEADLINE_EXCEEDED) and then refused
  with 429. Lone requests sometimes get 504s too. Both clear after tens of
  seconds, so `llm.py` retries 429 and 504 itself with 5/10/20/40 s backoff
  plus jitter, outside the concurrency slot. The SDK keeps its short retries
  for other transient errors. Dropped connections (`httpx.ReadError`) are not
  retried by the SDK and are retried here too. A per-day quota is not retried.
- The API returns `outputs: list[FormatResult]` (artifacts, warnings, the
  filled payload, error) in registry order, and `GET /api/formats` feeds the
  UI's checkboxes. One format failing, for any reason, is reported on that
  format; the others still return.
- Executive summary is not public, so it gets the full brief including IOCs;
  its prompt says whether indicators exist without listing them.

**2026-09-27 — S3 jobs: one table, one worker, progress derived.**
- SQLAlchemy added (the stack already named it) for Postgres-compatible
  models; stdlib `sqlite3` would tie the code to SQLite. Tables come from
  `create_all`; no Alembic until a schema actually changes. Calls are
  synchronous on the event loop: single-row SQLite writes of about a
  millisecond, and with no await between reading a row and writing it back,
  parallel formats cannot overwrite each other's results.
- One `jobs` row holds the request, the ingested source, the brief and each
  format's result as JSON. No `steps_json` column, despite the "No Celery"
  entry above: every step's status follows from the job status plus which
  results exist, so the API derives it instead of storing it twice. Text-only
  artifacts live on the row; file storage arrives with S5's binaries.
- The source is ingested when the job is created, so an empty text is still a
  422 and the worker starts at the brief.
- One worker task, one job at a time, one server process. Model calls are
  capped process-wide, so parallel jobs would only share the same slots.
- A restart re-queues jobs left `running`; they resume after their last saved
  step (a saved brief is not rebuilt, finished formats are not rerun).
- SSE re-reads the job row every 0.5 s and sends the job's full state whenever
  it changed, then closes when the job finishes. No in-memory pub/sub, so a
  tab opened late or reconnecting after a restart needs nothing replayed.
  Uses FastAPI's built-in `fastapi.sse`, no extra dependency.
- `POST /api/generate` is replaced by `POST /api/jobs`, `GET /api/jobs`,
  `GET /api/jobs/{id}` and `GET /api/jobs/{id}/events`.
- Run uvicorn with `--timeout-graceful-shutdown 3`. Uvicorn otherwise waits
  indefinitely for open streams on shutdown or reload, i.e. until the watched
  job finishes, which can be over a minute under throttling.

**2026-09-27 — Ollama provider landed; switched by `LLM_PROVIDER`.**
Closes the "Ollama fallback deferred" entry above. `LLM_PROVIDER=gemini|ollama`
picks where every call in `complete_json` goes; nothing outside `llm.py`
knows which ran. It is a manual switch, not automatic failover: a job that
silently moved to a model twenty times slower would look like a hang, and the
two models' outputs differ enough that you should know which you are
reading. Details:
- Ollama is called over its HTTP API with httpx, already installed (and now
  declared) for the Gemini client. The `ollama` Python package would be a new
  dependency wrapping the same single POST.
- Schema-constrained as before: the Pydantic JSON schema goes in `format`.
  qwen3 fills the full `_BriefDraft` schema, `$ref`s and nullable blocks
  included, and validates first time.
- `think: false`, since qwen3's thinking would add minutes before any JSON.
- `num_ctx` is sent on every call (default 16384). Ollama's default window
  is 4096 tokens and it drops the start of a longer prompt without an error;
  the brief for one fixture already uses about 3,750. A call that fills the
  window fails with a message to raise `OLLAMA_NUM_CTX`.
- No retries (no quota to wait out) and a 600 s timeout: on an M4 with 16 GB
  the brief takes about 140 s and a three-format job about four minutes.
  Ollama runs the formats one after another, so `LLM_CONCURRENCY` stays 3.
- Default model `qwen3:latest`. It returned about 30 claims where the prompt
  asks for 5-15; judge Ollama quality with evals, not by eye.
- Eval runs record the provider, and "what moved" compares only runs from
  the same provider and model.

**2026-09-27 — S4 ships without images; PyMuPDF instead of Docling.**
- Images and scanned PDFs are deferred. Development runs on Ollama, since
  Gemini free-tier latency and quota are too tight to iterate on, and the
  Ollama models in use read text only. Every other S4 input is read by a
  library and works on either provider. The S4 "done when" moves from a
  screenshot to a CERT-In advisory as a text PDF and as its web page.
- When images return, a vision model fills `Block`s (code assigns the ids)
  instead of PaddleOCR: OCR flattens layout, and `paddlepaddle` is painful on
  Apple Silicon. That needs `complete_json` to accept image parts, and either a
  vision model on Ollama or images being Gemini-only. Grounding is weaker on
  such blocks, since their text is itself the model's reading of the image.
- Documents that already have text are parsed, not sent to the model: parsing
  gives deterministic block ids with page numbers for S7 grounding, and the
  same input on every run, which evals need. Cost is not the reason. Gemini 3
  does not charge for a PDF's embedded text, and page images cost about what
  the extracted text would.
- PyMuPDF over Docling for PDFs. Docling brings torch, layout models and its
  own OCR, which is deferred anyway; PyMuPDF gives text blocks with page
  numbers. PyMuPDF is AGPL, acceptable unless this ships closed-source.
- Upload is `POST /api/jobs/upload` (multipart) beside the JSON text route.
  `GET /api/source-types` serves the ingest registry's extensions, so a new
  ingester needs no UI edit. Added `python-multipart` (FastAPI needs it for
  uploads) and `python-docx`. Limits: 20 MB per file, and 100,000 characters
  of extracted text, the same as pasted text. `.txt` and `.md` uploads use the
  text ingester.
- DOCX structure comes from paragraph styles and Word numbering, plus typed
  bullets. Headings made only with bold or large text are read as paragraphs.

**2026-09-27 — S4b PDF ingester: layout rules, no layout model.**
PyMuPDF gives text lines with size, weight and position; `app/ingest/pdf.py`
turns them into blocks with page numbers using plain rules, not a layout
model (PyMuPDF suggests its `pymupdf_layout` add-on; not needed yet):
- Headings are lines at least 15% larger than the body size (levels by size)
  or short standalone bold lines, which is how advisories label sections.
- Lists are lines starting with a bullet or number, or an indented block of
  short lines, since Chrome and others draw bullets as graphics.
- Tables come from `find_tables()`. Anything over 12 columns or mostly empty
  is a figure the finder misread, and is read as text instead.
- Running headers and footers (repeated in the page margins, page numbers
  aside) are dropped. Vertical margin text is skipped.
- Blocks keep the PDF's stored order rather than being sorted by position:
  sorting interleaves the columns of two-column layouts.
- The title is the top-level heading on page 1, since the first heading can
  be a notice or banner.
- A PDF with no text on any page is refused as scanned; pages without text in
  an otherwise text PDF are listed in `meta["pages_without_text"]`.
Tested on Chrome-printed advisories (headers, graphic bullets, a ruled
table, two columns), scanned, mixed, encrypted and corrupt files, and a
15-page two-column arXiv paper (under a second). Known weak spots: author
grids on title pages and hanging-indent reference lists split oddly, and
tables without vertical rules can run cells together.

**2026-09-27 — Brief support ids are an enum of the document's block ids.**
Supersedes "drops support ids that are not real blocks" in the ContentBrief
entry above. `qwen2.5:1.5b` cited the right blocks but wrote the ids as
`"/b5"`, `"[b2]"` or `"[b6][b9][]"`, so every citation was dropped and every
claim looked unsupported. `build_brief` now builds its draft schema per
document, and each `support` list is an array of a `BlockId` enum holding
exactly that document's ids. Constrained decoding (Gemini and Ollama both)
then cannot emit anything else, and validation plus the one retry catch it
if a provider lets it through. Chosen over rewording the prompt (a small model
may ignore it) and over cleaning ids with a regex (CLAUDE.md: never regex a
model response). `schemas.py` is unchanged; only the draft the model fills is.
Empty support is still allowed and still means "unsupported" for S7.
Checked with Ollama on the advisory PDF, cache off: on the 1.5b model the old
schema kept 0 valid claim citations in 3 runs, the new one kept all of them
in 3 runs; on qwen3 both schemas gave the same brief (17-18 claims, all
cited). A 225-block paper works too (qwen3: 10 of 10 claims cited, 160 s).
Not yet run on Gemini; evals paused, so not scored.

**2026-09-27 — S4c HTML ingester and URL input.**
- HTML goes through trafilatura, added for boilerplate removal; the stdlib
  parser would leave that to us. Its XML output (not its markdown) is walked
  into blocks, so block types come from elements, not from re-parsing text.
- `favor_recall=True`. Default mode dropped whole lists (the affected
  versions in an advisory); precision mode dropped most of a real CERT-In
  advisory.
- CERT-In lays pages out with tables and trafilatura keeps every cell, menus
  and footers included. A table whose cells hold paragraphs is read as layout,
  and when one layout cell holds 60% or more of the text, only that cell is
  kept. Pages without layout tables never hit this rule.
- Bold-only short paragraphs are headings, as in the PDF ingester. CERT-In's
  section labels are bold through CSS, which trafilatura cannot see, so they
  stay paragraphs: still separate, citable blocks.
- trafilatura can drop the headings at the top of a page with no `<article>`
  or `<main>`. The page's first `<h1>` goes back in if it was lost; `<title>`
  is not used for this, since CERT-In's is "Advisories" or "Vulnerability".
- `POST /api/jobs/url` downloads with httpx (already a dependency, so not
  trafilatura's fetcher), 20 s timeout, same 20 MB cap as uploads. The
  response's content type picks the ingester, so a link to a PDF or DOCX
  works too. `meta["source_url"]` records the final URL after redirects.
- The server fetches any http(s) URL it is given, including addresses on its
  own network. Acceptable for a local, single-user tool with no auth (see
  "Out of scope"); a reason not to expose it publicly as it stands.
- Tested on two real CERT-In pages (advisory and vulnerability note), a
  Wikipedia article, an undeclared Latin-1 page and a PDF link. A full job
  from a real CERT-In advisory URL cited real blocks and filled the security
  block with the right CVEs, product and versions.

**2026-09-27 — Pages that need JavaScript are refused, not rendered.**
A PIB press release link produced only "JavaScript must be enabled...", and
every format was then written about that notice. The page is PIB's site
shell: the release loads in a same-site iframe, and the shell's only prose is
a `<noscript>` warning. The HTML ingester now drops short "enable JavaScript"
notices from any page, and if under 200 characters of paragraph or table text
remain (menus arrive as lists and do not count), refuses the page with a 422
telling the user to paste the text or upload the page saved as PDF.
Considered and deferred:
- Following same-site iframes. It would fix PIB (the iframe holds 6,295
  characters of release text against the shell's 257), but it is a rule for
  one kind of site so far.
- Failing a job whose brief has no claims. Formats currently write from an
  empty brief; this guard would catch any bad source, not only this kind.
- A headless browser (Playwright + Chromium) to run page JavaScript: hundreds
  of MB, seconds per page and another demo-day failure point, for a case paste
  and PDF upload already cover.

**2026-09-27 — S5a: binary artifacts, file storage, WeasyPrint PDFs.**
- `Artifact` changed (frozen contract, agreed before editing): `text` is
  optional, `data: bytes` carries a binary from `render()` and is never
  serialised, and `path` is its storage key. `render()` stays free of I/O;
  the job saves the bytes, then writes the result to the row, so a result on
  the row always has its file. A crash between the two leaves an orphan file,
  which is harmless.
- Storage is `app/core/storage.py`, `save(key, data)` and `read(key)` over
  `storage/artifacts/`, keyed `<job>/<format>/<filename>`. ARCHITECTURE's
  "4-method interface" is two methods until something needs listing or
  deleting.
- One download route for every artifact, text or binary:
  `GET /api/jobs/{id}/files/{format}/{filename}`. It finds the artifact on the
  job row, so it can only serve what the job produced, never an arbitrary key.
- Formats that render a file also return their text artifact, so Copy keeps
  working: the exec summary is markdown plus a one-page PDF from one payload,
  with no schema or prompt change.
- Jinja2 added for templates: it autoescapes, and every value in a template
  is model output. `string.Template` does not escape, and S6's SVG templates
  need the same thing. Templates extend `render/templates/base.html`, one
  fixed house style (A4, running header and footer) until S8's brand kit.
- WeasyPrint gets a URL fetcher that allows no protocols, so nothing in a
  payload can make it read a local file or the network. It is imported inside
  `render_pdf`, so a machine without Pango fails the PDF formats with a clear
  message instead of refusing to start.
- WeasyPrint needs Pango (`brew install pango`). uv's Python does not search
  Homebrew's lib directory, so `.env` sets
  `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib`; it has to be in the
  environment when the process starts, which `uv run --env-file` does.
- `render()` runs in `asyncio.to_thread`: a PDF takes 0.1-0.3 s, a deck will
  take longer, and either would stall every progress stream on the loop.

**2026-09-27 — No plain-text rule in the exec summary prompt; Ollama cannot see field descriptions.**
`qwen2.5:1.5b` sometimes writes markdown inside summary fields
(`- **Threat level**: ...`), which the PDF prints literally. A prompt rule
plus field descriptions asking for plain text was tried and reverted, since
it measured no better. Old prompt against new, same brief each time, cache off:
- qwen2.5:1.5b, 5 fixtures × 2: markdown in 1 of 10 summaries either way
  (4 of 88 fields old, 2 of 80 new).
- qwen3, 3 fixtures: none either way (0 of 35, 0 of 37).
- Gemini, earlier eval runs: none (0 of 102 fields).
So it is a quirk of the small dev model, not something the prompt needs.
A Pydantic validator rejecting markdown would enforce it on any model
through the existing retry, at the cost of a summary failing outright when
the retry also has markdown; not worth it for a model used only for plumbing.
Found along the way: Ollama's `format` only constrains decoding. The model
never reads the JSON schema, so no `Field(description=...)` in any schema,
the ContentBrief's included, reaches an Ollama model; only Gemini sees them.
Ollama's docs recommend also putting the schema in the prompt. Doing that in
`complete_json` would change every Ollama call, so it waits for evals.

**2026-09-27 — S5b: slide deck with python-pptx.**
- New format `deck` ("Slide deck"): one module, one registry line, and
  `render/pptx.py`. Nothing in the API, the UI or the other formats changed;
  the panel's download button and "PowerPoint" label came from S5a.
- The model fills content, code fixes the order: title slide, a key-figures
  slide when the brief has stats (up to 4, values verbatim), then 4-7 content
  slides of 2-4 bullets. No per-slide "kind" for the model to choose: every
  layout decision it could get wrong is one less. Every slide has speaker
  notes. Titles are takeaways ("Attackers are already exploiting the flaw"),
  not topic labels. Output is the .pptx plus a markdown outline with the
  notes, for Copy and for reading without PowerPoint.
- Not public, like the exec summary: an internal briefing deck. It says
  whether indicators of compromise exist without listing them.
- Limits are in the prompt as well as the schema, since Ollama models never
  see field descriptions. Over-long titles and bullets are `check()` warnings.
- `render/pptx.py` is a builder with one method per slide kind and knows
  nothing about the deck payload. Default template, resized to 16:9, colours
  from the PDF house style, Arial (on every PowerPoint and Keynote install).
  Titles stay real title placeholders, restyled, so outline view, the slide
  navigator and screen readers find them. Bullets are written as OXML
  (`a:buChar`), since python-pptx has no bullet API. Key-figure values share
  one size, chosen so the longest fits on one line (24-44 pt).
- `python-pptx` added (named in CLAUDE.md); it brings `xlsxwriter` with it.
- Checked in Microsoft PowerPoint itself: decks are opened and exported to
  PDF through AppleScript, which is also the roadmap's "opens in PowerPoint"
  test. On qwen3, three fixtures gave valid decks first time (4-7 slides, one
  bullet over the word limit). One deck's speaker notes said "over 3,000
  appliances" where the brief says 4,200; the eval harness's invented-numbers
  score reads the whole payload, notes included, so it will measure this once
  evals resume, rather than the prompt being tuned on one output.
  `qwen2.5:1.5b` fills the schema too (all four formats in one job).

**2026-09-27 — S5c: `render()` receives the brief; advisory PDF for any source.**
- `OutputAdapter.render` is now `render(payload, config, brief)` (frozen
  contract, agreed before editing). An advisory's value is its exact facts:
  CVE ids, CVSS, versions, IOC hashes. Having the model copy them risks a
  changed digit nobody notices (qwen3 already invented a number in deck
  notes), so the renderer copies them from the brief and the model writes
  only prose. Rejected: the model copying everything (no contract change, but
  unchecked values), and a schema built per brief with enums of the brief's
  values (exact, but every schema becomes dynamic). The four existing
  adapters only gained the parameter.
- The IOC policy now covers rendering: the runner passes a public format a
  brief without IOCs, and without claims or actions that mention one, via
  `brief_for_render` beside `brief_for_prompt` in `brief_view.py`. The
  prompt view is byte-for-byte unchanged on all five fixtures.
- New format `advisory` ("Advisory"), not public: the one format that lists
  indicators. It works for any source; the header names the document by what
  it is: "Security advisory" when the brief has a security block, "Official
  notice" for a government memo, otherwise "Advisory" or "Information
  bulletin" by the status the model picks (`action_required` or
  `for_information`).
- Layout follows CERT-style advisories: status, severity and CVSS, CVE ids
  and audience at the top, summary, affected products, details, impact,
  actions, then key figures, timeline and indicators as tables from the
  brief. A heading and its table keep together, and a table longer than a
  page repeats its header. The prompt is told which tables will appear so the
  prose refers to them instead of copying lists.
- Checked on qwen3 with three fixtures: valid first time, no invented
  numbers, no indicators copied into the prose, sensible status for each
  source. Every indicator, the 64-character hash included, reads back from
  the PDF's text layer exactly as in the brief. `qwen2.5:1.5b` runs all five
  formats in one job. Open for evals: the press release's claims were stated
  rather than attributed to the company.

**2026-09-27 — S7 (grounding and review) before S6 (infographic).**
Neither slice depends on the other. S6 is one more format on the S5 pattern;
S7 works across all formats, and an infographic has almost no prose to
ground. S7's per-section regeneration is to be written generically over
formats, so the infographic joins it when S6 lands. S7's real dependencies
are brief citations (reliable on qwen3, sometimes empty on qwen2.5:1.5b, so
test on qwen3 with `LLM_CACHE=0`) and a way to score grounding, which the
paused evals would provide. Failing a job whose brief has no claims, still
open from S4, belongs in S7.

**2026-09-28 — S7 plan, and S7a: grounding checked after generation, per payload field.**
S7 is split into S7a (grounding report), S7b (review UI) and S7c
(regenerate one section). Decided for the whole slice:
- The unit of grounding is a payload field ("a passage": `slides[2].notes`,
  `tweets[0]`), not a sentence. Bullets, tweets and key points are about one
  sentence already. Splitting paragraphs into sentences would mean a regex
  over model output. For a partly supported passage the model quotes the
  unsupported words, and code keeps the quote only if it is a verbatim
  substring; otherwise the whole passage is flagged.
- Grounding is a separate check after generation (`app/verify/grounding.py`),
  not citations the format model writes as it goes. That would make every
  format schema dynamic per brief, which S5c rejected, and would have the
  writer mark its own work. The cost is one more model call per format;
  the Gemini key in use is now paid, so that is accepted.
- The review UI puts the source beside the outputs, with the brief in a
  tab or drawer (S7b).
- Regenerating a section is a request that waits and returns the new
  result, not a job sent back through the worker: the job is already done
  and its event stream closed. A section regenerates from the dev cache by
  default; a separate control forces a fresh model call (S7c).
S7a as built:
- Passages are found by walking the payload: every non-empty string that is
  not a `Literal` or `Enum` choice. No format declares anything, so a new
  format (the infographic) is grounded with no edit.
- The model sees the brief as items with ids (claims `c1`, stats `s1`,
  timeline `t1`, actions `a1`, entities `e1`, plus `src`, `tldr`, `sec`)
  and gives each passage a verdict: supported, partial, unsupported or
  not_factual (hashtags, questions to the reader). Passage and item ids are
  enums built per call, as block ids are for the brief, and a validator
  requires a verdict for every passage, so a skipped one gets the usual
  retry with the error appended.
- Code also lists numbers in each passage that appear nowhere in the brief,
  using the eval harness's `NUMBER` pattern, which now lives in
  `grounding.py`.
- A passage is flagged, with reasons, when it is unsupported or partial,
  has a number not in the brief, or rests on a claim, stat, timeline item or
  action that cites no source block. The source profile, entities and
  security details never carry citations, so resting on them is not a gap.
- Grounding runs against the full brief, IOCs included, for public formats
  too: it asks whether a passage is true to the source; whether it may be
  published is the IOC policy's job.
- The report is `FormatResult.grounding` (not a frozen contract). A failed
  grounding call keeps the format and its number check and records the
  error. Values that `render()` copies from the brief are not in the
  payload and are grounded by construction.
- A job whose brief has no claims now fails before any format is written,
  closing the item left open in S4.

**2026-09-28 — S7b: review works on passages, not on the rendered text.**
- The Review tab lists the payload's passages, not the markdown artifact.
  Grounding is per passage, and finding a passage again inside rendered
  markdown would mean matching text the renderer has rearranged. The Text
  tab keeps the rendered artifact, and Copy still copies that.
- Passages are labelled from their paths ("Slides 3 › notes"), so the UI
  still knows nothing about any format.
- The frontend rebuilds the brief's item ids (`c3`, `s1`, `src`...) in
  `web/src/lib/grounding.ts` to highlight them. The scheme is duplicated
  from `_items()` in `grounding.py`, and a comment on each side says so.
  Sending the items with every report was the alternative: the same list
  repeated once per format.
- Highlighting what a passage rests on is sky blue, not amber: amber means
  "needs review", blue means "look here".
- Added the shadcn `tabs` component (`shadcn add tabs`). It builds on
  `radix-ui`, already installed, so no new dependency.
- On a phone the panes stack and the source is not its own scroll area, so
  selecting a passage highlights its blocks but does not scroll to them.
  Acceptable for a review tool used on a laptop.
- Found while testing: on the security advisory the deck's speaker notes
  also say "thousands of appliances" for the source's "an estimated
  4,200", and the grounding check passed them there while flagging it in
  the advisory. Its verdicts are not consistent across formats. That needs
  measuring once evals resume, not a prompt change made from one example.

**2026-09-28 — S7c: edit, accept or regenerate one passage; edits are trusted.**
- A reviewer has three actions on any passage: edit it, regenerate it, or
  accept its flag (and undo that). Showing flags without a way to act on
  them left the PDF and deck shipping the flagged wording.
- Edited text is trusted, not checked against the brief (the user's call:
  the reviewer is the authority). It is marked "edited · not checked" and
  keeps no verdict, items or blocks, since those described the old text.
- A regenerated passage is the model's, so it is grounded again, alone
  (`ground(..., paths={path})`), and marked "regenerated". The prompt is the
  format's own prompt, so the brief view and IOC policy are the same, plus
  the current payload, the field's schema description and the passage's
  flag reasons, with "rewrite only this field".
- Accepting keeps the text and its reasons, struck through in the UI, and
  the passage stops counting as flagged.
- Every action works by payload path, so no format declares anything. Edit
  and regenerate put the text into the payload, validate it against the
  format's schema, then render, check and save the format exactly as the
  job does (`render_format` in the runner and `save_output` in jobs are
  shared with it). The Markdown, PDF and deck change together, under the
  same file names.
- Three `POST /api/jobs/{id}/outputs/{format}/{edit|accept|regenerate}`
  routes. Each waits and returns the format's new result, which the UI
  merges into the job, since a finished job's event stream has closed.
- Revisions run one at a time behind one lock, and write only their own
  format's result, re-reading the row just before, so they cannot overwrite
  another format even while the job is running.
- Regenerate uses the dev cache by default; "Regenerate (no cache)" skips
  reading it (`complete_json(..., cached=False)`; the answer is still
  stored). Since the prompt includes the current output, a repeat
  regenerate after a change is a new prompt and asks the model anyway;
  the cache only answers when the same output in the same state was
  rewritten before.
- Checked on Gemini through the API and in headless Chrome: accept and
  undo, an edit that removed "data exfiltration" from the advisory PDF, and
  regenerations of an advisory paragraph and of deck speaker notes, whose
  .pptx was rebuilt. The regenerated advisory paragraph fixed "thousands
  of" to "an estimated 4,200" but turned "at least 37" into "37", and the
  grounding check passed it: a second example of the check missing lost
  qualifiers, for the evals.

**2026-09-28 — One Regenerate button, always a fresh model call.**
Reverses "from the dev cache by default, with a no-cache control" above.
The regenerate prompt includes the current output, so after any change a
second regenerate is a new prompt and calls the model with either button.
The cache answered only when the same output, unchanged, was rewritten
before, which is a development case. Two buttons were noise for a
reviewer, and one who presses Regenerate wants a new attempt. The dev
cache is still read for everything else, and the rewrite is still stored.

**2026-09-28 — S8 before S6; the flagship demo after S6; evals resumed.**
- S8 (parameters, brand kit, i18n, cost meter) goes next, and S6
  (infographic) after it. Neither depends on the other: S7's grounding and
  review cover any new format without edits, so the infographic joins them
  when it lands. S8 first also helps S6, since its SVG templates can use
  the brand kit from the start instead of being retrofitted.
- S6 is deferred, not dropped. The problem statement asks for infographic
  content ("Infographic renders, it does not describe" above), so it must
  land before any submission or demo.
- The pre-cached flagship demo leaves S8 and is built after S6, since it
  captures every format's output and would otherwise be rebuilt.
- Video stays excluded. Adding it later reverses the "Video output
  excluded" entry, so it gets its own decision then, weighed against the
  week of work and demo-day risk recorded there.
- Evals resume at the start of S8, as CLAUDE.md requires after prompt
  changes: S8 is where format prompts start reading `GenerationConfig`.
  Testing concurrency and throttling stays paused. The harness now also
  scores grounding: flagged passages per format with their reasons,
  lower is better.
- Baseline run `20260928-191922`, Gemini `gemini-3.5-flash-lite`, cache on,
  all five formats on all five fixtures: 28/28 facts captured, kind and
  security right on 5/5, 0 unsupported brief items, 0 IOC leaks, 0
  invented numbers, 0 errors. 2 format warnings (government memo LinkedIn
  post 1,781/1,300 characters, exec summary 322/300 words). 5 of 382
  passages flagged: the two advisory flags already known, two
  embellishments in the incident-news summary and deck notes, and a
  research-report advisory's audience line, arguably a false flag since an
  audience is the writer's framing, not a claim.

**2026-09-28 — S8 scope: fixed audiences, saved brand kits, five Indian languages, polish later.**
- No free-text audience. Reverses the plan in the 2026-09-27 entry that
  removed `angles` ("a custom audience ... will live there too"): the
  audience stays one of the fixed values in `GenerationConfig`.
- Brand kits are saved on the server and chosen per job, not typed into
  each job.
- Output languages: English plus Hindi, Tamil, Malayalam, Kannada and
  Telugu. Nothing else until these work end to end.
- "Polish" (UI changes and visual refinement) leaves S8 and is done later.

**2026-09-28 — GenerationConfig and `check()` changed (frozen contract, agreed before editing).**
- `language` is one of `en`, `hi`, `ta`, `ml`, `kn`, `te`, not any string.
  `style` is capped at 300 characters.
- `brand_kit: BrandKit | None`. A job holds a copy of the saved kit made
  when it is created, not a reference, so editing a kit later never changes
  how an old job's files re-render after a passage is revised. The logo is
  a storage key; the runner loads its bytes into `logo_data` (excluded from
  serialisation, like `Artifact.data`) so `render()` still does no I/O.
  Logo files are named by content hash, so replacing a kit's logo leaves
  older jobs' logos in place. PNG or JPEG only: python-pptx cannot place SVG.
  The kit gives two colours; code derives the tints from them.
- `check(payload, artifacts, config)`: `detail_level` sets per-format
  targets (how many tweets, slides, words), and a check has to know the
  level to warn that one was missed. Evals score those warnings.
- Numbers stay in Western digits (0-9) in every output language. Devanagari,
  Tamil and the other native digit sets are rarely used, government
  documents included, and many readers do not know them. This also keeps
  the grounding number check meaningful for translated text.

**2026-09-28 — S8a: one settings section per prompt; formats own their detail targets.**
- One config applies to every format in a job. A format's prompt now says
  what the format is and its fixed rules; who reads it and in what voice
  come from `config_for_prompt()` (`formats/config_view.py`), one section
  shared by every format. The fixed readers and voices in the old prompts
  ("for a general audience", "for senior decision-makers", "formal and
  plain") are gone; "no hype" stays in every format. So at the default
  config (general public, neutral) the exec summary, deck and advisory are
  written for the public, not for executives as before.
- `detail_level` becomes per-format targets: LinkedIn 700/1,300/2,000
  characters, X 3-4/4-7/7-10 tweets, exec summary 2-3/3-5/5-7 points and
  150/300/450 words, deck 3-4/4-7/7-10 content slides, advisory 2-3/3-5/5-7
  detail paragraphs. "Standard" is close to what the formats produced
  before. Schemas allow the widest range; `check()` warns outside the
  chosen level's.
- The API takes a `settings` object (audience, objective, tone, detail,
  style), a JSON form field on uploads; unknown fields are refused, so
  `language` and a brand kit are 422 until S8c/S8d add them. `JobView`
  returns the config and an opened job fills the form with it. A blank
  style is stored as none.
- Select menus are the shadcn `select` component (`shadcn add select`),
  built on `radix-ui`, already installed.
- Evals take `--config` and compare only runs with the same config; runs
  from before S8 count as the default config.
- Eval runs (Gemini `gemini-3.5-flash-lite`, cache on, briefs cached):
  - Default config `20260928-194419` against baseline `20260928-191922`:
    28/28 facts, 0 IOC leaks, 0 errors unchanged; warnings 3 (+1: the
    incident-news LinkedIn post went to 1,511/1,300); invented numbers 2
    (+2), both in one deck writing "20,000" and "2,000" as "20000" and
    "2000", the same bullets dropping "minimum"; flagged passages 8 of 387
    (+3). One run, so not yet separable from run-to-run variation.
  - Executive, formal, brief, warn `20260928-194643`: 14 of 320 passages
    flagged, most of them consequences the brief does not state ("requires
    immediate executive review", "legal liabilities"). 4 of 5 exec
    summaries over the 150-word brief target (151-202).
  - Technical, detailed, instruct `20260928-194819`: 5 of 477 flagged,
    4 warnings (deck bullets over 16 words, one deck at 6 of 7-10 slides).

**2026-09-28 — S8a follow-ups: stated consequences only, brief summaries at 200 words, numbers compared without grouping.**
- The executive reader now leads with "the consequences and decisions the
  brief states" (was "what it means for the organisation"), and the warn
  purpose is "the risks the brief describes" (was "a risk and what it
  could mean for them"). Both invited consequences the source never gave.
- The brief-level exec summary target is 200 words, not 150. Its actions
  list carries every action in the brief, and six actions alone are about
  80 words. Listing only the three most urgent was rejected: an executive
  summary should not drop an action someone may need.
- The number check (grounding and evals) compares numbers without
  grouping commas (`number_value` in `grounding.py`), so "20000" matches
  "20,000", and Indian grouping ("2,00,000") matches too, which translated
  output will need. Decimal points and version dots still count: "98" does
  not match "9.8".
- Eval runs, against the S8a runs with the same config:
  - Default `20260928-200224` (all cached, only the number check moved):
    invented numbers 2 -> 0, flagged passages 8 -> 6 of 387.
  - Executive, formal, brief, warn `20260928-200225`: flagged 14 -> 6 of
    322, warnings 6 -> 4. The remaining flags include two questions to the
    reader judged partly unsupported (they should be not_factual) and a
    deck note turning "about 410,000 patients" into "hundreds of thousands",
    a real catch. Two exec summaries still exceed 200 words: the
    government memo's (282, seven actions) and the security advisory's
    (219, six actions).
  - Technical, detailed, instruct `20260928-200405`: unchanged (5 flagged,
    4 warnings); nothing in its prompts changed.

**2026-09-28 — Review: delete a passage's list entry.**
- A fourth review action beside edit, regenerate and accept. Delete
  removes the nearest list entry holding the passage: a paragraph, tweet,
  bullet, key point, detail, action or hashtag, and a whole slide or key
  figure when the passage is its title, notes, value or label. Fields
  outside any list (titles, summary, impact, bottom line) are required by
  every layout, so they have no Delete; the reviewer edits them instead.
  Emptying them and teaching each layout to skip empty sections was the
  alternative, and was not chosen.
- Worked out from the path, like the other actions, so no format declares
  anything (`list_entry` in `grounding.py`, mirrored by `listEntry` in
  `web/src/lib/grounding.ts`). The payload is validated after the delete,
  so a schema minimum holds: a thread keeps 3 tweets, a slide 2 bullets
  ("Cannot delete: at least 3 tweets are needed."). The format's files are
  rebuilt and saved as for an edit.
- Later entries in the list move up. Their passages keep their verdicts
  and reviews under the new paths rather than being grounded again: their
  text did not change.
- The UI asks for confirmation first, naming what goes ("Delete Slides 2,
  with everything in it?"), since a delete cannot be undone. The selection
  is cleared afterwards, as its path now belongs to the next entry.
- Checked through the API (thread minimum, a required title, an exec
  summary action gone from its markdown and PDF, a whole slide gone from
  the .pptx) and in headless Chrome driven over the DevTools protocol.

**2026-09-28 — S8b: usage metered by context, priced per call, one new column.**
- `complete_json` records every call's tokens (or a dev-cache hit) in
  `app/core/usage.py`. Code that wants a step's cost wraps it in
  `metered()`; every call inside the block counts, including calls in
  tasks it starts, since asyncio copies the context. Chosen over returning
  usage from `complete_json`, which would change every caller for
  bookkeeping.
- Recorded per step: the brief, and per format its writing, its grounding
  check and its revisions (a Regenerate's rewrite and re-check). Calls are
  recorded when they return, before validation: a response that fails it
  was still billed. A failed format, a failed brief and a failed
  regenerate all keep what they spent. A brief cut short by a restart adds
  to its earlier attempt instead of replacing it.
- Cost is worked out per call from the price table in `usage.py` when the
  call is made, so a later price change never rewrites an old job.
  `gemini-3.5-flash-lite` paid tier, Standard: $0.30 input, $0.03 cached
  input, $2.50 output (thinking included) per million tokens, from
  ai.google.dev/gemini-api/docs/pricing, updated 2026-09-24. A Gemini
  model not in the table is counted as unpriced, not free. Ollama is
  priced at zero. Dev-cache hits count as cached calls with no tokens and
  no cost, so a cached eval run shows $0; it measures spend, not what a
  job would cost uncached.
- Storage: a format's usage is on its `FormatResult`, in the JSON the job
  already stores. The brief has nowhere like that (`ContentBrief` is
  frozen), so jobs gain one nullable JSON column, `brief_usage`. Supersedes
  "no Alembic until a schema actually changes" for this case: `init_db`
  now adds any missing nullable column with `ALTER TABLE`, using the
  column's SQLAlchemy type, and refuses a missing required one. That
  covers a new nullable column on SQLite and Postgres alike; anything else
  still needs a real migration.
- The UI sums the parts itself rather than trusting a server total, since
  a revised passage replaces one output in the page. One line under the
  job's progress, "7 model calls · 9.2k tokens · est. $0.0080", opens into
  a table by step. Jobs from before S8b show no meter.
- Evals print a usage line per run (not scored: with the cache on it
  mostly measures what was cached).
- Checked with an uncached eval run (3 calls: token counts equal the
  model's own log lines, cost matches the table by hand, $0.0065), a fresh
  API job (brief $0.0025; each short format about $0.0009 to write and
  $0.0014 to check), a Regenerate (2 calls under revisions, generation
  untouched), a fully cached job ($0, calls counted as cached), the column
  step on a copy of the dev database, and the meter in headless Chrome.

**2026-09-28 — S8c: brand kits through a Theme; a job keeps its copy.**
- Saved kits live in a new `brand_kits` table (`create_all` makes it; no
  column step needed). Routes: list, create, edit, delete, upload and
  remove a logo, fetch the logo for the UI. A job's config holds a copy of
  its kit, so editing or deleting a kit never changes an old job, and a
  deck edited after its kit was deleted still re-renders with the kit it
  was made with.
- Renderers take a `Theme` (`render/theme.py`), never the kit, so
  `render/` still knows nothing about formats. `Theme()` is the house
  style; `Theme.branded()` derives the pale tint, muted text, hairlines
  and on-accent text from the kit's two colours with the proportions the
  house palette has. Without a kit, every PDF page and the deck XML were
  checked byte-identical to before the change.
- Kits are validated when saved, so rendering never has to guess:
  - Main colour at least 3:1 against white (WCAG large text: headings
    and white text on it), text colour at least 4.5:1. Too light is
    refused with the contrast figure, not silently darkened.
  - Font names: letters, digits, spaces and hyphens only, since the name
    is written into CSS. The organisation name is free text and never
    goes into CSS; it reaches the PDF header through `string-set` from an
    escaped element.
  - Logos: PNG or JPEG by content, readable by python-pptx, up to 1 MB.
    Stored as `brand/logos/<sha256>.<ext>` and never deleted, since a
    job's copy of a kit may name a logo the kit has since replaced.
- The PDF's URL fetcher now allows `data:` and nothing else. The logo is
  inlined as a data URI; `file:` and `https:` stay blocked (checked).
  Model text is escaped and cannot add an image.
- Logo placement: first page top right in PDFs; decks on a white panel on
  the title slide (a logo is usually drawn for a light background) and
  small in the top right of every other slide. Severity badges keep their
  own colours: a brand must not recolour "critical".
- Banned phrases go into the shared prompt section ("Never use these
  words or phrases") and the runner warns on any passage that still uses
  one, whole words, any case, for every format and after edits too. Eval
  `20260928-204753` banned "severe", "immediately" and "highlight": 20
  passages used them at the default config, 0 with the kit, and no
  warning fired. Format warnings were 7 against 3 (deck bullets one or
  two words over, one long LinkedIn post) and flagged passages 2 against
  6; every format was regenerated, so one run cannot tell those from
  variation. Without a kit the prompts are unchanged (the default run was
  all cache hits, scores unmoved).
- UI: a Brand kit menu in the settings (None is the house style) and a
  "Manage…" dialog, the shadcn `dialog` component (on `radix-ui`, already
  installed). A new kit is chosen for the next job; an opened job whose
  kit was deleted since starts the next job without one. FastAPI
  validation errors now show as their messages, not JSON.

**2026-09-28 — S8d: Indian-language output, translated after writing and checking.**
Decided with the user: review stays in English; fixed labels are
translated once and checked in; the brief's copied wording is translated
once per job, values never; Noto fonts are bundled.
- Order per format: write in English, ground against the English brief,
  translate the payload (one call), render and check the translation. The
  English payload stays what is grounded and reviewed
  (`FormatResult.payload`); the translation is `FormatResult.translation`.
  Edit and Regenerate change the English and translate that one passage
  again; Delete removes the same entry from both; Accept touches neither.
- Passages go to the model with ids and code puts each translation back at
  its path, as grounding does, so the structure cannot change.
- Code checks each translated passage: every number still there (by value,
  so Indian grouping "4,10,000" matches "410,000", and with no word
  boundary, since Kannada and Telugu attach endings to numbers: "2026ರ",
  "22న"); no native digits; no letters from another script; and, for four
  words or more, at least 15% of letters in the language's script. A
  passage that fails is sent once more with the problem named, to the
  stronger model (`GEMINI_STRONG_MODEL`, default `gemini-3.5-flash`):
  Flash-Lite repeated its own mistakes when asked again. What is still wrong
  becomes a warning, never a failure. Found in testing: Flash-Lite put
  Chinese for "bypass" (绕过) into Hindi twice, and returned a lone edited
  passage as Hindi in Latin letters; the retry fixed both.
- The translation prompt keeps names, product names, CVE ids, versions,
  abbreviations, URLs and hashes in Latin letters, numbers in Western
  digits, every qualifier and attribution, and security terms in their
  security sense ("compromise" is a breach, not an agreement, which both
  models got wrong without being told).
- Word limits (deck bullets and titles, exec summary and advisory summary
  words) are checked on English output only: they are set in English
  words, and Hindi writes case endings as separate words, so ten deck
  warnings on one Hindi deck meant nothing. Character limits (tweets,
  LinkedIn) and counts (tweets, slides, points) are checked on what ships.
- The brief's wording that renderers copy (figure labels, timeline dates and
  events, affected versions, the publication date) is translated once per
  job and stored in a new nullable column, `jobs.brief_translation`; its
  usage is added to the brief's.
- Fixed labels: `render/labels.json`, keyed by the English text, 54 labels,
  filled by `python -m tools.translate_labels` (a dev tool; render/ never
  calls a model). A label missing from the file fails in English too. The
  first pass with Flash-Lite had "Indicators of compromise" as "indicators
  of an agreement" and Tamil "Critical" as "complicated"; the tool now
  gives sense notes for ambiguous labels and uses `gemini-3.5-flash`,
  20 labels per call. The page footer is a label with {page} and {pages},
  since word order differs ("{pages} లో {page} వ పేజీ"). A native speaker
  should read the file before a demo.
- PDF fonts: with no font named, Pango fell back to Arial Unicode MS, which
  cannot shape these scripts (Telugu and Kannada vowel signs came apart).
  Noto Sans Devanagari, Tamil, Malayalam, Kannada and Telugu, regular and
  bold, are bundled in `render/fonts/` (1.2 MB, SIL Open Font License) and
  embedded for the job's language only, as data: URIs, so the fetcher rule
  is unchanged. They sit after the Latin fonts in the font list, so Latin
  text and digits keep the kit's or house font. PDFs stay about 20 KB.
  Text copied out of such a PDF is about 97% exact (a stray character per
  line, numbers intact); the markdown artifact, which Copy uses, is exact.
- Decks need nothing: PowerPoint shapes all five scripts with its own
  Indic fonts (Mangal, Latha, Kartika, Tunga, Gautami), checked on Mac.
- Hashtags are translated like any other passage, and the model sometimes
  keeps them in English; left as it is for now.
- Eval runs, all five fixtures and formats, English writing from the cache
  so only translation is new (after the number-check fix for kn and te):
  | Language | Run | Warnings | Expansion | Min script share | Cost |
  |---|---|---|---|---|---|
  | Hindi | 20260928-221745 | 3 | 1.03 | 0.63 | $0.11 |
  | Tamil | 20260928-221830 | 4 | 1.26 | 0.67 | $0.24 |
  | Malayalam | 20260928-222113 | 3 | 1.20 | 0.72 | $0.22 |
  | Kannada | 20260928-223403 | 3 | 1.12 | 0.76 | $0.24 |
  | Telugu | 20260928-223755 | 2 | 1.09 | 0.68 | $0.12 |
  28/28 facts and 6 flagged passages in each (grounding reads the English).
  No translation warnings remain. The warnings left are length: Tamil
  expands most, one Tamil tweet was 295/280 characters and Tamil and Telugu
  LinkedIn posts ran to 1,650-1,993 of 1,300. Open: give formats a smaller
  English budget for languages that expand, if this recurs.
- English output is unchanged: the default eval was all cache hits with no
  score moving, and English PDFs and deck XML are byte-identical. The one
  English change is deliberate: the advisory markdown's indicator types
  read "IP", "Domain" instead of "ip", "domain", as the PDF does.
