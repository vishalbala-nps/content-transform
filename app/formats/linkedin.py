"""S0 walking skeleton: one hardcoded prompt, straight from raw text.

This deliberately breaks the "generate from the brief" rule. S1 replaces the
raw-text input with a ContentBrief; S2 turns this into a registered adapter.
"""

from pydantic import BaseModel, Field

from app.core.llm import complete_json


class LinkedInPost(BaseModel):
    post: str = Field(description="The full LinkedIn post, ready to paste.")


PROMPT = """You are writing a LinkedIn post for a professional audience.

Turn the source text below into one LinkedIn post that:
- opens with a single-line hook that makes the reader want to expand the post
- states the key facts accurately; do not invent numbers, names or claims
- uses short paragraphs separated by blank lines
- ends with one takeaway or question for the reader
- stays under 1300 characters
- uses at most 3 hashtags, on the final line, and no emoji

Source text:
\"\"\"
{text}
\"\"\"
"""


async def generate(text: str) -> LinkedInPost:
    return await complete_json(LinkedInPost, PROMPT.format(text=text))
