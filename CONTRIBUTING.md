# Contributing to deeplearning-mcp

Thanks for your interest in contributing! 🎉

## How to contribute

1. **Fork** the repo and create a feature branch
2. **Install** dev dependencies: `uv sync --all-extras`
3. **Write tests** for any new functionality
4. **Run the test suite**: `uv run pytest tests/ -v`
5. **Open a PR** with a clear description of your changes

## Architecture overview

The codebase is designed around a clean separation:

```
fetcher.py   →  Browser agent that crawls course pages
cache.py     →  SQLite storage and retrieval
tools/*.py   →  Individual MCP tools (one file per tool)
schemas.py   →  Pydantic models (single source of truth)
server.py    →  MCP protocol wiring
```

## Adding support for other platforms

The `DeepLearningFetcher` in `fetcher.py` is designed to be subclassed for
other course platforms. To add support for a new platform (e.g. Coursera,
fast.ai, Udemy):

1. Create a new fetcher class (e.g. `CourseraFetcher`) that implements:
   - `async def fetch_all_courses(self) -> list[dict]`
   - `async def fetch_course_detail(self, url: str) -> dict`
   - `def _generate_course_id(self, url: str) -> str`

2. The return format must match the existing schemas in `tools/schemas.py`

3. The same `CourseCache` and tools can be reused — only the fetcher changes

## Code quality

- **Type hints** on every function signature
- **Docstrings** on every public method
- **No `print()`** — use `logging.getLogger(__name__)`
- **Pydantic models** for all inputs/outputs (no raw dicts)
- **Tests** for every new tool or fetcher method

## Reporting bugs

Please use the [bug report template](.github/ISSUE_TEMPLATE/bug_report.md)
and include:
- Python version
- MCP client used (Claude Code, Claude Desktop, etc.)
- Full error message / traceback
- Steps to reproduce
