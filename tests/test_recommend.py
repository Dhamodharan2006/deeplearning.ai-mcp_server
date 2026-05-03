"""Tests for the recommend_courses tool."""

from __future__ import annotations

import pytest

from deeplearning_mcp.cache import CourseCache
from deeplearning_mcp.tools.recommend import (
    _generate_reason,
    _infer_level,
    _score_course,
    _tokenise,
    recommend_courses,
)
from deeplearning_mcp.tools.schemas import RecommendCoursesInput


# ------------------------------------------------------------------
# Helper unit tests
# ------------------------------------------------------------------


class TestTokenise:
    def test_basic(self) -> None:
        assert _tokenise("Hello World") == {"hello", "world"}

    def test_with_punctuation(self) -> None:
        tokens = _tokenise("LangChain: Chat-With-Your-Data!")
        assert "langchain" in tokens
        assert "chat" in tokens
        assert "data" in tokens


class TestInferLevel:
    def test_no_background(self) -> None:
        assert _infer_level(None) == "beginner"

    def test_beginner(self) -> None:
        assert _infer_level("I'm new to programming") == "beginner"

    def test_intermediate(self) -> None:
        assert _infer_level("I'm familiar with the basics of ML") == "intermediate"

    def test_advanced(self) -> None:
        assert _infer_level("I have 5 years of experience as a senior ML engineer") == "advanced"


class TestScoreCourse:
    def test_perfect_keyword_match(self) -> None:
        row = {
            "title": "Deep Learning",
            "short_desc": "Learn neural networks",
            "level": "beginner",
            "topic": "deep-learning",
            "fetched_at": "2026-05-01T00:00:00+00:00",
        }
        scores = _score_course(
            row,
            all_tokens={"deep", "learning", "neural", "networks"},
            goal_tokens={"deep", "learning"},
            target_level="beginner",
        )
        assert scores["keyword"] == 40.0  # 4 tokens × 10, capped at 40
        assert scores["level"] == 20.0    # exact match

    def test_level_mismatch(self) -> None:
        row = {
            "title": "Advanced ML",
            "short_desc": "",
            "level": "advanced",
            "topic": "",
            "fetched_at": "2026-05-01T00:00:00+00:00",
        }
        scores = _score_course(row, set(), set(), target_level="beginner")
        assert scores["level"] == 0.0  # 2 levels apart


class TestGenerateReason:
    def test_keyword_reason(self) -> None:
        row = {"title": "ChatGPT Course"}
        scores = {"keyword": 40, "level": 10, "topic": 5, "freshness": 10}
        reason = _generate_reason(row, scores)
        assert "ChatGPT Course" in reason
        assert "learning goals" in reason


# ------------------------------------------------------------------
# Integration tests
# ------------------------------------------------------------------


class TestRecommendCourses:
    async def test_returns_ranked_results(self, seeded_cache: CourseCache) -> None:
        inp = RecommendCoursesInput(goal="learn deep learning and neural networks")
        results = await recommend_courses(inp, seeded_cache)

        assert len(results) <= 5
        assert results[0].rank == 1
        # Deep learning course should rank high
        ids = [r.course.id for r in results]
        assert "deep-learning-specialization" in ids

    async def test_limit(self, seeded_cache: CourseCache) -> None:
        inp = RecommendCoursesInput(goal="machine learning", limit=2)
        results = await recommend_courses(inp, seeded_cache)
        assert len(results) == 2

    async def test_with_background(self, seeded_cache: CourseCache) -> None:
        inp = RecommendCoursesInput(
            goal="learn generative AI",
            background="I'm familiar with the basics of ML",
        )
        results = await recommend_courses(inp, seeded_cache)
        assert len(results) > 0
        # All results should have reasons
        for r in results:
            assert len(r.reason) > 0

    async def test_empty_cache(self, cache: CourseCache) -> None:
        inp = RecommendCoursesInput(goal="anything")
        results = await recommend_courses(inp, cache)
        assert results == []

    async def test_ranks_are_sequential(self, seeded_cache: CourseCache) -> None:
        inp = RecommendCoursesInput(goal="AI courses", limit=4)
        results = await recommend_courses(inp, seeded_cache)
        ranks = [r.rank for r in results]
        assert ranks == list(range(1, len(results) + 1))
