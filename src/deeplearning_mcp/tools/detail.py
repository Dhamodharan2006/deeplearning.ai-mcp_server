"""get_course_detail tool implementation."""

from __future__ import annotations

import json
import logging

from deeplearning_mcp.cache import CourseCache
from deeplearning_mcp.fetcher import DeepLearningFetcher
from deeplearning_mcp.tools.schemas import (
    CourseDetail,
    GetCourseDetailInput,
    Lesson,
)

logger = logging.getLogger(__name__)


async def get_course_detail(
    inp: GetCourseDetailInput,
    cache: CourseCache,
    fetcher: DeepLearningFetcher,
) -> CourseDetail:
    """Return full course detail for a given course ID.

    Strategy:
    1. Look up course in cache
    2. If detail_json exists and not force_refresh → return cached
    3. Otherwise fetch live via Playwright, cache result, and return
    """
    row = await cache.get_course_by_id(inp.course_id)
    if row is None:
        raise ValueError(
            f"Course '{inp.course_id}' not found. "
            "Use search_courses first to get a valid course_id."
        )

    # Serve from cache if detail exists and no forced refresh
    if row.get("detail_json") and not inp.force_refresh:
        detail_data = json.loads(row["detail_json"])
        logger.info("Returning cached detail for %s", inp.course_id)
        return _parse_detail(detail_data)

    # Fetch live via Playwright
    logger.info("Fetching live detail for %s via Playwright", inp.course_id)
    detail_data = await fetcher.fetch_course_detail(row["url"])

    # Persist to cache
    await cache.upsert_course_detail(inp.course_id, detail_data)

    return _parse_detail(detail_data)


def _parse_detail(data: dict) -> CourseDetail:
    """Parse a raw detail dict into a validated CourseDetail model."""
    lessons = [
        Lesson(
            title=l.get("title", "Untitled"),
            duration_minutes=l.get("duration_minutes"),
        )
        for l in data.get("lessons", [])
    ]

    return CourseDetail(
        id=data.get("id", ""),
        title=data.get("title", "Unknown"),
        url=data.get("url", ""),
        topic=data.get("topic", ""),
        level=data.get("level"),
        instructors=data.get("instructors", []),
        lessons=lessons,
        skills_taught=data.get("skills_taught", []),
        prerequisites=data.get("prerequisites", "None listed"),
        total_hours=data.get("total_hours"),
        fetched_at=data.get("fetched_at", ""),
    )
