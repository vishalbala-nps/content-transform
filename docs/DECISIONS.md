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
