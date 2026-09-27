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
api/ web/                          jobs, SSE progress, review UI
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
class OutputAdapter(Protocol):
    name: str
    label: str
    schema: dict                                      # JSON schema
    def prompt(self, brief: ContentBrief, config: GenerationConfig) -> str: ...
    def render(self, payload: dict, config: GenerationConfig) -> list[Artifact]: ...
```

Adapters self-register. Adding a format touches exactly one new file plus the
registry import.

## GenerationConfig

One object, threaded to every adapter. Never spread as loose prompt strings.

```python
class GenerationConfig(BaseModel):
    audience: Literal["executive", "technical", "general_public", "media"]
    tone: Literal["formal", "neutral", "conversational", "urgent"]
    language: str = "en"
    detail_level: Literal["brief", "standard", "detailed"]
    objective: Literal["inform", "warn", "persuade", "instruct", "announce"]
    style: str | None
    brand_kit: BrandKit | None    # logo, palette, fonts, banned phrases
```

Translation runs **after** schema filling so character limits and layout
constraints still hold.

## Directory layout

```
app/
  core/          config.py, llm.py, jobs.py, storage.py
  ingest/        base.py, pdf.py, docx.py, html.py, image.py, registry.py
  understand/    brief.py, schemas.py, prompts/
  formats/       base.py, registry.py,
                 linkedin.py, twitter.py, advisory.py,
                 infographic.py, exec_summary.py, deck.py
  render/        pdf.py, pptx.py, svg.py, templates/
  verify/        grounding.py, pii.py
  api/           routes.py, sse.py
  db/            models.py, migrations/
web/             React + Vite
evals/           fixtures/, run_evals.py
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
| LLM      | Gemini free tier, Ollama fallback       | one client, provider in config |
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

Each generated factual sentence is matched back to a `Claim`, and therefore to
`Block` ids in the source. Unsupported sentences are flagged amber in the
review UI rather than silently shipped. A PII scan and a policy check run over
public-facing artefacts (for example: IOCs belong in the advisory, not in the
LinkedIn post).
