from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.llm import LLMError
from app.formats.base import GenerationConfig
from app.formats.registry import ADAPTERS
from app.formats.runner import FormatResult, run_formats
from app.ingest.base import SourceDocument
from app.ingest.text import ingest_text
from app.understand.brief import build_brief
from app.understand.schemas import ContentBrief

router = APIRouter(prefix="/api")


class FormatInfo(BaseModel):
    name: str
    label: str


class GenerateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=100_000)
    formats: list[str] = Field(min_length=1)


class GenerateResponse(BaseModel):
    source: SourceDocument
    brief: ContentBrief
    outputs: list[FormatResult]


@router.get("/formats", response_model=list[FormatInfo])
async def formats() -> list[FormatInfo]:
    return [FormatInfo(name=a.name, label=a.label) for a in ADAPTERS.values()]


@router.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest) -> GenerateResponse:
    unknown = [f for f in req.formats if f not in ADAPTERS]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown format: {', '.join(unknown)}")
    source = ingest_text(req.text)
    if not source.blocks:
        raise HTTPException(status_code=422, detail="Source text is empty.")
    try:
        brief = await build_brief(source)
    except LLMError as e:
        raise HTTPException(status_code=e.status, detail=str(e)) from e
    # Registry order, not request order, so the UI always lists outputs the same way.
    names = [n for n in ADAPTERS if n in req.formats]
    outputs = await run_formats(names, brief, GenerationConfig())
    return GenerateResponse(source=source, brief=brief, outputs=outputs)
