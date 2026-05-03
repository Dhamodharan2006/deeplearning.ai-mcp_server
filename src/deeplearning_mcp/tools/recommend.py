"""recommend_courses tool — pure Python scoring, no Playwright calls."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from deeplearning_mcp.cache import CourseCache
from deeplearning_mcp.tools.schemas import (
    CourseShort,
    Recommendation,
    RecommendCoursesInput,
)

logger = logging.getLogger(__name__)

# Level ordering used for scoring
_LEVEL_ORDER = {"beginner": 0, "intermediate": 1, "advanced": 2}


async def recommend_courses(
    inp: RecommendCoursesInput,
    cache: CourseCache,
) -> list[Recommendation]:
    """Recommend courses based on a learning goal and optional background.

    Scoring algorithm (100 pts max per course):
    - Keyword overlap (goal+background ↔ title+desc):  0-40 pts
    - Level match:                                      0-20 pts
    - Topic relevance to goal keywords:                 0-20 pts
    - Course freshness (newer = higher):                0-20 pts
    """
    rows = await cache.search_courses(limit=200)  # load all
    if not rows:
        return []

    goal_tokens = _tokenise(inp.goal)
    bg_tokens = _tokenise(inp.background or "")
    all_tokens = goal_tokens | bg_tokens

    # Infer target level from background
    target_level = _infer_level(inp.background)

    scored: list[tuple[float, dict, dict[str, float]]] = []
    for row in rows:
        scores = _score_course(row, all_tokens, goal_tokens, target_level)
        total = sum(scores.values())
        scored.append((total, row, scores))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[: inp.limit]

    results: list[Recommendation] = []
    for rank, (total, row, scores) in enumerate(top, start=1):
        age = cache.cache_age_from_timestamp(row["fetched_at"])
        course = CourseShort(
            id=row["id"],
            title=row["title"],
            topic=row["topic"] or "",
            level=row["level"],
            instructor=row["instructor"] or "",
            url=row["url"],
            short_description=row["short_desc"] or "",
            cache_age_hours=age,
        )
        reason = _generate_reason(row, scores)
        results.append(Recommendation(course=course, rank=rank, reason=reason))

    logger.info("recommend_courses returned %d results", len(results))
    return results


# ------------------------------------------------------------------
# Scoring helpers
# ------------------------------------------------------------------


def _tokenise(text: str) -> set[str]:
    """Lowercase and split text into a set of word tokens."""
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _infer_level(background: str | None) -> str:
    """Guess the ideal course level from background description."""
    if not background:
        return "beginner"
    bg_lower = background.lower()
    if any(kw in bg_lower for kw in ("expert", "senior", "advanced", "years")):
        return "advanced"
    if any(kw in bg_lower for kw in ("some", "familiar", "intermediate", "basics")):
        return "intermediate"
    return "beginner"


def _score_course(
    row: dict,
    all_tokens: set[str],
    goal_tokens: set[str],
    target_level: str,
) -> dict[str, float]:
    """Score a single course, returning a breakdown dict."""
    scores: dict[str, float] = {}

    # 1. Keyword overlap (0-40)
    course_tokens = _tokenise(f"{row['title']} {row.get('short_desc', '')}")
    overlap = len(all_tokens & course_tokens)
    scores["keyword"] = min(40.0, overlap * 10.0)

    # 2. Level match (0-20)
    course_level = (row.get("level") or "").lower()
    if course_level == target_level:
        scores["level"] = 20.0
    elif course_level in _LEVEL_ORDER and target_level in _LEVEL_ORDER:
        diff = abs(_LEVEL_ORDER[course_level] - _LEVEL_ORDER[target_level])
        scores["level"] = max(0.0, 20.0 - diff * 10.0)
    else:
        scores["level"] = 5.0  # unknown level gets a small score

    # 3. Topic relevance (0-20)
    topic_tokens = _tokenise(row.get("topic", ""))
    topic_overlap = len(goal_tokens & topic_tokens)
    scores["topic"] = min(20.0, topic_overlap * 10.0)

    # 4. Freshness (0-20)
    try:
        fetched = datetime.fromisoformat(row["fetched_at"])
        age_days = (datetime.now(timezone.utc) - fetched).total_seconds() / 86400
        scores["freshness"] = max(0.0, 20.0 - age_days * 0.5)
    except (ValueError, KeyError):
        scores["freshness"] = 0.0

    return scores


def _generate_reason(row: dict, scores: dict[str, float]) -> str:
    """Produce a one-sentence reason based on the highest scoring factor."""
    best_factor = max(scores, key=scores.get)  # type: ignore[arg-type]
    title = row["title"]

    reasons = {
        "keyword": f"'{title}' closely matches your learning goals.",
        "level": f"'{title}' is at the right difficulty level for your background.",
        "topic": f"'{title}' covers a topic directly related to your goal.",
        "freshness": f"'{title}' has recently updated content.",
    }
    return reasons.get(best_factor, f"'{title}' is a strong match for your goals.")
