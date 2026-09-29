# Spectra

One source document in, a verified set of communication artefacts out:
posts, an executive summary, a slide deck and an advisory, in English and
five Indian languages. See [About Spectra](#3-about-spectra-and-how-to-use-it).

- [1. One-time setup](#1-one-time-setup)
- [2. Operating Spectra](#2-operating-spectra)
- [3. About Spectra and how to use it](#3-about-spectra-and-how-to-use-it)

---

## 1. One-time setup

Run everything from the project folder. The steps are the same on macOS and
Linux except where marked.

### 1.1 Install the prerequisites

Spectra needs **uv** (Python and its packages), **Node.js 22.12 or newer**
(or 20.19+) with npm (the web interface), and **Pango** (PDF rendering). Python itself is
installed by uv.

**macOS** (with [Homebrew](https://brew.sh)):

```sh
brew install uv node pango
```

**Linux** (Debian or Ubuntu):

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh                        # uv
sudo apt install libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0   # Pango, for PDFs
```

Install Node.js 22.12 or newer from [nodejs.org](https://nodejs.org) or with
[nvm](https://github.com/nvm-sh/nvm); distribution packages are often older.
On Fedora, Pango is `sudo dnf install pango`.

**Optional, for offline use:** install [Ollama](https://ollama.com), then
`ollama pull qwen3`. See [Switching the AI model](#23-switching-the-ai-model).

### 1.2 Install Spectra's packages

```sh
uv sync                              # Python and the backend packages
cd web && npm install && cd ..       # the web interface's packages
```

### 1.3 Configure `.env`

```sh
cp .env.example .env
```

Then edit `.env`:

| Setting | What to put |
|---|---|
| `GEMINI_API_KEY` | Your Google Gemini API key. Required unless you use Ollama. |
| `DYLD_FALLBACK_LIBRARY_PATH` | **macOS:** leave as `/opt/homebrew/lib` on Apple Silicon; use `/usr/local/lib` on an Intel Mac. **Linux:** delete the line. |
| `LLM_CACHE` | Leave unset while developing. **Set `LLM_CACHE=0` for real use and demos**: the development cache replays earlier answers. |
| `LLM_PROVIDER` | `gemini` (default) or `ollama` for local models. |
| `SESSION_HOURS` | How long a sign-in lasts. Default `8`. |
| `SESSION_COOKIE_SECURE` | `1` when Spectra is served over HTTPS. Default `0`. |
| `ALLOWED_ORIGINS` | The site's address (e.g. `https://spectra.example.gov.in`) when a proxy in front rewrites the Host header. |
| `ALLOW_PRIVATE_URLS` | `1` to let link sources reach intranet addresses. Default `0`: private and internal addresses are refused. |
| `DATABASE_URL` | Where the database lives. Default `storage/app.db` (SQLite). |

The other settings in `.env.example` (model names, Ollama options,
concurrency) rarely need changing; each is explained there.

### 1.4 Build the web interface

```sh
cd web && npm run build && cd ..
```

Build again after pulling changes to `web/`. (Development mode, below, does
not need a build.)

### 1.5 Create the first user

Accounts are created from the command line only; there is no sign-up page.

```sh
uv run --env-file .env python -m tools.users create you@example.org
```

It asks for the password twice. The database is created on first use.

If this copy of Spectra has jobs and brand kits from before accounts existed,
give them to that user, or no one will see them:

```sh
uv run --env-file .env python -m tools.users adopt you@example.org
```

Setup is done: [start Spectra](#21-start-and-stop) and sign in.

---

## 2. Operating Spectra

### 2.1 Start and stop

The commands are the same on macOS and Linux.

**Normal use** (one server, serving the built interface):

```sh
uv run --env-file .env uvicorn app.main:app --timeout-graceful-shutdown 3
```

Open <http://127.0.0.1:8000> and sign in. The server logs which AI provider
and model it is using as it starts. To reach Spectra from other machines, add
`--host 0.0.0.0`, and put it behind an HTTPS reverse proxy (then set
`SESSION_COOKIE_SECURE=1`).

**Development** (the interface reloads as you edit), in two terminals:

```sh
uv run --env-file .env uvicorn app.main:app --reload --timeout-graceful-shutdown 3   # API on :8000
cd web && npm run dev                                                                 # open http://localhost:5173
```

**Stop:** press `Ctrl+C` in each terminal. If the server was started in the
background, find and stop it:

```sh
lsof -iTCP:8000 -sTCP:LISTEN     # shows the process id (PID)
kill <PID>
```

Stopping is safe at any time. Jobs in progress are kept and resume from
their last finished step when the server starts again.

`--timeout-graceful-shutdown 3` matters: without it, stopping or reloading
waits for every open progress stream, which lasts until its job finishes.
With it, streams are cut after 3 seconds (uvicorn logs a harmless traceback
for each) and browsers reconnect by themselves.

**Where the data is:** `storage/app.db` (accounts, jobs, brand kits) and
`storage/artifacts/` (generated PDFs, decks and logos). Back up the whole
`storage/` folder.

### 2.2 Manage users

Run these from the project folder; the server can keep running.

| Task | Command |
|---|---|
| Create a user | `uv run --env-file .env python -m tools.users create someone@example.org` |
| Reset a forgotten password | `uv run --env-file .env python -m tools.users passwd someone@example.org` |
| Remove a user's access | `uv run --env-file .env python -m tools.users disable someone@example.org` |
| Restore a user's access | `uv run --env-file .env python -m tools.users enable someone@example.org` |
| List all users | `uv run --env-file .env python -m tools.users list` |
| Give ownerless jobs and kits to a user | `uv run --env-file .env python -m tools.users adopt someone@example.org` |

- **There is no delete.** `disable` is how a user is removed: they are
  signed out at once and cannot sign in, and their jobs and brand kits are
  kept (and return with `enable`).
- **Passwords** are asked for twice and not shown on screen. For a script,
  `--password '…'` gives one on the command line instead (it is then kept in
  the shell history). Passwords shorter than 12 characters are accepted with
  a warning.
- **A forgotten password** cannot be looked up by anyone; only a one-way hash
  is stored. `passwd` sets a new one and signs the user out everywhere. Pass
  it on to them; they can change it in the app.
- **Users change their own password** in the app: the account menu at the
  top right, **Change password…**. It signs them out everywhere else.
- Emails are not case-sensitive. There are no roles: every user can do the
  same things with their own data.
- Five wrong passwords for one email within 15 minutes lock that email's
  sign-in until the 15 minutes are up. Restarting the server clears it.

### 2.3 Switching the AI model

Every model call goes to Gemini unless `LLM_PROVIDER=ollama`. Set it in
`.env`, or before the command for one run (a variable set in the shell wins
over `.env`):

```sh
LLM_PROVIDER=ollama uv run --env-file .env uvicorn app.main:app --timeout-graceful-shutdown 3
```

Changing provider needs a restart; `--reload` does not watch `.env`.

Ollama needs `ollama serve` running and the model pulled (`ollama pull
qwen3`, the default `OLLAMA_MODEL`). It works offline and has no rate limits,
but it is slow: on an M4 with 16 GB a job with three formats takes about four
minutes, most of it the brief.

### 2.4 Checks and tests

**Is the server up?**

```sh
curl -s http://127.0.0.1:8000/api/auth/me
```

`{"detail":"Sign in to continue."}` means it is running (the answer is the
same for everyone who is not signed in).

**Quality evaluations.** Run after any change to a prompt or a schema:

```sh
uv run --env-file .env python -m evals.run_evals                         # all formats, all fixtures
uv run --env-file .env python -m evals.run_evals --formats x_thread -v   # one format, more output
```

Each run writes the briefs, outputs and scores to `evals/runs/<timestamp>/`
and prints what moved since the last comparable run (same provider, model,
fixtures and formats). See `evals/README.md`.

**Web interface checks:**

```sh
cd web && npm run typecheck && npm run lint && cd ..
```

**Testing without using quota.** While developing, model answers are cached
under `.cache/llm/`, so the same input costs nothing twice. A fully cached
job finishes in under a second, too fast to watch its progress;
`LLM_CACHE_DELAY_S=8` in `.env` makes each cached answer wait 8 seconds. The
eval fixtures in `evals/fixtures/` are cached once the evals have run, so
pasting one gives a slow job that uses no quota.

---

## 3. About Spectra and how to use it

### What Spectra does

Spectra turns one source (an article, report, advisory or notice) into the
communication artefacts an organisation needs, and checks them against the
source before anything is published.

- **One analysis, many outputs.** The source is read once into a structured
  brief of claims, figures, dates and actions, each citing where in the
  source it came from. Every output is written from that brief, so the facts
  agree across all of them.
- **Outputs:** LinkedIn post, X thread, executive summary (PDF), slide deck
  (PowerPoint with speaker notes) and advisory (PDF). Infographic and video
  are planned.
- **Checked, not just generated.** Every passage is traced back to the
  source; anything unsupported is flagged for a person to fix before it goes
  out. Exact values (CVE ids, versions, figures, dates) are copied by code,
  never retyped by the AI. Technical indicators are kept out of public posts.
- **Tailored:** audience, purpose, tone, level of detail, style notes, the
  organisation's brand kit, and output in English, Hindi, Tamil, Malayalam,
  Kannada or Telugu.

### How a user works with it

1. **Sign in** with the email and password from your administrator.
2. **New job** (in the sidebar): give the source by pasting text, uploading a
   file (PDF, Word, HTML, text) or entering a link. Choose the formats, and
   the settings: who the reader is, the language, and the brand kit.
   **Generate.**
3. **Watch it work.** Progress shows as the brief and then each format are
   written. You can close the tab; the job keeps running and is in the
   sidebar when you come back.
4. **Review.** The source and brief are on the left, the outputs on the
   right, one format at a time. Passages that need review are highlighted in
   amber, and each format shows how many it has. Click a passage to see what
   in the source it rests on, then **Edit**, **Regenerate**, **Accept** or
   **Delete** it. The files update straight away.
5. **Take it away.** **Copy** the text, or download the PDF, PowerPoint or
   Markdown from each format's header.
6. **Reuse.** **New job from this** starts a new job with the same source and
   settings, for example to try another audience or language.
7. **Brand kits** (in the sidebar): save your organisation's name, colours,
   font, logo and banned phrases, then choose the kit in a new job. Jobs
   already made keep the kit as it was.
8. **Your account:** the menu at the top right changes your password or signs
   you out.
