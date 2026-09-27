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
uv run --env-file .env uvicorn app.main:app --reload --timeout-graceful-shutdown 3   # API on :8000
cd web && npm run dev                                                                 # UI on http://localhost:5173
```

Vite proxies `/api` to :8000.

**Single server** (demo): build the UI once, then FastAPI serves it.

```sh
cd web && npm run build && cd ..
uv run --env-file .env uvicorn app.main:app --timeout-graceful-shutdown 3
```

Open http://127.0.0.1:8000. FastAPI only serves the UI if `web/dist` existed
when it started, so restart it after the first build.

Paste text, tick the formats you want and click **Generate**. The content
brief appears beside the outputs; hover a block chip (`b3`) to see the source
paragraph it cites. Formats are generated in parallel, at most
`LLM_CONCURRENCY` (default 3) model calls at a time.

Each run is a job in `storage/app.db` (`DATABASE_URL` to change it). The page
URL carries the job id, so you can close the tab mid-job and come back to it;
**Recent jobs** lists earlier ones. A job cut off by a server restart resumes
from its last finished step when the server starts again.

`--timeout-graceful-shutdown 3` matters: without it, stopping or reloading the
server waits for every open progress stream, which lasts until its job
finishes. With it, open streams are cut after 3 s (uvicorn logs a traceback for
each; harmless) and the browser reconnects to the new server.

Model responses are cached under `.cache/llm/` while developing, so the same
input costs no quota twice. **Set `LLM_CACHE=0` for demo runs.**

A fully cached job finishes in under a second, too fast to watch progress or
to close the tab or restart the server mid-job. `LLM_CACHE_DELAY_S=8` makes
each cache hit wait 8 s instead. The eval fixtures in `evals/fixtures/` are
already cached once the evals have run, so pasting one gives a slow job that
uses no quota.

## Evals

Run after any prompt or schema change:

```sh
uv run --env-file .env python -m evals.run_evals            # all formats, all fixtures
uv run --env-file .env python -m evals.run_evals --formats x_thread -v
```

Each run writes the briefs, outputs and scores to `evals/runs/<timestamp>/`
and prints what moved since the last comparable run. See `evals/README.md`.
