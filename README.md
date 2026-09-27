# content-transform

One source document in, several communication artefacts out.
See `CLAUDE.md` and `docs/ROADMAP.md`.

## Run

One-time setup:

```sh
cp .env.example .env        # add your GEMINI_API_KEY
uv sync
cd web && npm install && cd ..
```

**Development** (UI hot reload), two terminals:

```sh
uv run --env-file .env uvicorn app.main:app --reload   # API on :8000
cd web && npm run dev                                   # UI on http://localhost:5173
```

Vite proxies `/api` to :8000.

**Single server** (demo): build the UI once, then FastAPI serves it.

```sh
cd web && npm run build && cd ..
uv run --env-file .env uvicorn app.main:app
```

Open http://127.0.0.1:8000. FastAPI only serves the UI if `web/dist` existed
when it started, so restart it after the first build.

Paste text, tick the formats you want and click **Generate**. The content
brief appears beside the outputs; hover a block chip (`b3`) to see the source
paragraph it cites. Formats are generated in parallel, at most
`LLM_CONCURRENCY` (default 3) model calls at a time.

Model responses are cached under `.cache/llm/` while developing, so the same
input costs no quota twice. **Set `LLM_CACHE=0` for demo runs.**

## Evals

Run after any prompt or schema change:

```sh
uv run --env-file .env python -m evals.run_evals            # all formats, all fixtures
uv run --env-file .env python -m evals.run_evals --formats x_thread -v
```

Each run writes the briefs, outputs and scores to `evals/runs/<timestamp>/`
and prints what moved since the last comparable run. See `evals/README.md`.
