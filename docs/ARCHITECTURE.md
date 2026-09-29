# Architecture

## Problem

Convert one source of information (text, document, article, report, prompt,
image) into whichever communication artefacts the operator selects, with
consistent facts across all of them and an audit trail back to the source.

## Layers

```
ingest/      -> SourceDocument     pdf, docx, html, text, image
understand/  -> ContentBrief       one schema-constrained LLM call
formats/     -> payload JSON       one LLM call per selected format
render/      -> files              pure Python, no model calls
verify/      -> grounding report   claims mapped back to source blocks
api/ web/                          jobs, SSE progress, review UI, sign-in
```

The `ContentBrief` is the seam that matters. Source analysis happens once;
adding a seventh output format adds one generation call, not another full
document read.

## Contract 1 — SourceDocument

Produced by every ingester. Downstream code never knows the input type.

```python
class Block(BaseModel):
    id: str            # stable, citable
    type: Literal["heading", "para", "list", "table", "caption"]
    text: str
    page: int | None

class Asset(BaseModel):
    id: str
    kind: Literal["image", "table", "chart"]
    path: str
    caption: str | None

class SourceDocument(BaseModel):
    doc_id: str
    markdown: str          # normalised body, headings preserved
    blocks: list[Block]    # citation targets for grounding
    assets: list[Asset]
    meta: dict             # title, source_url, mime, ingested_at
```

## Contract 2 — ContentBrief

The single intermediate representation. Every claim carries the block ids that
support it, which is what makes the grounding check possible later.

```python
class Claim(BaseModel):
    id: str
    text: str
    support: list[str]     # Block.id references

class ContentBrief(BaseModel):
    brief_id: str
    doc_id: str
    title: str
    source: SourceProfile  # kind, origin, published, tone
    tldr: str
    claims: list[Claim]
    entities: list[Entity]
    timeline: list[TimelineItem]   # when, event, support
    stats: list[Stat]              # value, label, support
    actions: list[Action]          # text, support: mitigations, directives, recommendations
    security: SecurityDetails | None   # domain extension, null unless security
```

The brief is tone-neutral: claims are written plainly whatever the source's
tone, so any output tone can be produced from it. `SourceProfile`
describes the source (news article, government memo, advisory...) and who
issued it, so outputs can attribute claims instead of stating a reporter's
claim with the authority of an official directive. Choosing what to emphasise
for a given audience is the format prompt's job, driven by `GenerationConfig`.

Everything above `security` is general and applies to any source. Domains
are optional extension blocks: `SecurityDetails` carries CVE ids, affected
products and versions, severity, CVSS score and IOCs, and is null for a
non-security source. A new domain is one more `<domain>: <Domain>Details | None`
field. Full definitions: `app/understand/schemas.py`.

## Contract 3 — OutputAdapter

```python
class Artifact(BaseModel):
    filename: str                  # "linkedin.md", "exec_summary.pdf"
    media_type: str                # "text/markdown", "application/pdf"
    text: str | None = None        # text artifacts: what Copy uses
    parts: list[str] = []          # separately postable pieces, e.g. each tweet
    part_limit: int | None = None  # character limit per part
    data: bytes | None = None      # binary artifacts, from render(); never serialised
    path: str | None = None        # storage key, set when the job saves `data`

class OutputAdapter(Protocol):
    name: str                      # registry key and API id
    label: str                     # UI label
    description: str               # UI: what it makes, "… · PDF + Markdown"
    public: bool                   # public-facing: the IOC policy applies
    schema: type[BaseModel]        # what the model fills
    def prompt(self, brief: ContentBrief, config: GenerationConfig) -> str: ...
    def render(self, payload: BaseModel, config: GenerationConfig,
               brief: ContentBrief) -> list[Artifact]: ...
    def check(self, payload: BaseModel, artifacts: list[Artifact],
              config: GenerationConfig) -> list[str]: ...
```

- `schema` is a Pydantic model class. `complete_json` derives the JSON schema
  from it and validates the response, so `render` receives a typed payload,
  never a raw dict.
- `public` marks formats read outside the organisation (LinkedIn, X). The IOC
  policy and, later, the PII scan apply to those without naming formats.
- `check` returns soft warnings (over a character limit, too many hashtags,
  fewer slides than the detail level asks for). It never fails a job. Evals
  score with it, so a new format brings its own limits and the eval harness
  needs no edit.
- `render()` also receives the brief, so exact values (CVE ids, versions,
  CVSS, IOCs, dates, figures) are copied from it into the output rather than
  retyped by the model; the model writes prose. A `public` format receives
  the brief with IOCs removed, the same rule its prompt gets
  (`brief_view.py`).
- `render()` does no I/O. A binary artefact (PDF, PPTX, PNG) comes back as
  bytes in `data`; the job saves them through `app/core/storage.py` before
  writing the result to its row, and records the key in `path`. Text
  artefacts stay on the row. Every artefact, text or binary, downloads from
  `GET /api/jobs/{id}/files/{format}/{filename}`, which looks it up on the
  row. `render()` runs in a worker thread, since PDF and PPTX rendering take
  long enough to stall the event loop.
- A format that renders a file also returns a text artefact where one makes
  sense (the exec summary's markdown beside its PDF), so Copy still works.

Adding a format touches exactly one new file plus one line in
`app/formats/registry.py`. Full definitions: `app/formats/base.py`.

## GenerationConfig

One object, threaded to every adapter. Never spread as loose prompt strings.

```python
class GenerationConfig(BaseModel):
    audience: Literal["executive", "technical", "general_public", "media"]
    tone: Literal["formal", "neutral", "conversational", "urgent"]
    language: Literal["en", "hi", "ta", "ml", "kn", "te"] = "en"
    detail_level: Literal["brief", "standard", "detailed"]
    objective: Literal["inform", "warn", "persuade", "instruct", "announce"]
    style: str | None             # free text, at most 300 characters
    brand_kit: BrandKit | None    # copy of a saved kit: name, colours, font, logo, banned phrases
```

Every field has a default, and the job row stores the config, so a
regenerated passage uses the same settings as the job. One config applies
to every format in a job.

- A format's prompt says what the format is and its fixed rules (use only
  the brief, attribute claims, no hype). `config_for_prompt()`
  (`formats/config_view.py`) adds one section, the same in every format, for
  audience, objective, tone and style. It changes emphasis and voice, never
  the rules.
- `detail_level` is turned into targets by each format (tweets, slides,
  words), stated in its prompt and warned on by its `check()`. The schema
  allows the widest range, since `schema` is one class per format.
- `language`: every format is written, grounded and reviewed in English;
  for another language its payload is then translated
  (`formats/translate.py`, one call per format) and the files are rendered
  and checked from the translation (`FormatResult.translation`). The
  brief's wording that renderers copy (figure labels, timeline, dates,
  affected versions) is translated once per job (`jobs.brief_translation`);
  values are never translated. Numbers stay in Western digits. Fixed labels
  in files come from `render/labels.json`, translated once and checked in;
  PDFs embed bundled Noto fonts for the script (`render/fonts/`).
- `brand_kit` is copied from a saved kit (`core/brand_kits.py`, table
  `brand_kits`) when the job is created, so editing or deleting the kit
  never changes an old job. Renderers receive a `Theme` (`render/theme.py`)
  built from it by `formats/brand.py`, never the kit; no kit is the house
  style. The runner loads the logo's bytes before `render()`. A kit's
  banned phrases go into the shared prompt section and are warned on after
  rendering, for every format.

Translation runs **after** schema filling so character limits and layout
constraints still hold, and after grounding, so the fact check always reads
English.

## Users

One organisation per deployment; each user has their own jobs, history and
brand kits. Accounts are email and password, made only with
`python -m tools.users`.

- `app/core/users.py`: scrypt password hashes (standard library), sessions
  (a random token in an HttpOnly, SameSite=Lax cookie; only its SHA-256 is
  stored; 8 hours), a lockout after 5 failed sign-ins for an email.
- `app/api/auth.py`: `current_user`, attached to the whole API router, and
  the sign-in routes (`/api/auth/login`, `logout`, `me`, `password`). A
  same-origin check refuses data-changing requests from other sites.
- Jobs and brand kits carry `user_id`. The API checks ownership when it
  loads one and answers 404 for another user's. The worker, revisions and
  storage address jobs by id and never check: they are only reached through
  a route that has.
- Single sign-on later is another way to start the same session (an OIDC
  callback), or an identity header `current_user` reads from a trusted
  proxy. Routes do not change either way.

## Directory layout

```
app/
  core/          config.py, llm.py, usage.py, jobs.py, storage.py, revise.py,
                 brand_kits.py, users.py
  ingest/        base.py, common.py, registry.py, url.py, text.py, docx.py,
                 pdf.py, html.py, image.py
  understand/    brief.py, schemas.py, prompts/
  formats/       base.py, registry.py, runner.py, brief_view.py, config_view.py,
                 brand.py, translate.py,
                 linkedin.py, x_thread.py, advisory.py,
                 infographic.py, exec_summary.py, deck.py
  render/        theme.py, labels.py, labels.json, pdf.py, pptx.py, svg.py,
                 templates/, fonts/
  verify/        grounding.py, pii.py
  api/           routes.py, auth.py
  db/            models.py, migrations/
web/             React + Vite
evals/           fixtures/, run_evals.py
tools/           translate_labels.py (fills render/labels.json),
                 users.py (makes and manages accounts)
storage/         artifacts/
```

## Stack decisions

| Concern  | Choice                                  | Note |
|----------|-----------------------------------------|------|
| API      | FastAPI + Pydantic v2                   | schemas double as the contracts |
| Jobs     | DB table + in-process asyncio worker    | no Celery, no Redis |
| DB       | SQLite now, Postgres-shaped models      | swap the URL later |
| Storage  | local dir behind a 4-method interface   | S3 is a small swap |
| Progress | SSE off the job table                   | |
| LLM      | Gemini (paid key), Ollama fallback      | one client, provider in config |
| Usage    | `metered()` blocks over `complete_json` | tokens and estimated cost per step |
| Frontend | React + Vite + Tailwind + shadcn/ui     | |

## Output formats (current scope)

| Format            | Renderer            | Artefact       |
|-------------------|---------------------|----------------|
| LinkedIn Post     | text                | markdown       |
| X / Twitter thread| text + char counts  | markdown/json  |
| Executive Summary | text + WeasyPrint   | md + pdf       |
| Advisory          | WeasyPrint          | pdf            |
| Infographic       | Jinja -> SVG -> PNG | svg + png      |
| Presentation      | python-pptx         | pptx           |

Video is deliberately excluded. The adapter interface supports it; see
`docs/DECISIONS.md`.

## Verification

Each prose field of a format's payload (a passage) is matched back to the
brief items that support it, and therefore to `Block` ids in the source
(`app/verify/grounding.py`, run by the format runner after `check`).
Unsupported passages are flagged amber in the review UI rather than silently
shipped. A reviewer can edit a passage (trusted, not re-checked), regenerate
it (re-checked), accept its flag, or delete the list entry holding it (a
paragraph, a tweet, a whole slide; fields outside any list are required);
the format's files are rebuilt from the revised payload
(`app/core/revise.py`). A PII scan and a policy check run over
public-facing artefacts (for example: IOCs belong in the advisory, not in the
LinkedIn post).
