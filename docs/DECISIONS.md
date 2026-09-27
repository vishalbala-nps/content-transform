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
