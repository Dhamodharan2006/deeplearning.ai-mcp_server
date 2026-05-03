"""Tests for search_courses and list_topics tools."""

from __future__ import annotations

import pytest

from deeplearning_mcp.cache import CourseCache
from deeplearning_mcp.tools.schemas import ListTopicsInput, SearchCoursesInput
from deeplearning_mcp.tools.search import search_courses
from deeplearning_mcp.tools.topics import list_topics


# ------------------------------------------------------------------
# search_courses
# ------------------------------------------------------------------


class TestSearchCourses:
    async def test_no_filters(self, seeded_cache: CourseCache) -> None:
        inp = SearchCoursesInput()
        results = await search_courses(inp, seeded_cache)
        assert len(results) == 4

    async def test_query_match(self, seeded_cache: CourseCache) -> None:
        inp = SearchCoursesInput(query="LangChain")
        results = await search_courses(inp, seeded_cache)
        assert len(results) == 1
        assert results[0].id == "langchain-chat-with-your-data"

    async def test_topic_filter(self, seeded_cache: CourseCache) -> None:
        inp = SearchCoursesInput(topic="machine-learning")
        results = await search_courses(inp, seeded_cache)
        assert len(results) == 1

    async def test_level_filter(self, seeded_cache: CourseCache) -> None:
        inp = SearchCoursesInput(level="advanced")
        results = await search_courses(inp, seeded_cache)
        assert len(results) == 1
        assert results[0].id == "deep-learning-specialization"

    async def test_instructor_filter(self, seeded_cache: CourseCache) -> None:
        inp = SearchCoursesInput(instructor="Harrison")
        results = await search_courses(inp, seeded_cache)
        assert len(results) == 1

    async def test_limit(self, seeded_cache: CourseCache) -> None:
        inp = SearchCoursesInput(limit=2)
        results = await search_courses(inp, seeded_cache)
        assert len(results) == 2

    async def test_returns_course_short_models(self, seeded_cache: CourseCache) -> None:
        inp = SearchCoursesInput(query="ChatGPT")
        results = await search_courses(inp, seeded_cache)
        course = results[0]
        assert course.id == "building-systems-with-chatgpt"
        assert course.cache_age_hours < 1.0  # freshly seeded
        assert course.url.startswith("https://")

    async def test_no_results(self, seeded_cache: CourseCache) -> None:
        inp = SearchCoursesInput(query="nonexistent-course-xyz")
        results = await search_courses(inp, seeded_cache)
        assert results == []


# ------------------------------------------------------------------
# list_topics
# ------------------------------------------------------------------


class TestListTopics:
    async def test_returns_topics(self, seeded_cache: CourseCache) -> None:
        inp = ListTopicsInput()
        results = await list_topics(inp, seeded_cache)
        assert len(results) == 3
        slugs = {t.slug for t in results}
        assert "generative-ai" in slugs
        assert "machine-learning" in slugs
        assert "deep-learning" in slugs

    async def test_topic_counts(self, seeded_cache: CourseCache) -> None:
        inp = ListTopicsInput()
        results = await list_topics(inp, seeded_cache)
        gen_ai = next(t for t in results if t.slug == "generative-ai")
        assert gen_ai.course_count == 2

    async def test_empty_cache(self, cache: CourseCache) -> None:
        inp = ListTopicsInput()
        results = await list_topics(inp, cache)
        assert results == []
