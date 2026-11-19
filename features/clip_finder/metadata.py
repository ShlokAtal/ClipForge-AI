"""Offline title, description, and hashtag drafts for exported clips.

Suggestions are derived only from the clip's transcript. Nothing is sent to an
external service, so the feature works offline and never uploads content.
They are drafts: the user reviews and edits them before publishing.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

MAX_TITLE_LENGTH = 70
MAX_DESCRIPTION_LENGTH = 220
MAX_HASHTAGS = 5
MIN_KEYWORD_LENGTH = 4

STOPWORDS = frozenset(
    """
    about above after again against also always another because been before
    being below between both came come could did does doing down during each
    either else even ever every from further gonna good got gotta great have
    having here hers herself himself into its itself just know like little
    look make made make many maybe more most much must need never okay only
    onto other ourselves over really right said same say see shall should
    since some still such than that their theirs them themselves then there
    these they thing things think this those though through till today too
    took under until upon very want was well were what when where whether
    which while whom whose will with within without would yeah yes your
    yours yourself yourselves going gonna wanna gotta kinda sorta
    doesn didn isn aren wasn weren hasn haven hadn couldn shouldn wouldn
    won can cant dont thats theyre youre
    """.split()
)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _shorten(text: str, limit: int) -> str:
    """Trim to ``limit`` characters at a word boundary, adding an ellipsis."""
    text = _clean(text)
    if len(text) <= limit:
        return text

    cut = text[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,;:-")
    return (cut or text[: limit - 1]) + "…"


def suggest_title(transcript: str) -> str:
    """Use the clip's opening sentence as a concise draft title."""
    text = _clean(transcript)
    if not text:
        return "Highlight"

    first_sentence = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)[0]
    first_sentence = first_sentence.rstrip(".")
    return _shorten(first_sentence or "Highlight", MAX_TITLE_LENGTH)


def suggest_hashtags(
    transcript: str,
    *,
    max_tags: int = MAX_HASHTAGS,
    include_shorts: bool = False,
) -> list[str]:
    """Return hashtags built from the most frequent meaningful words."""
    # Letters only: apostrophes are dropped so "you're" never becomes "#you're".
    words = re.findall(r"[A-Za-z]+", transcript)

    normalized = []
    for word in words:
        cleaned = word.lower()
        if len(cleaned) >= MIN_KEYWORD_LENGTH and cleaned not in STOPWORDS:
            normalized.append(cleaned)

    counts = Counter(normalized)
    first_seen: dict[str, int] = {}
    for position, word in enumerate(normalized):
        first_seen.setdefault(word, position)

    ranked = sorted(counts, key=lambda word: (-counts[word], first_seen[word]))
    tags = [f"#{word}" for word in ranked[:max_tags]]

    if include_shorts:
        tags.append("#Shorts")

    return tags


def suggest_description(transcript: str, hashtags: list[str]) -> str:
    """Combine a trimmed transcript excerpt with the hashtags."""
    body = _shorten(transcript, MAX_DESCRIPTION_LENGTH)
    tag_line = " ".join(hashtags)
    return f"{body}\n\n{tag_line}".strip() if tag_line else body


def build_metadata(transcript: str, *, include_shorts: bool = False) -> dict:
    """Build the full set of draft fields for one clip."""
    hashtags = suggest_hashtags(transcript, include_shorts=include_shorts)
    return {
        "title": suggest_title(transcript),
        "description": suggest_description(transcript, hashtags),
        "hashtags": hashtags,
    }


def write_metadata_file(path: str | Path, payload: dict) -> Path:
    """Save clip details as a UTF-8 JSON sidecar file."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    record = dict(payload)
    record.setdefault(
        "created_at",
        datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )

    destination.write_text(
        json.dumps(record, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return destination
