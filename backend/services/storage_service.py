import aiosqlite
import os

DB_PATH = os.getenv("DB_PATH", "storage/study_tool.db")


async def init_db():
    os.makedirs("storage", exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS notes (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id   TEXT NOT NULL,
                content    TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS transcripts (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id   TEXT NOT NULL UNIQUE,
                title      TEXT,
                language   TEXT,
                source     TEXT,
                full_text  TEXT,
                segments   TEXT,   -- JSON blob
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS screenshots (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id         TEXT NOT NULL,
                filename         TEXT NOT NULL,
                video_timestamp  REAL,
                created_at       TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """)
        await db.commit()


# ── Notes ───────────────────────────────────────────────────────────────────

async def get_note(video_id: str) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT content FROM notes WHERE video_id = ?", (video_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else ""


async def save_note(video_id: str, content: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO notes (video_id, content, updated_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(video_id) DO UPDATE
              SET content = excluded.content, updated_at = excluded.updated_at
        """, (video_id, content))
        await db.commit()


# ── Transcripts ──────────────────────────────────────────────────────────────

async def get_transcript(video_id: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM transcripts WHERE video_id = ?", (video_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def save_transcript(video_id: str, title: str, language: str,
                           source: str, full_text: str, segments_json: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO transcripts (video_id, title, language, source, full_text, segments)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(video_id) DO UPDATE
              SET title=excluded.title, language=excluded.language,
                  source=excluded.source, full_text=excluded.full_text,
                  segments=excluded.segments
        """, (video_id, title, language, source, full_text, segments_json))
        await db.commit()


# ── Screenshots ──────────────────────────────────────────────────────────────

async def save_screenshot_record(video_id: str, filename: str, video_timestamp: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO screenshots (video_id, filename, video_timestamp) VALUES (?, ?, ?)",
            (video_id, filename, video_timestamp)
        )
        await db.commit()
