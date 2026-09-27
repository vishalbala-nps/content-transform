# content-transform

One source document in, several communication artefacts out.
See `CLAUDE.md` and `docs/ROADMAP.md`.

## Run

```sh
cp .env.example .env        # add your GEMINI_API_KEY
uv sync
uv run --env-file .env uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000, paste text, click **Generate LinkedIn post**.
The content brief appears beside the post; hover a block chip (`b3`) to see
the source paragraph it cites.
