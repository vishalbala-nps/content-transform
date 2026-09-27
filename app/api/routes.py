from fastapi import APIRouter, HTTPException
from google.genai import errors as genai_errors
from pydantic import BaseModel, Field

from app.core.llm import LLMError
from app.formats import linkedin

router = APIRouter(prefix="/api")


class GenerateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=100_000)


class GenerateResponse(BaseModel):
    post: str


@router.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest) -> GenerateResponse:
    try:
        result = await linkedin.generate(req.text)
    except LLMError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    except genai_errors.APIError as e:
        status = 429 if e.code == 429 else 502
        raise HTTPException(status_code=status, detail=f"Gemini: {e.message}") from e
    return GenerateResponse(post=result.post)
