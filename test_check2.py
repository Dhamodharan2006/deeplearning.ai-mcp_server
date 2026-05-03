import asyncio, os
os.environ.setdefault('GROQ_API_KEY', 'not-needed-for-algolia')
from deeplearning_mcp.fetcher import DeepLearningFetcher

async def test():
    f = DeepLearningFetcher()
    courses = await f.fetch_all_courses()
    print(f'Total: {len(courses)}')
    topics = set(c['topic'] for c in courses if c['topic'])
    print(f'Topics: {sorted(topics)}')
    for c in courses[:5]:
        print(f'  {c["id"]:45} | {c["title"][:50]}')

asyncio.run(test())
