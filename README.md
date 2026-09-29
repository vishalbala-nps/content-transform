# content-transform

One source document in, several communication artefacts out.
See `CLAUDE.md` and `docs/ROADMAP.md`.

## Run

One-time setup:

```sh
cp .env.example .env        # add your GEMINI_API_KEY
brew install pango          # PDF rendering (WeasyPrint); .env.example points uv's Python at it
uv sync
cd web && npm install && cd ..
```

Generated files (PDFs, and decks from S5b) are saved under
`storage/artifacts/<job id>/` and download from each output's card.

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

Choose **New job** in the sidebar, paste text (or upload a file, or give a
link), pick the formats you want and click **Generate**. The content brief
appears beside the outputs; hover a block chip (`b3`) to see the source
paragraph it cites. Formats are generated in parallel, at most
`LLM_CONCURRENCY` (default 3) model calls at a time.

Each run is a job in `storage/app.db` (`DATABASE_URL` to change it). The page
URL carries the job id, so you can close the tab mid-job and come back to it;
the sidebar lists earlier ones, and **New job from this** starts a new job
from one's input and settings. A job cut off by a server restart resumes
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

## Model provider

Every model call goes to Gemini unless `LLM_PROVIDER=ollama`. Set it in `.env`
to change the default, or put it before the command for one run (a variable
set in the shell wins over `.env`):

```sh
LLM_PROVIDER=ollama uv run --env-file .env uvicorn app.main:app --reload --timeout-graceful-shutdown 3
```

The server logs which provider and model it is using when it starts. Changing
provider needs a restart; `--reload` does not watch `.env`.

Ollama needs `ollama serve` running and the model pulled (`ollama pull
qwen3`, the default `OLLAMA_MODEL`). It works offline and has no rate limits,
but it is slow: on an M4 with 16 GB a job with three formats takes about four
minutes, most of it the brief. The dev cache keys on the model, so Gemini and
Ollama results never mix, and `LLM_CACHE_DELAY_S` works the same for both.

## Evals

Run after any prompt or schema change:

```sh
uv run --env-file .env python -m evals.run_evals            # all formats, all fixtures
uv run --env-file .env python -m evals.run_evals --formats x_thread -v
```

Each run writes the briefs, outputs and scores to `evals/runs/<timestamp>/`
and prints what moved since the last comparable run: same provider, model,
fixtures and formats. See `evals/README.md`.
