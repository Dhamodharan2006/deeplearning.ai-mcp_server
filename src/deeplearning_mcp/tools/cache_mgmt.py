"""refresh_cache and get_cache_status tool implementations."""

from __future__ import annotations

import logging

from deeplearning_mcp.cache import CourseCache
from deeplearning_mcp.fetcher import DeepLearningFetcher
from deeplearning_mcp.tools.schemas import CacheStatus, RefreshCacheInput

logger = logging.getLogger(__name__)


async def refresh_cache(
    inp: RefreshCacheInput,
    cache: CourseCache,
    fetcher: DeepLearningFetcher,
) -> str:
    """Trigger a live crawl and update the cache.

    Scope values:
    - ``"all"`` — full refresh of every course listing
    - ``"topic:<slug>"`` — not yet implemented (falls back to all)
    - ``"course:<id>"`` — refresh a single course detail
    """
    if inp.scope.startswith("course:"):
        course_id = inp.scope.split(":", 1)[1]
        row = await cache.get_course_by_id(course_id)
        if row is None:
            return f"Course '{course_id}' not found in cache."
        detail = await fetcher.fetch_course_detail(row["url"])
        await cache.upsert_course_detail(course_id, detail)
        logger.info("Refreshed detail for course %s", course_id)
        return f"Refreshed detail for course '{course_id}'."

    # Default: full refresh
    logger.info("Starting full cache refresh via Playwright")
    courses = await fetcher.fetch_all_courses()
    count = await cache.upsert_courses(courses)
    logger.info("Full cache refresh complete: %d courses", count)
    return f"Cache refreshed: {count} courses updated."


async def get_cache_status(cache: CourseCache) -> CacheStatus:
    """Return the current state of the local course cache."""
    status = await cache.get_status()
    return CacheStatus(
        total_courses=status["total_courses"],
        last_refresh=status["last_refresh"],
        cache_age_hours=status["cache_age_hours"],
        topics_covered=status["topics_covered"],
    )
