from fastapi import APIRouter, HTTPException
from google.genai import errors as genai_errors
from pydantic import BaseModel, Field

from app.core.llm import LLMError
from app.formats import linkedin
from app.ingest.base import SourceDocument
from app.ingest.text import ingest_text
from app.understand.brief import build_brief
from app.understand.schemas import ContentBrief

router = APIRouter(prefix="/api")


class GenerateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=100_000)


class GenerateResponse(BaseModel):
    source: SourceDocument
    brief: ContentBrief
    post: str


@router.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest) -> GenerateResponse:
    source = ingest_text(req.text)
    if not source.blocks:
        raise HTTPException(status_code=422, detail="Source text is empty.")
    try:
        brief = await build_brief(source)
        post = await linkedin.generate(brief)
    except LLMError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    except genai_errors.APIError as e:
        status = 429 if e.code == 429 else 502
        raise HTTPException(status_code=status, detail=f"Gemini: {e.message}") from e
    return GenerateResponse(source=source, brief=brief, post=post)
