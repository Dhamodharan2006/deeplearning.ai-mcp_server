"""Tests for the Playwright + Anthropic fetcher."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from deeplearning_mcp.fetcher import DeepLearningFetcher


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

FAKE_COURSES_JSON = [
    {
        "title": "Building Systems with ChatGPT",
        "url": "https://deeplearning.ai/short-courses/building-systems-with-chatgpt/",
        "topic": "generative-ai",
        "level": "beginner",
        "instructor": "Andrew Ng",
        "short_description": "Build systems using ChatGPT.",
    },
    {
        "title": "LangChain: Chat With Your Data",
        "url": "https://deeplearning.ai/short-courses/langchain-chat-with-your-data/",
        "topic": "generative-ai",
        "level": "intermediate",
        "instructor": "Harrison Chase",
        "short_description": "Chat with documents via LangChain.",
    },
]

FAKE_DETAIL_JSON = {
    "title": "Building Systems with ChatGPT",
    "instructors": [{"name": "Andrew Ng", "bio": "Founder"}],
    "lessons": [
        {"title": "Intro", "duration_minutes": 5},
        {"title": "Building", "duration_minutes": 15},
    ],
    "skills_taught": ["Prompt engineering"],
    "prerequisites": "Basic Python",
    "total_hours": 1.5,
}

def _mock_llm_response(data: list | dict) -> AIMessage:
    return AIMessage(content=json.dumps(data))

# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


class TestGenerateCourseId:
    def test_normal_url(self) -> None:
        f = DeepLearningFetcher()
        assert (
            f._generate_course_id(
                "https://deeplearning.ai/short-courses/building-systems-with-chatgpt/"
            )
            == "building-systems-with-chatgpt"
        )

    def test_nested_path(self) -> None:
        f = DeepLearningFetcher()
        assert (
            f._generate_course_id(
                "https://deeplearning.ai/courses/deep-learning-specialization/"
            )
            == "deep-learning-specialization"
        )

    def test_empty_url(self) -> None:
        f = DeepLearningFetcher()
        assert f._generate_course_id("") == "unknown"


class TestExtractJson:
    def test_clean_json(self) -> None:
        f = DeepLearningFetcher()
        data = [{"a": 1}]
        assert f._json_extract_fallback(json.dumps(data), expect_list=True) == data

    def test_markdown_fenced_json(self) -> None:
        f = DeepLearningFetcher()
        raw = '```json\n[{"a": 1}]\n```'
        assert f._json_extract_fallback(raw, expect_list=True) == [{"a": 1}]

    def test_surrounded_text(self) -> None:
        f = DeepLearningFetcher()
        raw = 'Here are the results: [{"a": 1}] Hope this helps!'
        assert f._json_extract_fallback(raw, expect_list=True) == [{"a": 1}]

    def test_unparseable_returns_empty(self) -> None:
        f = DeepLearningFetcher()
        assert f._json_extract_fallback("totally not json", expect_list=True) == []
        err_res = f._json_extract_fallback("totally not json", expect_list=False)
        assert err_res == {"extraction_error": True}


class TestFetchAllCourses:
    @pytest.mark.asyncio
    @patch("deeplearning_mcp.fetcher.ChatGroq.ainvoke")
    async def test_fetch_all_returns_courses(self, mock_ainvoke: MagicMock, mock_playwright) -> None:
        mock_ainvoke.return_value = _mock_llm_response(FAKE_COURSES_JSON)

        fetcher = DeepLearningFetcher()
        courses = await fetcher.fetch_all_courses()

        assert len(courses) == 2
        assert courses[0]["id"] == "building-systems-with-chatgpt"
        assert courses[1]["id"] == "langchain-chat-with-your-data"
        assert courses[0]["title"] == "Building Systems with ChatGPT"

    @pytest.mark.asyncio
    @patch("deeplearning_mcp.fetcher.ChatGroq.ainvoke")
    async def test_fetch_all_handles_error(self, mock_ainvoke: MagicMock, mock_playwright) -> None:
        mock_ainvoke.side_effect = RuntimeError("llm failed")

        fetcher = DeepLearningFetcher()
        with pytest.raises(RuntimeError, match="llm failed"):
            await fetcher.fetch_all_courses()


class TestFetchCourseDetail:
    @pytest.mark.asyncio
    @patch("deeplearning_mcp.fetcher.ChatGroq.ainvoke")
    async def test_fetch_detail_returns_dict(self, mock_ainvoke: MagicMock, mock_playwright) -> None:
        mock_ainvoke.return_value = _mock_llm_response(FAKE_DETAIL_JSON)

        fetcher = DeepLearningFetcher()
        detail = await fetcher.fetch_course_detail(
            "https://deeplearning.ai/short-courses/building-systems-with-chatgpt/"
        )

        assert detail["id"] == "building-systems-with-chatgpt"
        assert detail["title"] == "Building Systems with ChatGPT"
        assert len(detail["instructors"]) == 1
        assert len(detail["lessons"]) == 2
        assert detail["fetched_at"]  # should be an ISO datetime

    @pytest.mark.asyncio
    @patch("deeplearning_mcp.fetcher.ChatGroq.ainvoke")
    async def test_fetch_detail_handles_bad_json(self, mock_ainvoke: MagicMock, mock_playwright) -> None:
        mock_ainvoke.return_value = AIMessage(content="not json at all")

        fetcher = DeepLearningFetcher()
        detail = await fetcher.fetch_course_detail("https://example.com/course/")

        # Should not raise; returns a dict with defaults and extraction error
        assert detail["id"] == "course"
        assert detail["title"] == "Unknown"
