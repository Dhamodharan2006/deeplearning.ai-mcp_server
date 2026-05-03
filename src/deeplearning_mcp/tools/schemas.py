"""Pydantic input/output models — single source of truth for all tool shapes."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------


class SearchCoursesInput(BaseModel):
    """Input schema for the search_courses tool."""

    query: str | None = None
    """Free-text search across titles and descriptions."""

    topic: str | None = None
    """Topic slug, e.g. ``"generative-ai"``."""

    level: Literal["beginner", "intermediate", "advanced"] | None = None
    """Difficulty filter."""

    instructor: str | None = None
    """Instructor name (case-insensitive partial match)."""

    limit: int = Field(default=10, ge=1, le=50)
    """Max results to return."""


class GetCourseDetailInput(BaseModel):
    """Input schema for get_course_detail."""

    course_id: str
    """Stable slug ID returned by search_courses."""

    force_refresh: bool = False
    """When *True*, bypass cache and fetch live via Playwright/LLM."""


class ListTopicsInput(BaseModel):
    """Input schema for list_topics (no parameters needed)."""

    pass


class RecommendCoursesInput(BaseModel):
    """Input schema for recommend_courses."""

    goal: str
    """What the learner wants to achieve."""

    background: str | None = None
    """Optional description of existing knowledge."""

    limit: int = Field(default=5, ge=1, le=20)
    """How many recommendations to return."""


class RefreshCacheInput(BaseModel):
    """Input schema for refresh_cache."""

    scope: str = "all"
    """``"all"`` | ``"topic:<slug>"`` | ``"course:<id>"``."""


# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------


class CourseShort(BaseModel):
    """Compact course summary returned by search and recommendation tools."""

    id: str
    title: str
    topic: str
    level: str | None = None
    instructor: str
    url: str
    short_description: str
    cache_age_hours: float


class Lesson(BaseModel):
    """Single lesson inside a course syllabus."""

    title: str
    duration_minutes: int | None = None


class CourseDetail(BaseModel):
    """Full course detail including syllabus and instructor bios."""

    id: str
    title: str
    url: str
    topic: str
    level: str | None = None
    instructors: list[dict]
    lessons: list[Lesson]
    skills_taught: list[str]
    prerequisites: str
    total_hours: float | None = None
    fetched_at: str  # ISO datetime


class TopicSummary(BaseModel):
    """One topic/category with its course count."""

    slug: str
    display_name: str
    course_count: int


class Recommendation(BaseModel):
    """A single course recommendation with ranking rationale."""

    course: CourseShort
    rank: int
    reason: str


class CacheStatus(BaseModel):
    """Current state of the local SQLite cache."""

    total_courses: int
    last_refresh: str  # ISO datetime
    cache_age_hours: float
    topics_covered: list[str]
