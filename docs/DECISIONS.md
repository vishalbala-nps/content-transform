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
