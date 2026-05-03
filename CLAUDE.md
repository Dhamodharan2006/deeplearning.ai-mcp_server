# deeplearning-mcp — Project Memory

## What this is
MCP server that fetches DeepLearning.ai courses via MultiOn browser agent
and serves them to Claude through 6 tools. SQLite cache with nightly refresh.

## Stack
- Python 3.11+, MCP SDK, MultiOn, aiosqlite, APScheduler, Pydantic v2, uv

## Key decisions made (do not revisit without reason)
- Cache-first for all read tools — MultiOn only on refresh or cache miss
- SQLite (not PostgreSQL) — zero-dependency for open-source users
- Course ID = URL slug (stable across fetches)
- Recommend logic is pure Python scoring (no LLM call inside the tool)
- All MultiOn prompts wrap with the "DO NOT ASK QUESTIONS / return JSON only" header

## File map
- server.py       → MCP entrypoint, tool registration
- fetcher.py      → MultiOn wrapper
- cache.py        → SQLite async layer
- scheduler.py    → Nightly cron
- tools/schemas.py → All Pydantic models (source of truth for shapes)
- tools/search.py  → search_courses
- tools/detail.py  → get_course_detail
- tools/topics.py  → list_topics
- tools/recommend.py → recommend_courses (pure Python scoring)
- tools/cache_mgmt.py → refresh_cache + get_cache_status

## DB location
data/courses.db — created on first run, gitignored

## Running locally
uv run python -m deeplearning_mcp.server

## Adding to Claude Code
claude mcp add deeplearning-mcp --scope project \
  -- uv run --project /path/to/deeplearning-mcp \
     python -m deeplearning_mcp.server

## Common failure modes
- MultiOn returns text not JSON → fetcher.py has a json_extract_fallback()
  that strips markdown fences and retries json.loads
- DeepLearning.ai adds new topics → list_topics auto-discovers on next refresh
- MultiOn session hangs → MAX_MULTION_STEPS env var caps at 15 by default
