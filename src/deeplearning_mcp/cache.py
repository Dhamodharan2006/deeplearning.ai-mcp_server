"""SQLite async cache layer for course data with TTL support."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS courses (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    url         TEXT NOT NULL,
    topic       TEXT,
    level       TEXT,
    instructor  TEXT,
    short_desc  TEXT,
    detail_json TEXT,
    fetched_at  TEXT NOT NULL,
    detail_at   TEXT
);

CREATE TABLE IF NOT EXISTS topics (
    slug         TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    course_count INTEGER DEFAULT 0,
    updated_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class CourseCache:
    """Async SQLite cache for DeepLearning.ai courses."""

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path or os.getenv(
            "CACHE_DB_PATH", "data/courses.db"
        )
        self._ttl_hours = float(os.getenv("CACHE_TTL_HOURS", "24"))
        self._db: aiosqlite.Connection | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def init_db(self) -> None:
        """Create the database file and tables if they don't exist."""
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self._db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(_SCHEMA_SQL)
        await self._db.commit()
        logger.info("Cache DB initialised at %s", self._db_path)

    async def close(self) -> None:
        """Close the database connection."""
        if self._db:
            await self._db.close()
            self._db = None

    @property
    def db(self) -> aiosqlite.Connection:
        """Return the active connection, raising if not initialised."""
        if self._db is None:
            raise RuntimeError("CourseCache.init_db() has not been called")
        return self._db

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    async def upsert_courses(self, courses: list[dict]) -> int:
        """Bulk insert or update courses. Returns the number of rows upserted."""
        now = datetime.now(timezone.utc).isoformat()
        rows_affected = 0
        for c in courses:
            await self.db.execute(
                """
                INSERT INTO courses (id, title, url, topic, level, instructor,
                                     short_desc, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title      = excluded.title,
                    url        = excluded.url,
                    topic      = excluded.topic,
                    level      = excluded.level,
                    instructor = excluded.instructor,
                    short_desc = excluded.short_desc,
                    fetched_at = excluded.fetched_at
                """,
                (
                    c["id"],
                    c["title"],
                    c["url"],
                    c.get("topic", ""),
                    c.get("level"),
                    c.get("instructor", ""),
                    c.get("short_description", ""),
                    now,
                ),
            )
            rows_affected += 1
        # Cleanup any stale empty topics in the DB
        await self.db.execute("UPDATE courses SET topic = 'General Tech' WHERE topic = '' OR topic IS NULL OR LOWER(topic) = 'uncategorised'")
        
        # Rebuild topic counts
        await self._rebuild_topics(now)
        # Update last_refresh meta
        await self.db.execute(
            "INSERT INTO meta (key, value) VALUES ('last_refresh', ?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (now,),
        )
        await self.db.commit()
        logger.info("Upserted %d courses", rows_affected)
        return rows_affected

    async def upsert_course_detail(self, course_id: str, detail: dict) -> None:
        """Store full course detail JSON for one course."""
        now = datetime.now(timezone.utc).isoformat()
        await self.db.execute(
            "UPDATE courses SET detail_json = ?, detail_at = ? WHERE id = ?",
            (json.dumps(detail), now, course_id),
        )
        await self.db.commit()

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    async def get_course_by_id(self, course_id: str) -> dict | None:
        """Return a single course row as a dict, or None."""
        cursor = await self.db.execute(
            "SELECT * FROM courses WHERE id = ?", (course_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def search_courses(
        self,
        query: str | None = None,
        topic: str | None = None,
        level: str | None = None,
        instructor: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """Search courses from SQLite cache with flexible filtering."""
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row

            # Build query dynamically
            conditions = []
            params = []

            # Full-text search across title + short_desc + topic + instructor
            if query and query.strip():
                q = f"%{query.strip()}%"
                conditions.append(
                    "(title LIKE ? OR short_desc LIKE ? "
                    "OR topic LIKE ? OR instructor LIKE ?)"
                )
                params.extend([q, q, q, q])

            # Topic filter — match slug or display name
            if topic and topic.strip():
                t = f"%{topic.strip()}%"
                conditions.append("topic LIKE ?")
                params.append(t)

            # Level filter — case-insensitive
            if level and level.strip():
                conditions.append("LOWER(level) = LOWER(?)")
                params.append(level.strip())

            # Instructor filter
            if instructor and instructor.strip():
                i = f"%{instructor.strip()}%"
                conditions.append("instructor LIKE ?")
                params.append(i)

            # Build final SQL
            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            sql = f"""
                SELECT id, title, url, topic, level, instructor,
                       short_desc, fetched_at
                FROM courses
                {where}
                ORDER BY fetched_at DESC
                LIMIT ?
            """
            params.append(limit)

            logger.debug(f"search_courses SQL: {sql} | params: {params}")

            async with db.execute(sql, params) as cur:
                rows = await cur.fetchall()

            now = datetime.now(timezone.utc)
            results = []
            for row in rows:
                r = dict(row)
                try:
                    fetched = datetime.fromisoformat(r["fetched_at"])
                    age = (now - fetched).total_seconds() / 3600
                except Exception:
                    age = 0.0

                results.append({
                    "id":               r["id"],
                    "title":            r["title"] or "",
                    "url":              r["url"] or "",
                    "topic":            r["topic"] or "",
                    "level":            r["level"],
                    "instructor":       r["instructor"] or "",
                    "short_description": r.get("short_desc") or "",
                    "short_desc":       r.get("short_desc") or "",  # Fallback for recommend.py
                    "cache_age_hours":  round(age, 2),
                    "fetched_at":       r["fetched_at"],            # Fallback for recommend.py
                })

            return results

    async def get_all_topics(self) -> list[dict]:
        """Return all topics with their course counts."""
        cursor = await self.db.execute(
            "SELECT slug, display_name, course_count FROM topics ORDER BY display_name"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_cache_age_hours(self) -> float:
        """Return the age of the cache in hours, or infinity if never refreshed."""
        cursor = await self.db.execute(
            "SELECT value FROM meta WHERE key = 'last_refresh'"
        )
        row = await cursor.fetchone()
        if not row:
            return float("inf")
        last = datetime.fromisoformat(row["value"])
        delta = datetime.now(timezone.utc) - last
        return delta.total_seconds() / 3600

    async def get_status(self) -> dict:
        """Return overall cache status dict."""
        cursor = await self.db.execute("SELECT COUNT(*) as cnt FROM courses")
        row = await cursor.fetchone()
        total = row["cnt"] if row else 0

        cursor = await self.db.execute(
            "SELECT value FROM meta WHERE key = 'last_refresh'"
        )
        meta_row = await cursor.fetchone()
        last_refresh = meta_row["value"] if meta_row else "never"

        age = await self.get_cache_age_hours()

        topics = await self.get_all_topics()
        topic_slugs = [t["slug"] for t in topics]

        return {
            "total_courses": total,
            "last_refresh": last_refresh,
            "cache_age_hours": round(age, 2),
            "topics_covered": topic_slugs,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def is_stale(self, fetched_at: str) -> bool:
        """Check whether a fetched_at timestamp is older than the TTL."""
        fetched = datetime.fromisoformat(fetched_at)
        delta = datetime.now(timezone.utc) - fetched
        return delta.total_seconds() / 3600 > self._ttl_hours

    def cache_age_from_timestamp(self, fetched_at: str) -> float:
        """Return age in hours for a single timestamp."""
        fetched = datetime.fromisoformat(fetched_at)
        delta = datetime.now(timezone.utc) - fetched
        return round(delta.total_seconds() / 3600, 2)

    async def _rebuild_topics(self, now: str) -> None:
        """Recompute topic table from courses."""
        cursor = await self.db.execute(
            "SELECT topic, COUNT(*) as cnt FROM courses GROUP BY topic"
        )
        rows = await cursor.fetchall()
        await self.db.execute("DELETE FROM topics")
        for row in rows:
            slug = row["topic"] or "uncategorised"
            display = slug.replace("-", " ").title()
            await self.db.execute(
                "INSERT INTO topics (slug, display_name, course_count, updated_at)"
                " VALUES (?, ?, ?, ?)",
                (slug, display, row["cnt"], now),
            )
