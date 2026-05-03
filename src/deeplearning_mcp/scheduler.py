"""APScheduler nightly cron that triggers a full cache refresh."""

from __future__ import annotations

import logging
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from deeplearning_mcp.cache import CourseCache
from deeplearning_mcp.fetcher import DeepLearningFetcher

logger = logging.getLogger(__name__)


class CacheScheduler:
    """Wraps APScheduler to run a nightly cache refresh job."""

    def __init__(self) -> None:
        self._scheduler: AsyncIOScheduler | None = None

    def start(self, fetcher: DeepLearningFetcher, cache: CourseCache) -> None:
        """Register and start the nightly cron job.

        Uses ``SCHEDULER_CRON_HOUR`` and ``SCHEDULER_CRON_MINUTE``
        environment variables (default: 02:00 UTC).
        """
        hour = int(os.getenv("SCHEDULER_CRON_HOUR", "2"))
        minute = int(os.getenv("SCHEDULER_CRON_MINUTE", "0"))

        self._scheduler = AsyncIOScheduler()
        self._scheduler.add_job(
            self._refresh_job,
            "cron",
            hour=hour,
            minute=minute,
            args=[fetcher, cache],
            id="nightly_refresh",
            replace_existing=True,
        )
        self._scheduler.start()
        logger.info("Scheduler started — nightly refresh at %02d:%02d UTC", hour, minute)

    def stop(self) -> None:
        """Shutdown the scheduler gracefully."""
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped")

    @staticmethod
    async def _refresh_job(fetcher: DeepLearningFetcher, cache: CourseCache) -> None:
        """Job callback: fetch all courses and upsert into cache."""
        try:
            courses = await fetcher.fetch_all_courses()
            count = await cache.upsert_courses(courses)
            logger.info("Nightly refresh complete: %d courses updated", count)
        except Exception:
            logger.exception("Nightly refresh failed")
