import asyncio
from playwright.async_api import async_playwright

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto("https://deeplearning.ai/courses", wait_until="domcontentloaded")
        await asyncio.sleep(4)
        
        js_code = """
            () => {
                let results = [];
                document.querySelectorAll('a[href^="/courses/"]').forEach(a => {
                    let card = a;
                    for (let i = 0; i < 6; i++) {
                        if (!card.parentElement) break;
                        card = card.parentElement;
                        if (card.offsetHeight > 80) break;
                    }
                    const badge = card.querySelector('[class*="tag"], [class*="topic"], [class*="category"], [class*="badge"], [class*="label"], [class*="chip"]');
                    results.push({
                        href: a.href,
                        badge: badge ? badge.innerText.trim() : 'NOT FOUND'
                    });
                });
                return results;
            }
        """
        cards = await page.evaluate(js_code)
        for c in cards[:10]:
            print(c)
        await browser.close()

asyncio.run(test())
