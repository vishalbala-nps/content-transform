"""X (Twitter) thread, generated from the ContentBrief only.

The model writes the tweets; code adds the "3/7" counters and hashtags, so
the model's character budget per tweet is the limit minus that overhead.
Lengths are counted with len(), which is close to but not exactly X's
weighted count (X counts every URL as 23 and CJK characters and emoji as 2).
"""

from pydantic import BaseModel, Field

from app.formats.base import Artifact, GenerationConfig
from app.formats.brief_view import brief_for_prompt
from app.formats.config_view import config_for_prompt
from app.understand.schemas import ContentBrief

TWEET_LIMIT = 280
TWEET_BUDGET = 260  # what the model is told: room for " 10/10" and hashtags
# Tweets per thread at each detail level. The schema allows the widest range.
TWEETS = {"brief": (3, 4), "standard": (4, 7), "detailed": (7, 10)}
MIN_TWEETS, MAX_TWEETS = TWEETS["brief"][0], TWEETS["detailed"][1]


class XThread(BaseModel):
    tweets: list[str] = Field(
        min_length=MIN_TWEETS,
        max_length=MAX_TWEETS,
        description=f"The thread in order, one tweet per item, each at most {TWEET_BUDGET} characters. No numbering.",
    )
    hashtags: list[str] = Field(max_length=2, description="At most 2 hashtags for the last tweet, without the # sign.")


PROMPT = """You are writing a thread for X (formerly Twitter).

Everything you know about the subject is in the brief below. It is the only
source of truth: do not add numbers, names, dates or claims that are not in it.

Write a thread of {min_tweets} to {max_tweets} tweets that:
- opens with a first tweet that states the news and makes people read on
- gives one idea per tweet, each readable on its own
- carries the key numbers from the stats exactly as written in the brief
- attributes claims to the source when it is not an official statement of
  fact: for a news article, opinion or report, say who reported it; for a
  government memo or advisory, name the issuing body
- if the brief lists actions, puts the most important one in a tweet
- ends with a tweet that says what readers should take away or do
- keeps every tweet at most {budget} characters, with no numbering, no
  emoji and no links
- uses at most 2 hashtags, which will be added to the last tweet

{settings}

Brief:
{brief}
"""


class XThreadAdapter:
    name = "x_thread"
    label = "X thread"
    description = "A numbered thread, each post within 280 characters · Markdown"
    public = True
    schema = XThread

    def prompt(self, brief: ContentBrief, config: GenerationConfig) -> str:
        low, high = TWEETS[config.detail_level]
        return PROMPT.format(
            min_tweets=low,
            max_tweets=high,
            budget=TWEET_BUDGET,
            settings=config_for_prompt(config),
            brief=brief_for_prompt(brief, public=self.public),
        )

    def render(self, payload: XThread, config: GenerationConfig, brief: ContentBrief) -> list[Artifact]:
        n = len(payload.tweets)
        tags = " ".join("#" + t.lstrip("#").replace(" ", "") for t in payload.hashtags)
        parts = [f"{tweet.strip()} {i}/{n}" for i, tweet in enumerate(payload.tweets, start=1)]
        if tags:
            parts[-1] = f"{parts[-1]}\n\n{tags}"
        return [
            Artifact(
                filename="x_thread.md",
                media_type="text/markdown",
                text="\n\n---\n\n".join(parts),
                parts=parts,
                part_limit=TWEET_LIMIT,
            )
        ]

    def check(self, payload: XThread, artifacts: list[Artifact], config: GenerationConfig) -> list[str]:
        warnings = []
        low, high = TWEETS[config.detail_level]
        if not low <= (n := len(payload.tweets)) <= high:
            warnings.append(f"thread has {n} tweets; {config.detail_level} is {low}-{high}")
        warnings += [
            f"tweet {i} is {len(part)}/{TWEET_LIMIT} characters"
            for i, part in enumerate(artifacts[0].parts, start=1)
            if len(part) > TWEET_LIMIT
        ]
        return warnings


adapter = XThreadAdapter()
