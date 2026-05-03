const { chromium } = require('playwright');

(async () => {
    const browser = await chromium.launch();
    const page = await browser.newPage();
    await page.goto('https://deeplearning.ai/courses', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(4000);
    
    const cards = await page.evaluate(() => {
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
                badge: badge ? badge.innerText.trim() : 'NOT FOUND',
            });
        });
        return results;
    });
    
    console.log(cards.slice(0, 10));
    await browser.close();
})();
