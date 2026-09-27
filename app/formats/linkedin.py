"""LinkedIn post, generated from the ContentBrief only."""

from pydantic import BaseModel, Field

from app.formats.base import Artifact, GenerationConfig
from app.formats.brief_view import brief_for_prompt
from app.understand.schemas import ContentBrief

MAX_CHARS = 1300
# LinkedIn cuts the post off behind "...see more" after roughly this many characters.
HOOK_CHARS = 200


class LinkedInPost(BaseModel):
    hook: str = Field(description="A single-line opener that makes the reader want to expand the post.")
    paragraphs: list[str] = Field(
        description="The body, one short paragraph per item. The last one is the takeaway or question."
    )
    hashtags: list[str] = Field(max_length=3, description="At most 3 hashtags, without the # sign.")


PROMPT = """You are writing a LinkedIn post for a professional audience.

Everything you know about the subject is in the brief below. It is the only
source of truth: do not add numbers, names, dates or claims that are not in it.

Write one LinkedIn post that:
- opens with a single-line hook that makes the reader want to expand the post
- is built from the tldr, the claims and the stats; if the brief lists
  actions, the most important one belongs in the post
- attributes claims to the source when it is not an official statement of
  fact: for a news article, opinion or report, say who reported it ("According
  to <origin>..."); for a government memo or advisory, name the issuing body
- uses short paragraphs of one to three sentences
- ends with one takeaway or question for the reader
- stays under {max_chars} characters in total
- uses at most 3 hashtags and no emoji

Brief:
{brief}
"""


class LinkedInAdapter:
    name = "linkedin"
    label = "LinkedIn post"
    public = True
    schema = LinkedInPost

    def prompt(self, brief: ContentBrief, config: GenerationConfig) -> str:
        return PROMPT.format(max_chars=MAX_CHARS, brief=brief_for_prompt(brief, public=self.public))

    def render(self, payload: LinkedInPost, config: GenerationConfig, brief: ContentBrief) -> list[Artifact]:
        tags = " ".join("#" + t.lstrip("#").replace(" ", "") for t in payload.hashtags)
        text = "\n\n".join([payload.hook, *payload.paragraphs, *([tags] if tags else [])])
        return [Artifact(filename="linkedin.md", media_type="text/markdown", text=text)]

    def check(self, payload: LinkedInPost, artifacts: list[Artifact]) -> list[str]:
        warnings = []
        if (n := len(artifacts[0].text)) > MAX_CHARS:
            warnings.append(f"post is {n}/{MAX_CHARS} characters")
        if (n := len(payload.hook)) > HOOK_CHARS:
            warnings.append(f"hook is {n} characters; LinkedIn truncates after about {HOOK_CHARS}")
        return warnings


adapter = LinkedInAdapter()
