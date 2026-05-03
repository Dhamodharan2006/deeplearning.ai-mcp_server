"""Verify the real Algolia credentials work and return courses."""
import asyncio
import json
import httpx


async def test():
    APP_ID  = "Y5109WLMQW"
    API_KEY = "9030ff79d3ba653535d5b66c26b56683"
    INDEX   = "courses_date_desc"

    url = f"https://{APP_ID}-dsn.algolia.net/1/indexes/{INDEX}/query"
    headers = {
        "Content-Type": "application/json",
        "X-Algolia-Application-Id": APP_ID,
        "X-Algolia-API-Key": API_KEY,
    }
    payload = {
        "hitsPerPage": 10,
        "page": 0,
        "attributesToRetrieve": [
            "title", "slug", "url", "short_description",
            "description", "topic", "partner", "instructor",
            "level", "course_type",
        ],
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"Total courses: {data.get('nbHits')}")
            print(f"Total pages:   {data.get('nbPages')}")
            print(f"Index:         {data.get('index')}")
            print("\nFirst 5 hits:")
            for h in data.get("hits", [])[:5]:
                print(f"  - {h.get('title','?')} | topic={h.get('topic','?')} | level={h.get('level','?')}")
                print(f"    instructor={h.get('instructor','?')}")
                print(f"    slug={h.get('slug','?')}")
        else:
            print(resp.text[:500])


asyncio.run(test())
