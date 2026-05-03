"""
Intercepts real Algolia credentials from deeplearning.ai.
Scans both network requests AND embedded Next.js JS bundles.
"""
import asyncio
import re
import json
from playwright.async_api import async_playwright


async def find_creds():
    found_creds = {}
    js_urls = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # ── Intercept every request ────────────────────────────────────
        async def on_request(request):
            url = request.url
            headers = request.headers

            # Direct Algolia API call — grab headers
            if "algolia.net" in url or "algolia.io" in url:
                print(f"\n[ALGOLIA REQUEST] {url}")
                for k, v in headers.items():
                    if "algolia" in k.lower():
                        print(f"  {k}: {v}")
                        found_creds[k] = v
                try:
                    body = request.post_data
                    if body:
                        print(f"  body: {body[:200]}")
                except Exception:
                    pass

            # Collect Next.js JS chunks to scan later
            if "_next/static" in url and url.endswith(".js"):
                js_urls.append(url)

        page.on("request", on_request)

        print("Loading deeplearning.ai/courses ...")
        await page.goto(
            "https://deeplearning.ai/courses",
            wait_until="domcontentloaded",
            timeout=60000,
        )
        # Wait for Algolia XHR calls to fire
        await asyncio.sleep(6)

        await browser.close()

    # ── If we didn't catch headers, scan JS bundles ────────────────────
    if not found_creds and js_urls:
        print(f"\nNo direct Algolia headers captured. Scanning {len(js_urls)} JS bundles...")
        import httpx
        patterns = {
            "app_id":  re.compile(r'"(?:appId|applicationId)"\s*:\s*"([A-Z0-9]{8,12})"', re.I),
            "api_key": re.compile(r'"(?:apiKey|searchApiKey|searchKey)"\s*:\s*"([a-f0-9]{32})"', re.I),
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            for js_url in js_urls[:30]:  # scan first 30 chunks
                try:
                    resp = await client.get(js_url)
                    text = resp.text
                    for key, pat in patterns.items():
                        m = pat.search(text)
                        if m:
                            print(f"  [{js_url.split('/')[-1]}] {key}: {m.group(1)}")
                            found_creds[key] = m.group(1)
                except Exception as e:
                    pass

    print("\n=== RESULT ===")
    print(json.dumps(found_creds, indent=2))
    return found_creds


asyncio.run(find_creds())
