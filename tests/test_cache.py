"""Tests for the SQLite cache layer."""

from __future__ import annotations

import pytest

from deeplearning_mcp.cache import CourseCache
from conftest import SAMPLE_COURSES, SAMPLE_DETAIL


# ------------------------------------------------------------------
# init & lifecycle
# ------------------------------------------------------------------


class TestCacheInit:
    async def test_init_db_creates_tables(self, cache: CourseCache) -> None:
        """Tables exist after init_db()."""
        cursor = await cache.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row["name"] for row in await cursor.fetchall()}
        assert "courses" in tables
        assert "topics" in tables
        assert "meta" in tables

    async def test_db_property_raises_before_init(self) -> None:
        """Accessing db before init_db raises RuntimeError."""
        c = CourseCache(db_path=":memory:")
        with pytest.raises(RuntimeError, match="init_db"):
            _ = c.db


# ------------------------------------------------------------------
# upsert_courses
# ------------------------------------------------------------------


class TestUpsertCourses:
    async def test_upsert_inserts_all(self, cache: CourseCache) -> None:
        count = await cache.upsert_courses(SAMPLE_COURSES)
        assert count == len(SAMPLE_COURSES)

    async def test_upsert_updates_existing(self, seeded_cache: CourseCache) -> None:
        updated = [
            {**SAMPLE_COURSES[0], "title": "Updated Title"},
        ]
        await seeded_cache.upsert_courses(updated)
        row = await seeded_cache.get_course_by_id(SAMPLE_COURSES[0]["id"])
        assert row is not None
        assert row["title"] == "Updated Title"

    async def test_upsert_rebuilds_topics(self, seeded_cache: CourseCache) -> None:
        topics = await seeded_cache.get_all_topics()
        slugs = {t["slug"] for t in topics}
        assert "generative-ai" in slugs
        assert "machine-learning" in slugs

    async def test_upsert_sets_last_refresh(self, seeded_cache: CourseCache) -> None:
        status = await seeded_cache.get_status()
        assert status["last_refresh"] != "never"


# ------------------------------------------------------------------
# get_course_by_id
# ------------------------------------------------------------------


class TestGetCourseById:
    async def test_found(self, seeded_cache: CourseCache) -> None:
        row = await seeded_cache.get_course_by_id("building-systems-with-chatgpt")
        assert row is not None
        assert row["title"] == "Building Systems with ChatGPT"

    async def test_not_found(self, seeded_cache: CourseCache) -> None:
        row = await seeded_cache.get_course_by_id("nonexistent")
        assert row is None


# ------------------------------------------------------------------
# search_courses
# ------------------------------------------------------------------


class TestSearchCourses:
    async def test_no_filters(self, seeded_cache: CourseCache) -> None:
        results = await seeded_cache.search_courses()
        assert len(results) == len(SAMPLE_COURSES)

    async def test_query_filter(self, seeded_cache: CourseCache) -> None:
        results = await seeded_cache.search_courses(query="LangChain")
        assert len(results) == 1
        assert results[0]["id"] == "langchain-chat-with-your-data"

    async def test_topic_filter(self, seeded_cache: CourseCache) -> None:
        results = await seeded_cache.search_courses(topic="generative-ai")
        assert len(results) == 2

    async def test_level_filter(self, seeded_cache: CourseCache) -> None:
        results = await seeded_cache.search_courses(level="advanced")
        assert len(results) == 1

    async def test_instructor_filter(self, seeded_cache: CourseCache) -> None:
        results = await seeded_cache.search_courses(instructor="Harrison")
        assert len(results) == 1

    async def test_limit(self, seeded_cache: CourseCache) -> None:
        results = await seeded_cache.search_courses(limit=2)
        assert len(results) == 2

    async def test_combined_filters(self, seeded_cache: CourseCache) -> None:
        results = await seeded_cache.search_courses(
            topic="generative-ai", level="beginner"
        )
        assert len(results) == 1
        assert results[0]["instructor"] == "Andrew Ng"


# ------------------------------------------------------------------
# topics
# ------------------------------------------------------------------


class TestTopics:
    async def test_topic_counts(self, seeded_cache: CourseCache) -> None:
        topics = await seeded_cache.get_all_topics()
        gen_ai = next(t for t in topics if t["slug"] == "generative-ai")
        assert gen_ai["course_count"] == 2


# ------------------------------------------------------------------
# cache status & TTL
# ------------------------------------------------------------------


class TestCacheStatus:
    async def test_status_empty(self, cache: CourseCache) -> None:
        status = await cache.get_status()
        assert status["total_courses"] == 0
        assert status["last_refresh"] == "never"

    async def test_status_seeded(self, seeded_cache: CourseCache) -> None:
        status = await seeded_cache.get_status()
        assert status["total_courses"] == len(SAMPLE_COURSES)
        assert len(status["topics_covered"]) == 3

    async def test_cache_age_never_refreshed(self, cache: CourseCache) -> None:
        age = await cache.get_cache_age_hours()
        assert age == float("inf")

    async def test_cache_age_just_refreshed(self, seeded_cache: CourseCache) -> None:
        age = await seeded_cache.get_cache_age_hours()
        assert age < 0.1  # just refreshed, should be near zero

    async def test_is_stale(self, cache: CourseCache) -> None:
        assert cache.is_stale("2020-01-01T00:00:00+00:00") is True

    async def test_is_not_stale(self, cache: CourseCache) -> None:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        assert cache.is_stale(now) is False


# ------------------------------------------------------------------
# course detail
# ------------------------------------------------------------------


class TestCourseDetail:
    async def test_upsert_and_retrieve_detail(self, seeded_cache: CourseCache) -> None:
        await seeded_cache.upsert_course_detail(
            "building-systems-with-chatgpt", SAMPLE_DETAIL
        )
        row = await seeded_cache.get_course_by_id("building-systems-with-chatgpt")
        assert row is not None
        assert row["detail_json"] is not None
        assert row["detail_at"] is not None
