"""list_topics tool implementation."""

from __future__ import annotations

import logging

from deeplearning_mcp.cache import CourseCache
from deeplearning_mcp.tools.schemas import ListTopicsInput, TopicSummary

logger = logging.getLogger(__name__)


async def list_topics(
    inp: ListTopicsInput,
    cache: CourseCache,
) -> list[TopicSummary]:
    """Return all topic categories with course counts. Cache-only."""
    rows = await cache.get_all_topics()
    results = [
        TopicSummary(
            slug=row["slug"],
            display_name=row["display_name"],
            course_count=row["course_count"],
        )
        for row in rows
    ]
    logger.info("list_topics returned %d topics", len(results))
    return results
