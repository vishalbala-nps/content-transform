# content-transform

One source document in, several communication artefacts out.
See `CLAUDE.md` and `docs/ROADMAP.md`.

## Run (S0)

```sh
cp .env.example .env        # add your GEMINI_API_KEY
uv sync
uv run --env-file .env uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000, paste text, click **Generate LinkedIn post**.
