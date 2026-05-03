"""Shared fixtures for the deeplearning-mcp test suite."""

from __future__ import annotations

import asyncio
import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio

from deeplearning_mcp.cache import CourseCache

# Force an in-memory DB for tests (fast, no disk artefacts)
os.environ.setdefault("CACHE_DB_PATH", ":memory:")
os.environ.setdefault("CACHE_TTL_HOURS", "24")
os.environ.setdefault("MAX_SCROLL_ITERATIONS", "1")
os.environ.setdefault("BROWSER_HEADLESS", "true")
os.environ.setdefault("BROWSER_TIMEOUT_MS", "5000")
os.environ.setdefault("GROQ_API_KEY", "test_key")


SAMPLE_COURSES: list[dict] = [
    {
        "id": "building-systems-with-chatgpt",
        "title": "Building Systems with ChatGPT",
        "url": "https://www.deeplearning.ai/short-courses/building-systems-with-chatgpt/",
        "topic": "generative-ai",
        "level": "beginner",
        "instructor": "Andrew Ng",
        "short_description": "Learn to build systems using ChatGPT APIs.",
    },
    {
        "id": "langchain-chat-with-your-data",
        "title": "LangChain: Chat With Your Data",
        "url": "https://www.deeplearning.ai/short-courses/langchain-chat-with-your-data/",
        "topic": "generative-ai",
        "level": "intermediate",
        "instructor": "Harrison Chase",
        "short_description": "Use LangChain to chat with your own documents.",
    },
    {
        "id": "machine-learning-specialization",
        "title": "Machine Learning Specialization",
        "url": "https://www.deeplearning.ai/courses/machine-learning-specialization/",
        "topic": "machine-learning",
        "level": "beginner",
        "instructor": "Andrew Ng",
        "short_description": "Comprehensive ML course covering supervised and unsupervised learning.",
    },
    {
        "id": "deep-learning-specialization",
        "title": "Deep Learning Specialization",
        "url": "https://www.deeplearning.ai/courses/deep-learning-specialization/",
        "topic": "deep-learning",
        "level": "advanced",
        "instructor": "Andrew Ng",
        "short_description": "Master deep learning fundamentals and neural networks.",
    },
]


SAMPLE_DETAIL: dict = {
    "id": "building-systems-with-chatgpt",
    "title": "Building Systems with ChatGPT",
    "url": "https://www.deeplearning.ai/short-courses/building-systems-with-chatgpt/",
    "topic": "generative-ai",
    "level": "beginner",
    "instructors": [
        {"name": "Andrew Ng", "bio": "Co-founder of DeepLearning.AI"}
    ],
    "lessons": [
        {"title": "Introduction", "duration_minutes": 5},
        {"title": "Building Chains", "duration_minutes": 15},
    ],
    "skills_taught": ["Prompt engineering", "API integration"],
    "prerequisites": "Basic Python knowledge",
    "total_hours": 1.5,
    "fetched_at": "2026-01-01T00:00:00+00:00",
}


@pytest_asyncio.fixture
async def cache() -> AsyncGenerator[CourseCache, None]:
    """Provide a fresh in-memory CourseCache for each test."""
    c = CourseCache(db_path=":memory:")
    await c.init_db()
    yield c
    await c.close()


@pytest_asyncio.fixture
async def seeded_cache(cache: CourseCache) -> CourseCache:
    """CourseCache pre-loaded with SAMPLE_COURSES."""
    await cache.upsert_courses(SAMPLE_COURSES)
    return cache

@pytest.fixture
def mock_playwright(mocker):
    """Mock Playwright for testing fetcher without a real browser."""
    mock_page = mocker.AsyncMock()
    mock_page.content.return_value = "<html><body>Fake HTML</body></html>"
    mock_page.evaluate.return_value = "<html><body>Fake HTML</body></html>"
    
    mock_context = mocker.AsyncMock()
    mock_context.new_page.return_value = mock_page
    
    mock_browser = mocker.AsyncMock()
    mock_browser.new_context.return_value = mock_context
    
    mock_playwright_obj = mocker.AsyncMock()
    mock_playwright_obj.chromium.launch.return_value = mock_browser
    
    mock_start = mocker.AsyncMock()
    mock_start.start.return_value = mock_playwright_obj
    
    mocker.patch("deeplearning_mcp.fetcher.async_playwright", return_value=mock_start)
    return mock_page
