"""search_courses tool implementation."""

from __future__ import annotations

import logging

from deeplearning_mcp.cache import CourseCache
from deeplearning_mcp.tools.schemas import CourseShort, SearchCoursesInput

logger = logging.getLogger(__name__)


async def search_courses(
    inp: SearchCoursesInput,
    cache: CourseCache,
) -> list[CourseShort]:
    """Search cached courses with optional filters.

    This is a cache-only operation — it never triggers Playwright.
    """
    rows = await cache.search_courses(
        query=inp.query,
        topic=inp.topic,
        level=inp.level,
        instructor=inp.instructor,
        limit=inp.limit,
    )

    results: list[CourseShort] = []
    for row in rows:
        age = cache.cache_age_from_timestamp(row["fetched_at"])
        results.append(
            CourseShort(
                id=row["id"],
                title=row["title"],
                topic=row["topic"] or "",
                level=row["level"],
                instructor=row["instructor"] or "",
                url=row["url"],
                short_description=row["short_desc"] or "",
                cache_age_hours=age,
            )
        )

    logger.info("search_courses returned %d results", len(results))
    return results
