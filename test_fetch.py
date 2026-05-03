import asyncio
from deeplearning_mcp.fetcher import DeepLearningFetcher

async def test():
    f = DeepLearningFetcher()
    
    urls = await f._fetch_course_urls_from_sitemap()
    print(f'Sitemap returned {len(urls)} URLs')
    if urls:
        print(f'Sample URL: {urls[0]}')
        
    courses = await f._fetch_courses_playwright_direct()
    print(f'Total courses scraped: {len(courses)}')
    for c in courses[:5]:
        print(f'  {c["id"]:40} | {c["title"][:50]}')

asyncio.run(test())
