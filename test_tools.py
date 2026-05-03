import asyncio
import os
import json
from deeplearning_mcp.server import handle_call_tool, _cache, _fetcher, _scheduler, app
from deeplearning_mcp.cache import CourseCache
from deeplearning_mcp.fetcher import DeepLearningFetcher
from deeplearning_mcp.scheduler import CacheScheduler
import deeplearning_mcp.server as server_module

async def run_tests():
    # Initialize components
    print("Initializing components...")
    server_module._cache = CourseCache()
    await server_module._cache.init_db()
    server_module._fetcher = DeepLearningFetcher()
    await server_module._fetcher.init()
    
    try:
        # 1. get_cache_status
        print("\n--- 1. Testing get_cache_status ---")
        res = await handle_call_tool("get_cache_status", {})
        print(json.dumps(json.loads(res[0].text), indent=2))

        # 2. refresh_cache (fetch live using Groq)
        print("\n--- 2. Testing refresh_cache (live fetch) ---")
        res = await handle_call_tool("refresh_cache", {"scope": "all"})
        print(json.dumps(json.loads(res[0].text), indent=2))

        # 3. search_courses
        print("\n--- 3. Testing search_courses ---")
        res = await handle_call_tool("search_courses", {"query": "AI"})
        print(json.dumps(json.loads(res[0].text)[:2], indent=2)) # Print first 2

        # 4. list_topics
        print("\n--- 4. Testing list_topics ---")
        res = await handle_call_tool("list_topics", {})
        print(json.dumps(json.loads(res[0].text)[:3], indent=2)) # Print first 3

        # 5. get_course_detail (for the first course found)
        print("\n--- 5. Testing get_course_detail ---")
        courses = json.loads((await handle_call_tool("search_courses", {"query": "AI"}))[0].text)
        if courses:
            first_course_id = courses[0]["id"]
            res = await handle_call_tool("get_course_detail", {"course_id": first_course_id})
            print(json.dumps(json.loads(res[0].text), indent=2))
        else:
            print("No courses found to detail.")

        # 6. recommend_courses
        print("\n--- 6. Testing recommend_courses ---")
        res = await handle_call_tool("recommend_courses", {"goal": "learn prompt engineering", "limit": 2})
        print(json.dumps(json.loads(res[0].text), indent=2))

    finally:
        print("\nShutting down...")
        await server_module._fetcher.close()
        await server_module._cache.close()

if __name__ == "__main__":
    asyncio.run(run_tests())
