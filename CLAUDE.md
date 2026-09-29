# Project instructions

AI content transformation platform. One source document in, several
communication artefacts out (LinkedIn post, X thread, advisory PDF,
infographic, executive summary, slide deck).

Solo project, built in vertical slices. See `docs/ROADMAP.md` for the
current slice and `docs/ARCHITECTURE.md` for the layer contracts.

## Core architectural rule

**One analysis, many renderings.** The source document is analysed exactly
once into a `ContentBrief`. Every output format is generated from that brief,
never from the raw source. This is what keeps the artefacts consistent with
each other and keeps token cost flat as formats are added.

Data flows strictly downward:

```
ingest/ -> SourceDocument -> understand/ -> ContentBrief -> formats/ -> payload JSON -> render/ -> files
```

Never import upward. `render/` must never import an LLM client — if a renderer
needs to call a model, the format's JSON schema is wrong, so fix the schema.

## Frozen contracts

These three are stable. Changing them means updating every module, so propose
the change and wait for confirmation rather than editing them in passing.

- `app/ingest/base.py` — `SourceDocument`
- `app/understand/schemas.py` — `ContentBrief`
- `app/formats/base.py` — `OutputAdapter`

Everything else is expected to churn.

## Adding an output format

One new file in `app/formats/`, registered in `app/formats/registry.py`.
It must not require edits to any other format, to the API layer, or to the
frontend. If it does, the registry is broken — fix that first.

Each adapter provides: `name`, `schema` (JSON schema the model fills),
`prompt(brief, config)`, `render(payload, config) -> list[Artifact]`.

## LLM calls

- All model calls go through `app/core/llm.py::complete_json(schema, prompt, model=...)`.
  No direct SDK calls anywhere else.
- Always schema-constrained. Never parse free text, never regex a model
  response. Validate with Pydantic on return; on failure retry once with the
  validation error appended to the prompt.
- Provider is config, not code. Gemini free tier is the default; an Ollama
  fallback must keep working.
- Dev cache is on by default: hash `(model, prompt, schema)` to disk under
  `.cache/llm/`. Never enabled in demo runs.

## Rate limits

The Gemini free tier is rate-limited by requests per minute, and this app
fans out to N parallel generation calls per job. Concurrency is bounded by a
semaphore in `app/core/llm.py` (default 3 in flight). Retry 429s with
exponential backoff. Do not raise the concurrency limit to make things faster.

## Stack

FastAPI + Pydantic v2, SQLAlchemy, SQLite in dev (Postgres-compatible models),
React + Vite + Tailwind + shadcn/ui, Docker Compose.

Jobs run on a Postgres/SQLite `jobs` table plus an in-process asyncio worker.
**Do not introduce Celery, Redis, or an external broker.** Progress is streamed
over SSE from the job table.

Renderers: `python-pptx` for decks, WeasyPrint for PDFs, Jinja to SVG then
`cairosvg` for infographics.

## Out of scope — do not build

No multi-tenancy (one organisation per deployment; users within it have their
own jobs and brand kits, see "Users" below), no microservices, no Kubernetes,
no vector database (the brief *is* the context; there is no retrieval
requirement), no token-by-token streaming UI, no video output pipeline. See
`docs/DECISIONS.md` for why.

## Users

Email and password accounts, created only from the command line
(`python -m tools.users`); no sign-up, no admin role. Every API route is
signed-in only through `current_user` in `app/api/auth.py`, attached to the
whole router. A route that loads a job or a brand kit must check it belongs
to the caller and answer 404 otherwise. Single sign-on is planned: it will
be another way to start a session, not a change to the routes.

## Working style

- Every change should end with something runnable. Prefer a thin vertical
  slice over a complete horizontal layer.
- Before adding a dependency, say what it replaces and why the stdlib or an
  existing dep will not do.
- Run `python -m evals.run_evals` after any prompt or schema change and report
  what moved. Do not tune prompts by eyeballing single outputs.
- Keep `docs/DECISIONS.md` current: append a dated entry whenever a scope or
  stack decision is made or reversed.
