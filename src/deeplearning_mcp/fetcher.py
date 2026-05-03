"""Playwright + LLM structured data extractor for DeepLearning.ai."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from playwright.async_api import async_playwright, Browser, Page, Playwright
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = (
    "IMPORTANT: DO NOT ASK QUESTIONS. "
    "Extract data from the provided text content only. "
    "Return ONLY valid JSON — no markdown fences, no explanation, no preamble.\n\n"
    "Task: {task_description}\n\n"
    "Text:\n{text}"
)

_COURSES_URL = "https://deeplearning.ai/courses"

class DeepLearningFetcher:
    """Wraps Playwright to fetch course data from DeepLearning.ai and uses an LLM to extract JSON."""

    def __init__(self) -> None:
        self._headless = os.getenv("BROWSER_HEADLESS", "true").lower() == "true"
        self._timeout = int(os.getenv("PLAYWRIGHT_TIMEOUT", "60000"))
        self._max_scroll_iters = int(os.getenv("MAX_SCROLL_ITERATIONS", "20"))
        
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        
        # Initialize Groq LLM for data extraction
        api_key = os.getenv("GROQ_API_KEY", "")
        self._llm = ChatGroq(
            model_name="llama-3.3-70b-versatile",
            temperature=0,
            max_tokens=4000,
            api_key=api_key
        ) if api_key else None

    async def init(self) -> None:
        """Launch the Playwright browser."""
        if not self._playwright:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self._headless,
                timeout=self._timeout
            )
            logger.info("Playwright browser launched")

    async def close(self) -> None:
        """Close the browser gracefully."""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        logger.info("Playwright browser closed")

    async def _get_page(self) -> Page:
        if not self._browser:
            await self.init()
        assert self._browser is not None
        context = await self._browser.new_context()
        return await context.new_page()

    async def fetch_all_courses(self) -> list[dict]:
        """
        Fetch all DeepLearning.ai courses.

        Priority order:
        1. Algolia API  — instant, no browser, returns ALL 200+ courses
        2. Browser Use agent — LLM-driven browser (fallback if Algolia fails)
        3. Direct Playwright — raw scraper (last resort)
        """

        # ── Strategy 1: Algolia API (preferred — fast and complete) ───────
        try:
            courses = await self._fetch_courses_algolia()
            if len(courses) >= 10:   # sanity check — expect 100+
                logger.info(
                    f"Algolia strategy succeeded: {len(courses)} courses"
                )
                return await self._fill_missing_topics(courses)
            else:
                logger.warning(
                    f"Algolia returned only {len(courses)} courses — "
                    f"falling back to browser"
                )
        except Exception as e:
            logger.warning(f"Algolia strategy failed: {e} — trying browser")

        # ── Strategy 2: Browser Use agent ─────────────────────────────────
        try:
            logger.info("Initializing Playwright to grab raw text for LLM fallback...")
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self._headless)
                ctx = await browser.new_context(
                    viewport={"width": 1280, "height": 900},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                )
                page = await ctx.new_page()
                
                await page.goto(
                    "https://deeplearning.ai/courses",
                    wait_until="domcontentloaded",
                    timeout=int(os.environ.get("PLAYWRIGHT_TIMEOUT", "60000")),
                )
                
                # Wait for initial JS render
                await asyncio.sleep(3)
                
                # Extract raw text specifically from course cards so the LLM doesn't get confused
                html_content = await page.evaluate("""
                    () => {
                        let text = "";
                        const seen = new Set();
                        document.querySelectorAll('a[href^="/courses/"]').forEach(a => {
                            if (a.href.endsWith('/courses/') || seen.has(a.href)) return;
                            seen.add(a.href);
                            
                            let card = a;
                            for (let i = 0; i < 6; i++) {
                                if (!card.parentElement) break;
                                card = card.parentElement;
                                if (card.offsetHeight > 80) break;
                            }
                            
                            // Try to find the topic badge
                            const badge = card.querySelector('[class*="tag"], [class*="topic"], [class*="category"], [class*="badge"]');
                            const topic = badge ? badge.innerText.trim() : "Unknown Topic";
                            
                            text += "--- COURSE CARD ---\\n";
                            text += "URL: " + a.href + "\\n";
                            text += "Topic Badge: " + topic + "\\n";
                            text += "Visible Text:\\n" + card.innerText + "\\n\\n";
                        });
                        return text || document.body.innerText;
                    }
                """)
                await browser.close()

            truncated_content = html_content[:40000]

            logger.info("Sending content to Groq LLM for structured extraction...")
            if not hasattr(self, "_llm") or not self._llm:
                raise RuntimeError("GROQ_API_KEY not set")
                
            task_desc = (
                "Extract EVERY course card visible. "
                "Each object MUST contain the following exact keys: "
                "title, url, topic (use the Topic Badge, if 'Unknown Topic' try to infer it from the title/text), "
                "level, instructor, short_description."
            )
            prompt_content = EXTRACTION_PROMPT.format(
                task_description=task_desc,
                text=truncated_content
            )
            
            completion = self._llm.invoke([
                SystemMessage(content="You are a JSON extractor. You extract a list of courses from the provided webpage text. Always output JSON matching the requested schema. DO NOT output markdown blocks, just raw JSON. The JSON should be an array of objects."),
                HumanMessage(content=prompt_content)
            ])
            
            text = completion.content
            if text.startswith("```json"):
                text = text[7:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
            
            courses_raw = json.loads(text)
            if not isinstance(courses_raw, list):
                if isinstance(courses_raw, dict) and "courses" in courses_raw:
                    courses_raw = courses_raw["courses"]
                else:
                    raise ValueError("Output is not a JSON list")

            courses: list[dict] = []
            for item in courses_raw:
                url = item.get("url", "")
                title = item.get("title", "Unknown")
                
                course_id = self._generate_course_id(url)
                if course_id == "unknown" and title != "Unknown":
                    import re
                    course_id = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
                    if not course_id:
                        course_id = "unknown"

                courses.append({
                    "id": course_id,
                    "title": title,
                    "url": url,
                    "topic": str(item.get("topic") or "").strip(),
                    "level": item.get("level"),
                    "instructor": item.get("instructor", ""),
                    "short_description": item.get("short_description", ""),
                })
            
            logger.info("Fetched %d courses from DeepLearning.ai", len(courses))
            return await self._fill_missing_topics(courses)

        except Exception as e:
            logger.warning(f"Agent approach failed: {e}. Trying direct Playwright...")
            # ── Strategy 3: Direct Playwright fallback ────────────────────────
            courses = await self._fetch_courses_playwright_direct()
            return await self._fill_missing_topics(courses)
            
    async def _fill_missing_topics(self, courses: list[dict]) -> list[dict]:
        """Post-processing step to guarantee no course has an empty topic."""
        for course in courses:
            current_topic = str(course.get("topic") or "").lower().strip()
            if not current_topic or current_topic in ["unknown", "unknown topic", "uncategorised", "none"]:
                try:
                    if self._llm:
                        infer_prompt = f"Determine the primary category for the course '{course.get('title', '')}' based on its description: '{course.get('short_description', '')}'. Return ONLY a 1-3 word category name (e.g. 'Deep Learning', 'Generative AI', 'Data Engineering'). Do not add any punctuation, quotes, or explanation."
                        resp = await self._llm.ainvoke([HumanMessage(content=infer_prompt)])
                        inferred = str(resp.content).strip(' "\'\\n.').title()
                        course["topic"] = inferred if inferred else "General Tech"
                        logger.info(f"Inferred topic '{course['topic']}' for course '{course.get('title')}'")
                    else:
                        course["topic"] = "General Tech"
                except Exception as e:
                    logger.warning(f"Failed to infer topic for {course.get('title')}: {e}")
                    course["topic"] = "General Tech"
        return courses

    async def _fetch_courses_algolia(self) -> list[dict]:
        """
        Fetch ALL courses directly from DeepLearning.ai's Algolia search API.
        No browser required. No LLM required. No scrolling needed.
        Returns complete data for every course in a single paginated request.
        """
        import httpx

        # Public read-only Algolia credentials from deeplearning.ai
        ALGOLIA_APP_ID  = os.environ.get("ALGOLIA_APP_ID",  "Y5109WLMQW")
        ALGOLIA_API_KEY = os.environ.get("ALGOLIA_API_KEY",  "9030ff79d3ba653535d5b66c26b56683")
        ALGOLIA_INDEX   = os.environ.get("ALGOLIA_INDEX",    "courses_date_desc")

        base_url = (
            f"https://{ALGOLIA_APP_ID}-dsn.algolia.net"
            f"/1/indexes/{ALGOLIA_INDEX}/query"
        )
        headers = {
            "Content-Type":           "application/json",
            "X-Algolia-Application-Id": ALGOLIA_APP_ID,
            "X-Algolia-API-Key":       ALGOLIA_API_KEY,
        }

        all_hits = []
        page      = 0
        per_page  = 100   # Algolia max per page

        logger.info("Fetching courses from Algolia API (no browser needed)...")

        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                payload = {
                    "hitsPerPage": per_page,
                    "page":        page,
                    # Request all useful attributes
                    "attributesToRetrieve": [
                        "title", "slug", "url", "short_description",
                        "description", "topic", "partner", "instructor",
                        "level", "course_type", "skills",
                        "num_videos", "duration", "image_url",
                    ],
                }

                resp = await client.post(base_url, headers=headers, json=payload)

                if resp.status_code != 200:
                    logger.error(
                        f"Algolia API error {resp.status_code}: {resp.text[:200]}"
                    )
                    break

                data       = resp.json()
                hits       = data.get("hits", [])
                nb_pages   = data.get("nbPages", 1)
                nb_hits    = data.get("nbHits", 0)

                logger.info(
                    f"Algolia page {page+1}/{nb_pages}: "
                    f"{len(hits)} hits (total: {nb_hits})"
                )

                all_hits.extend(hits)

                if page + 1 >= nb_pages or not hits:
                    break   # all pages fetched
                page += 1

        # ── Normalise hits to our internal schema ─────────────────────────
        now     = datetime.now(timezone.utc).isoformat()
        courses = []

        for hit in all_hits:
            # Build URL — prefer explicit url field, fall back to slug
            slug = hit.get("slug", "").strip("/")
            url  = hit.get("url", "").strip()
            if not url and slug:
                url = f"https://www.deeplearning.ai/courses/{slug}/"
            if not url:
                continue   # can't use a course without a URL

            # Instructor — may be string, list, or under different keys
            instructor_raw = (
                hit.get("instructor")
                or hit.get("instructors")
                or hit.get("partner")
                or hit.get("partners")
                or ""
            )
            if isinstance(instructor_raw, list):
                instructor = ", ".join(str(i) for i in instructor_raw if i)
            else:
                instructor = str(instructor_raw or "").strip()

            # Topic — Algolia returns it as a list e.g. ['Generative AI']
            topic_raw = hit.get("topic", hit.get("topics", ""))
            if isinstance(topic_raw, list):
                topic = topic_raw[0] if topic_raw else ""
            else:
                topic = str(topic_raw or "").strip()

            # Description — prefer short_description, fall back to description
            description = (
                hit.get("short_description")
                or hit.get("description")
                or ""
            )
            if isinstance(description, list):
                description = " ".join(description)
            description = str(description).strip()[:500]

            # Level
            level_raw = hit.get("level", "")
            level     = str(level_raw).lower().strip() if level_raw else None
            if level not in ("beginner", "intermediate", "advanced"):
                level = None

            title = str(hit.get("title", "")).strip()
            if not title:
                title = slug.replace("-", " ").title()

            courses.append({
                "id":                slug or self._generate_course_id(url),
                "title":             title,
                "url":               url,
                "topic":             topic,
                "level":             level,
                "instructor":        instructor,
                "short_description": description,
                "fetched_at":        now,
            })

        logger.info(f"Algolia API returned {len(courses)} courses total")
        return courses

    async def _fetch_course_urls_from_sitemap(self) -> list[str]:
        """
        Fetch course URLs from DeepLearning.ai sitemap.
        Much faster than browser scraping — no JS needed.
        Returns list of full course URLs.
        """
        import httpx

        sitemap_urls = [
            "https://deeplearning.ai/sitemap.xml",
            "https://deeplearning.ai/sitemap-0.xml",
            "https://deeplearning.ai/sitemap_index.xml",
        ]

        course_urls = []
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            for sitemap_url in sitemap_urls:
                try:
                    resp = await client.get(sitemap_url)
                    if resp.status_code != 200:
                        continue
                    text = resp.text
                    # Extract /courses/ URLs from sitemap XML
                    import re
                    found = re.findall(
                        r'<loc>(https://(?:www\.)?deeplearning\.ai/courses/[^<]+)</loc>',
                        text
                    )
                    if found:
                        course_urls.extend(found)
                        logger.info(
                            f"Found {len(found)} course URLs in {sitemap_url}"
                        )
                        break
                except Exception as e:
                    logger.debug(f"Sitemap {sitemap_url} failed: {e}")
                    continue

        # Deduplicate
        return list(dict.fromkeys(course_urls))

    async def _fetch_courses_playwright_direct(self) -> list[dict]:
        """
        Pure Playwright scraper for deeplearning.ai/courses.
        Handles infinite scroll by looping until course count stabilises.
        No LLM required — zero Groq tokens consumed.
        """
        from playwright.async_api import async_playwright
        import asyncio

        logger.info("Starting direct Playwright scraper with scroll loop...")
        now = datetime.now(timezone.utc).isoformat()

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=self._headless,
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                ],
            )
            ctx = await browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
            )
            page = await ctx.new_page()

            # ── Step 1: Navigate ──────────────────────────────────────────
            logger.info("Navigating to deeplearning.ai/courses ...")
            await page.goto(
                "https://deeplearning.ai/courses",
                wait_until="domcontentloaded",
                timeout=60000,
            )

            # Wait for initial JS render
            await asyncio.sleep(4)

            # ── Step 2: Scroll loop until no new courses load ─────────────
            logger.info("Starting scroll loop to load all courses...")
            stable_count = 0
            prev_count   = 0
            max_scrolls  = 40   # safety cap — 40 × ~600px = full long page

            for scroll_i in range(max_scrolls):
                # Scroll down by one viewport height
                await page.evaluate("window.scrollBy(0, window.innerHeight)")
                await asyncio.sleep(2)   # wait for lazy-load API response

                # Count course links currently in DOM
                current_count = await page.evaluate("""
                    () => new Set(
                        [...document.querySelectorAll('a[href]')]
                        .map(a => a.getAttribute('href'))
                        .filter(h => h && h.startsWith('/courses/') && h !== '/courses/')
                    ).size
                """)

                logger.info(
                    f"Scroll {scroll_i+1}: {current_count} unique course links visible"
                )

                if current_count == prev_count:
                    stable_count += 1
                    if stable_count >= 3:
                        # Count didn't change for 3 consecutive scrolls — done
                        logger.info(
                            f"Scroll stabilised at {current_count} courses "
                            f"after {scroll_i+1} scrolls"
                        )
                        break
                else:
                    stable_count = 0   # reset — new courses appeared

                prev_count = current_count

            # ── Step 3: Extract all course data from DOM ──────────────────
            logger.info("Extracting course data from DOM...")
            raw_courses = await page.evaluate("""
                () => {
                    const seen  = new Set();
                    const items = [];

                    // Collect every unique /courses/slug link
                    document.querySelectorAll('a[href]').forEach(a => {
                        const href = a.getAttribute('href') || '';
                        if (!href.startsWith('/courses/')) return;
                        if (href === '/courses/' || href === '/courses') return;
                        if (seen.has(href)) return;
                        seen.add(href);

                        // Walk UP the DOM to find the card container
                        let card = a;
                        for (let i = 0; i < 6; i++) {
                            if (!card.parentElement) break;
                            card = card.parentElement;
                            // Stop at a reasonably-sized container
                            if (card.offsetHeight > 80) break;
                        }

                        const allText = (card.innerText || '')
                            .split('\\n')
                            .map(s => s.trim())
                            .filter(s => s.length > 1);

                        // Title: first meaningful line
                        const title = allText.find(t => t.length > 4) || '';

                        // Instructor: line containing "By " or "Taught by"
                        const instrLine = allText.find(t =>
                            /^(by |with |taught by )/i.test(t)
                        ) || '';
                        const instructor = instrLine
                            .replace(/^(by |with |taught by )/i, '')
                            .trim();

                        // Description: longest line that isn't title/instructor
                        const desc = allText
                            .filter(t => t !== title && t !== instrLine
                                      && t.length > 25 && t.length < 300)
                            .sort((a, b) => b.length - a.length)[0] || '';

                        // Topic / category badge
                        const badge = card.querySelector(
                            '[class*="tag"], [class*="topic"], '  +
                            '[class*="category"], [class*="badge"], ' +
                            '[class*="label"], [class*="chip"]'
                        );
                        const topic = badge
                            ? badge.innerText.trim()
                            : '';

                        // Level
                        const levelMatch = (card.innerText || '')
                            .match(/beginner|intermediate|advanced/i);
                        const level = levelMatch
                            ? levelMatch[0].toLowerCase()
                            : '';

                        const url = 'https://deeplearning.ai' + href;
                        items.push({ url, title, topic, instructor, desc, level });
                    });

                    return items;
                }
            """)

            await browser.close()

        # ── Step 4: Normalise and return ──────────────────────────────────
        courses = []
        for item in (raw_courses or []):
            url   = (item.get("url") or "").strip()
            title = (item.get("title") or "").strip()
            if not url:
                continue
            # Use URL slug as fallback title if title is empty
            if not title:
                title = self._generate_course_id(url).replace("-", " ").title()

            courses.append({
                "id":                self._generate_course_id(url),
                "title":             title,
                "url":               url,
                "topic":             (item.get("topic") or "").strip(),
                "level":             (item.get("level") or None),
                "instructor":        (item.get("instructor") or "").strip(),
                "short_description": (item.get("desc") or "").strip(),
                "fetched_at":        now,
            })

        logger.info(f"Direct Playwright extracted {len(courses)} courses")
        return courses

    async def fetch_course_detail(self, url: str) -> dict:
        """Fetch full detail for a single course page."""
        page = None
        try:
            page = await self._get_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=self._timeout)
            await asyncio.sleep(2)
            text = await page.evaluate("document.body.innerText")
            
            task = (
                "Extract the full course details as JSON: "
                "title, instructors (list of objects with name and bio), "
                "lessons (list of objects with title and duration_minutes), "
                "skills_taught (list of strings), prerequisites (string), "
                "total_hours (number or null). "
                "Return ONLY valid JSON, no extra text."
            )
            prompt = EXTRACTION_PROMPT.format(task_description=task, text=text[:30000])
            
            if not self._llm:
                raise RuntimeError("GROQ_API_KEY not set")
            msg = await self._llm.ainvoke([HumanMessage(content=prompt)])
            raw = msg.content if isinstance(msg.content, str) else str(msg.content)
            detail = self._json_extract_fallback(raw, expect_list=False)
            
            if "extraction_error" in detail:
                detail = {"title": "Unknown", "url": url, "extraction_error": detail["extraction_error"]}

            now = datetime.now(timezone.utc).isoformat()
            return {
                "id": self._generate_course_id(url),
                "title": detail.get("title", "Unknown"),
                "url": url,
                "topic": detail.get("topic", ""),
                "level": detail.get("level"),
                "instructors": detail.get("instructors", []),
                "lessons": detail.get("lessons", []),
                "skills_taught": detail.get("skills_taught", []),
                "prerequisites": detail.get("prerequisites", "None listed"),
                "total_hours": detail.get("total_hours"),
                "fetched_at": now,
            }

        except Exception as e:
            logger.exception("Failed to fetch course detail for %s", url)
            raise RuntimeError(f"Playwright course detail fetch failed: {e}") from e
        finally:
            if page:
                await page.context.close()

    def _generate_course_id(self, url: str) -> str:
        """Derive a stable slug ID from the URL path."""
        path = urlparse(url).path.strip("/")
        slug = path.rsplit("/", 1)[-1] if "/" in path else path
        return slug or "unknown"

    def _json_extract_fallback(self, text: str, *, expect_list: bool) -> list | dict:
        """Best-effort JSON extraction from LLM's sometimes-messy output."""
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            pass

        cleaned = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`")
        try:
            return json.loads(cleaned)
        except (json.JSONDecodeError, TypeError):
            pass

        pattern = r"\[[\s\S]*\]" if expect_list else r"\{[\s\S]*\}"
        match = re.search(pattern, cleaned)
        if match:
            try:
                return json.loads(match.group())
            except (json.JSONDecodeError, TypeError):
                pass

        logger.error("Could not extract JSON from LLM response: %s", text[:500])
        err_dict = {"extraction_error": True}
        return [] if expect_list else err_dict
