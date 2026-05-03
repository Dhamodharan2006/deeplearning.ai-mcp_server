"""MCP server entrypoint — registers all 6 tools and manages lifecycle."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys

from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from deeplearning_mcp.cache import CourseCache
from deeplearning_mcp.fetcher import DeepLearningFetcher
from deeplearning_mcp.scheduler import CacheScheduler
from deeplearning_mcp.tools.cache_mgmt import get_cache_status, refresh_cache
from deeplearning_mcp.tools.detail import get_course_detail
from deeplearning_mcp.tools.recommend import recommend_courses
from deeplearning_mcp.tools.schemas import (
    GetCourseDetailInput,
    ListTopicsInput,
    RecommendCoursesInput,
    RefreshCacheInput,
    SearchCoursesInput,
)
from deeplearning_mcp.tools.search import search_courses
from deeplearning_mcp.tools.topics import list_topics

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(name)s] %(levelname)s — %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

app = Server("deeplearning-mcp")

# Module-level singletons — initialised in main()
_cache: CourseCache | None = None
_fetcher: DeepLearningFetcher | None = None
_scheduler: CacheScheduler | None = None

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

def _fix_schema(schema: dict) -> dict:
    """Ensure the JSON schema has 'type': 'object' instead of ['object'] for MCP compatibility."""
    if "type" in schema and isinstance(schema["type"], list):
        if "object" in schema["type"]:
            schema["type"] = "object"
    return schema


_TOOLS: list[Tool] = [
    Tool(
        name="search_courses",
        description=(
            "Search DeepLearning.ai courses by keyword, topic, level, or "
            "instructor. Returns a list of matching courses from the local cache. "
            "Always call this before get_course_detail to get a course_id."
        ),
        inputSchema=_fix_schema(SearchCoursesInput.model_json_schema()),
    ),
    Tool(
        name="get_course_detail",
        description=(
            "Get the full syllabus, lesson list, skills taught, prerequisites, "
            "and instructor bios for a single course. Uses course_id from "
            "search_courses. Set force_refresh=true only if the user explicitly "
            "asks for the very latest data."
        ),
        inputSchema=_fix_schema(GetCourseDetailInput.model_json_schema()),
    ),
    Tool(
        name="list_topics",
        description=(
            "List all available topics/categories on DeepLearning.ai with the "
            "number of courses in each. Call this first if the user is exploring "
            "what's available or if you need a valid topic slug for search_courses."
        ),
        inputSchema=_fix_schema(ListTopicsInput.model_json_schema()),
    ),
    Tool(
        name="recommend_courses",
        description=(
            "Given a learning goal and optional background, recommend the best "
            "DeepLearning.ai courses in suggested study order. Returns ranked "
            "courses with a reason for each recommendation."
        ),
        inputSchema=_fix_schema(RecommendCoursesInput.model_json_schema()),
    ),
    Tool(
        name="refresh_cache",
        description=(
            "Trigger a fresh crawl of DeepLearning.ai to rebuild the course "
            "cache using a live browser agent. Use scope='all' to refresh "
            "everything, 'topic:slug' for one topic, or 'course:id' for a "
            "single course. This takes 2-5 minutes for a full refresh. Only "
            "call this when the user explicitly asks for fresh data or "
            "get_cache_status shows data older than 48 hours."
        ),
        inputSchema=_fix_schema(RefreshCacheInput.model_json_schema()),
    ),
    Tool(
        name="get_cache_status",
        description=(
            "Check how fresh the local course cache is. Returns total courses "
            "stored, last refresh timestamp, and topics covered. Call this "
            "first when the user asks about 'latest' or 'new' courses to "
            "decide whether a refresh is needed."
        ),
        inputSchema={"type": "object", "properties": {}},
    ),
]


@app.list_tools()
async def handle_list_tools() -> list[Tool]:
    """Return the full list of available tools."""
    return _TOOLS


@app.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Dispatch a tool call to the correct handler."""
    assert _cache is not None and _fetcher is not None

    try:
        if name == "search_courses":
            inp = SearchCoursesInput(**arguments)
            result = await search_courses(inp, _cache)
            payload = [r.model_dump() for r in result]

        elif name == "get_course_detail":
            inp = GetCourseDetailInput(**arguments)
            result = await get_course_detail(inp, _cache, _fetcher)
            payload = result.model_dump()

        elif name == "list_topics":
            inp = ListTopicsInput(**arguments)
            result = await list_topics(inp, _cache)
            payload = [r.model_dump() for r in result]

        elif name == "recommend_courses":
            inp = RecommendCoursesInput(**arguments)
            result = await recommend_courses(inp, _cache)
            payload = [r.model_dump() for r in result]

        elif name == "refresh_cache":
            inp = RefreshCacheInput(**arguments)
            message = await refresh_cache(inp, _cache, _fetcher)
            payload = {"message": message}

        elif name == "get_cache_status":
            result = await get_cache_status(_cache)
            payload = result.model_dump()

        else:
            payload = {"error": f"Unknown tool: {name}"}

        return [TextContent(type="text", text=json.dumps(payload, indent=2))]

    except Exception as exc:
        logger.exception("Tool '%s' raised an error", name)
        return [
            TextContent(
                type="text",
                text=json.dumps({"error": str(exc)}),
            )
        ]


# ---------------------------------------------------------------------------
# Server lifecycle
# ---------------------------------------------------------------------------


async def main() -> None:
    """Initialise components and run the MCP server on stdio."""
    global _cache, _fetcher, _scheduler

    _cache = CourseCache()
    await _cache.init_db()

    _fetcher = DeepLearningFetcher()
    await _fetcher.init()

    _scheduler = CacheScheduler()
    _scheduler.start(_fetcher, _cache)

    logger.info("deeplearning-mcp running on stdio")

    try:
        async with stdio_server() as (read_stream, write_stream):
            await app.run(
                read_stream,
                write_stream,
                app.create_initialization_options(),
            )
    finally:
        _scheduler.stop()
        if _fetcher:
            await _fetcher.close()
        await _cache.close()
        logger.info("deeplearning-mcp shut down gracefully")


def main_sync() -> None:
    """Synchronous entry point for the ``deeplearning-mcp`` console script."""
    asyncio.run(main())


if __name__ == "__main__":
    main_sync()
