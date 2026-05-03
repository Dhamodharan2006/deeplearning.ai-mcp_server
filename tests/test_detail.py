"""Tests for get_course_detail tool."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from deeplearning_mcp.cache import CourseCache
from deeplearning_mcp.fetcher import DeepLearningFetcher
from deeplearning_mcp.tools.detail import get_course_detail
from deeplearning_mcp.tools.schemas import GetCourseDetailInput
from conftest import SAMPLE_COURSES, SAMPLE_DETAIL


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


class TestGetCourseDetail:
    async def test_not_found_raises(self, seeded_cache: CourseCache) -> None:
        inp = GetCourseDetailInput(course_id="nonexistent")
        fetcher = DeepLearningFetcher()
        with pytest.raises(ValueError, match="not found"):
            await get_course_detail(inp, seeded_cache, fetcher)

    async def test_returns_cached_detail(self, seeded_cache: CourseCache) -> None:
        # Pre-store detail
        await seeded_cache.upsert_course_detail(
            "building-systems-with-chatgpt", SAMPLE_DETAIL
        )
        inp = GetCourseDetailInput(course_id="building-systems-with-chatgpt")
        fetcher = DeepLearningFetcher()  # should NOT be called

        result = await get_course_detail(inp, seeded_cache, fetcher)

        assert result.id == "building-systems-with-chatgpt"
        assert result.title == "Building Systems with ChatGPT"
        assert len(result.lessons) == 2
        assert result.lessons[0].title == "Introduction"

    @patch("deeplearning_mcp.tools.detail.DeepLearningFetcher", autospec=True)
    async def test_fetches_on_cache_miss(
        self, MockFetcher: MagicMock, seeded_cache: CourseCache
    ) -> None:
        # No detail_json stored — should trigger fetcher
        fetcher = MockFetcher()
        fetcher.fetch_course_detail = AsyncMock(return_value=SAMPLE_DETAIL)

        inp = GetCourseDetailInput(course_id="building-systems-with-chatgpt")
        result = await get_course_detail(inp, seeded_cache, fetcher)

        fetcher.fetch_course_detail.assert_called_once()
        assert result.title == "Building Systems with ChatGPT"

        # Verify it was cached
        row = await seeded_cache.get_course_by_id("building-systems-with-chatgpt")
        assert row["detail_json"] is not None

    @patch("deeplearning_mcp.tools.detail.DeepLearningFetcher", autospec=True)
    async def test_force_refresh_bypasses_cache(
        self, MockFetcher: MagicMock, seeded_cache: CourseCache
    ) -> None:
        # Pre-store detail
        await seeded_cache.upsert_course_detail(
            "building-systems-with-chatgpt", SAMPLE_DETAIL
        )

        updated_detail = {**SAMPLE_DETAIL, "title": "Refreshed Title"}
        fetcher = MockFetcher()
        fetcher.fetch_course_detail = AsyncMock(return_value=updated_detail)

        inp = GetCourseDetailInput(
            course_id="building-systems-with-chatgpt", force_refresh=True
        )
        result = await get_course_detail(inp, seeded_cache, fetcher)

        fetcher.fetch_course_detail.assert_called_once()
        assert result.title == "Refreshed Title"
