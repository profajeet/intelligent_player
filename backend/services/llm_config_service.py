"""
Persists LLM provider configuration in the database and returns
the active client on demand.

One config is marked `is_active = 1` at a time.
All other configs are stored but inactive.
"""

import json
import aiosqlite
from services.storage_service import DB_PATH
from services.llm.registry import build_client, LLMError
from services.llm.base import BaseLLMClient


# ── DB init (called from storage_service.init_db) ────────────────────────────

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS llm_configs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,           -- human label, e.g. "My GPT-4o"
    provider    TEXT NOT NULL,           -- openai | anthropic | gemini | ollama | vllm
    model       TEXT NOT NULL,
    api_key     TEXT,                    -- NULL for local providers (ollama, vllm)
    base_url    TEXT,                    -- custom endpoint; NULL for cloud providers
    extra       TEXT DEFAULT '{}',       -- JSON blob for any future provider-specific fields
    is_active   INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


async def ensure_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_TABLE_SQL)
        await db.commit()


# ── CRUD ──────────────────────────────────────────────────────────────────────

async def create_config(
    name: str,
    provider: str,
    model: str,
    api_key: str | None = None,
    base_url: str | None = None,
    extra: dict | None = None,
    set_active: bool = True,
) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        if set_active:
            await db.execute("UPDATE llm_configs SET is_active = 0")

        cursor = await db.execute(
            """
            INSERT INTO llm_configs
                (name, provider, model, api_key, base_url, extra, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (name, provider.lower(), model, api_key, base_url,
             json.dumps(extra or {}), 1 if set_active else 0),
        )
        await db.commit()

        async with db.execute(
            "SELECT * FROM llm_configs WHERE id = ?", (cursor.lastrowid,)
        ) as cur:
            row = await cur.fetchone()
            return _safe_row(row)


async def list_configs() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM llm_configs ORDER BY created_at DESC"
        ) as cur:
            rows = await cur.fetchall()
            return [_safe_row(r) for r in rows]


async def get_config(config_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM llm_configs WHERE id = ?", (config_id,)
        ) as cur:
            row = await cur.fetchone()
            return _safe_row(row) if row else None


async def set_active_config(config_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("UPDATE llm_configs SET is_active = 0")
        await db.execute(
            "UPDATE llm_configs SET is_active = 1, updated_at = datetime('now') WHERE id = ?",
            (config_id,),
        )
        await db.commit()
        async with db.execute(
            "SELECT * FROM llm_configs WHERE id = ?", (config_id,)
        ) as cur:
            row = await cur.fetchone()
            return _safe_row(row) if row else None


async def update_config(config_id: int, **fields) -> dict | None:
    allowed = {"name", "model", "api_key", "base_url", "extra"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return await get_config(config_id)

    if "extra" in updates:
        updates["extra"] = json.dumps(updates["extra"])

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values     = list(updates.values()) + [config_id]

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            f"UPDATE llm_configs SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
            values,
        )
        await db.commit()
        async with db.execute(
            "SELECT * FROM llm_configs WHERE id = ?", (config_id,)
        ) as cur:
            row = await cur.fetchone()
            return _safe_row(row) if row else None


async def delete_config(config_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM llm_configs WHERE id = ?", (config_id,)
        )
        await db.commit()
        return cursor.rowcount > 0


# ── Active client helper ──────────────────────────────────────────────────────

async def get_active_config() -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM llm_configs WHERE is_active = 1 LIMIT 1"
        ) as cur:
            row = await cur.fetchone()
            return _safe_row(row) if row else None


async def get_active_client() -> BaseLLMClient:
    """
    Returns a ready-to-use LLM client using the currently active config.
    Raises LLMError if no active config is found.
    """
    cfg = await get_active_config()
    if not cfg:
        raise LLMError(
            "none",
            "No active LLM configuration found. "
            "POST /llm-config to register one.",
            status_code=503,
        )
    extra = json.loads(cfg.get("extra") or "{}")
    merged = {**cfg, **extra}
    return build_client(cfg["provider"], merged)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_row(row) -> dict:
    """Convert a Row to dict, masking the api_key."""
    d = dict(row)
    if d.get("api_key"):
        d["api_key"] = d["api_key"][:8] + "••••••••"
    if d.get("extra"):
        try:
            d["extra"] = json.loads(d["extra"])
        except Exception:
            d["extra"] = {}
    return d
