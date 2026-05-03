import sqlite3, json, os

db_path = os.getenv('CACHE_DB_PATH', 'data/courses.db')
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# How many courses?
cur.execute('SELECT COUNT(*) as n FROM courses')
print(f'Total courses in DB: {cur.fetchone()["n"]}')

# Show first 5 rows — all columns
cur.execute('SELECT id, title, topic, level, instructor, short_desc, fetched_at FROM courses LIMIT 5')
rows = cur.fetchall()
print('\n--- First 5 courses ---')
for r in rows:
    print(json.dumps(dict(r), indent=2))

# Check how many have empty title/topic/short_desc
cur.execute("SELECT COUNT(*) as n FROM courses WHERE title = '' OR title IS NULL")
print(f'\nCourses with empty title: {cur.fetchone()["n"]}')

cur.execute("SELECT COUNT(*) as n FROM courses WHERE topic = '' OR topic IS NULL")
print(f'Courses with empty topic: {cur.fetchone()["n"]}')

cur.execute("SELECT COUNT(*) as n FROM courses WHERE short_desc = '' OR short_desc IS NULL")
print(f'Courses with empty short_desc: {cur.fetchone()["n"]}')

# Try the exact SQL that search_courses runs
cur.execute("""
    SELECT id, title, topic, level, instructor, short_desc
    FROM courses
    WHERE title LIKE '%AI%' OR short_desc LIKE '%AI%'
    LIMIT 5
""")
results = cur.fetchall()
print(f'\nDirect SQL search for AI: {len(results)} results')
for r in results:
    print(' -', dict(r).get('title', '?'))

conn.close()
