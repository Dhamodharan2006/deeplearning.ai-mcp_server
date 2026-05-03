import asyncio
from deeplearning_mcp.fetcher import DeepLearningFetcher
from deeplearning_mcp.cache import CourseCache

async def test():
    # Check 2: direct Algolia call
    f = DeepLearningFetcher()
    courses = await f._fetch_courses_algolia()
    print(f"Total courses from Algolia: {len(courses)}")
    topics = set(c["topic"] for c in courses if c["topic"])
    print(f"Topics ({len(topics)}): {sorted(topics)}")
    instructors = [c["instructor"] for c in courses if c["instructor"]]
    print(f"Courses with instructor: {len(instructors)}")
    for c in courses[:5]:
        print(f"  {c['id']:50} | {c['title'][:45]} | topic={c['topic']}")

    # Check 3: upsert into DB and search
    print("\n--- Upserting into DB ---")
    cache = CourseCache()
    await cache.init_db()
    await cache.upsert_courses(courses)

    results = await cache.search_courses(query="RAG", limit=10)
    print(f"\nSearch 'RAG': {len(results)} results")
    for r in results:
        print(f"  - {r['title']}")

    results = await cache.search_courses(query="LLM", limit=10)
    print(f"\nSearch 'LLM': {len(results)} results")

    results = await cache.search_courses(query="Python", limit=10)
    print(f"\nSearch 'Python': {len(results)} results")

    status = await cache.get_status()
    print(f"\nCache status: {status}")
    await cache.close()

asyncio.run(test())
