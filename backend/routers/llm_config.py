"""
/llm-config  — manage and select LLM provider configurations.

POST   /llm-config              Register a new config (and optionally set it active)
GET    /llm-config              List all saved configs
GET    /llm-config/active       Get the currently active config
GET    /llm-config/{id}         Get one config by ID
PUT    /llm-config/{id}/activate  Switch the active config
PATCH  /llm-config/{id}         Update fields on an existing config
DELETE /llm-config/{id}         Remove a config

POST   /llm-config/test         Send a test prompt through the active (or specified) config
POST   /llm-config/test/stream  Same, but stream the response via SSE
"""

import json
from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from models.schemas import (
    LLMConfigCreate, LLMConfigUpdate, LLMConfigResponse, LLMTestRequest
)
from services.llm_config_service import (
    create_config, list_configs, get_config,
    set_active_config, update_config, delete_config,
    get_active_config, get_active_client,
    ensure_table,
)
from services.llm.registry import build_client
from services.llm.base import LLMError

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_response(row: dict | None) -> LLMConfigResponse:
    if not row:
        raise HTTPException(status_code=404, detail="Config not found")
    return LLMConfigResponse(**{k: row.get(k) for k in LLMConfigResponse.model_fields})


# ── CRUD ──────────────────────────────────────────────────────────────────────

@router.post("", response_model=LLMConfigResponse, status_code=201)
async def register_config(body: LLMConfigCreate):
    """
    Register a new LLM provider configuration.

    - For **cloud providers** (openai, anthropic, gemini) `api_key` is required.
    - For **local providers** (ollama, vllm) `api_key` is optional; `base_url` defaults
      to localhost if omitted.
    - Set `set_active: true` (default) to immediately start using this config for
      all AI features (summary, questions).
    """
    await ensure_table()

    # Validate: cloud providers need an api_key
    cloud = {"openai", "anthropic", "gemini"}
    if body.provider.lower() in cloud and not body.api_key:
        raise HTTPException(
            status_code=422,
            detail=f"api_key is required for provider '{body.provider}'",
        )

    # Smoke-test the config before saving (fast fail)
    try:
        build_client(body.provider, body.model_dump())
    except ImportError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except LLMError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))

    row = await create_config(
        name=body.name,
        provider=body.provider,
        model=body.model,
        api_key=body.api_key,
        base_url=body.base_url,
        extra=body.extra,
        set_active=body.set_active,
    )
    return _to_response(row)


@router.get("", response_model=list[LLMConfigResponse])
async def get_all_configs():
    """List all saved LLM configurations (api_key is masked)."""
    await ensure_table()
    rows = await list_configs()
    return [_to_response(r) for r in rows]


@router.get("/active", response_model=LLMConfigResponse)
async def active_config():
    """Return the currently active LLM configuration."""
    await ensure_table()
    row = await get_active_config()
    if not row:
        raise HTTPException(
            status_code=404,
            detail="No active LLM config. POST /llm-config to register one.",
        )
    return _to_response(row)


@router.get("/{config_id}", response_model=LLMConfigResponse)
async def get_one_config(config_id: int):
    await ensure_table()
    return _to_response(await get_config(config_id))


@router.put("/{config_id}/activate", response_model=LLMConfigResponse)
async def activate_config(config_id: int):
    """Switch the active LLM configuration."""
    await ensure_table()
    row = await set_active_config(config_id)
    if not row:
        raise HTTPException(status_code=404, detail="Config not found")
    return _to_response(row)


@router.patch("/{config_id}", response_model=LLMConfigResponse)
async def patch_config(config_id: int, body: LLMConfigUpdate):
    """Update specific fields on a saved configuration."""
    await ensure_table()
    row = await update_config(config_id, **body.model_dump(exclude_none=True))
    return _to_response(row)


@router.delete("/{config_id}", status_code=204)
async def remove_config(config_id: int):
    """Delete a configuration. Cannot delete the active config."""
    await ensure_table()
    cfg = await get_config(config_id)
    if not cfg:
        raise HTTPException(status_code=404, detail="Config not found")
    if cfg.get("is_active"):
        raise HTTPException(
            status_code=409,
            detail="Cannot delete the active config. Activate another config first.",
        )
    deleted = await delete_config(config_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Config not found")


# ── Test endpoints ─────────────────────────────────────────────────────────────

@router.post("/test")
async def test_config(body: LLMTestRequest):
    """
    Send a test prompt through a config and return the full response.
    Uses the active config if `config_id` is omitted.
    """
    await ensure_table()
    try:
        if body.config_id is not None:
            cfg = await get_config(body.config_id)
            if not cfg:
                raise HTTPException(status_code=404, detail="Config not found")
            extra  = cfg.get("extra") or {}
            if isinstance(extra, str):
                extra = json.loads(extra)
            client = build_client(cfg["provider"], {**cfg, **extra})
        else:
            client = await get_active_client()

        result = await client.complete(
            system="You are a helpful assistant.",
            user=body.prompt,
            max_tokens=256,
        )
        return {"response": result}

    except LLMError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test/stream")
async def test_config_stream(body: LLMTestRequest):
    """
    Stream a test prompt response via Server-Sent Events.
    Uses the active config if `config_id` is omitted.
    """
    await ensure_table()

    async def event_generator():
        try:
            if body.config_id is not None:
                cfg = await get_config(body.config_id)
                if not cfg:
                    yield {"data": json.dumps({"error": "Config not found"})}
                    return
                extra  = cfg.get("extra") or {}
                if isinstance(extra, str):
                    extra = json.loads(extra)
                client = build_client(cfg["provider"], {**cfg, **extra})
            else:
                client = await get_active_client()

            async for chunk in client.stream(
                system="You are a helpful assistant.",
                user=body.prompt,
                max_tokens=256,
            ):
                yield {"data": chunk}

            yield {"data": "[DONE]"}

        except LLMError as e:
            yield {"data": json.dumps({"error": str(e)})}
        except Exception as e:
            yield {"data": json.dumps({"error": str(e)})}

    return EventSourceResponse(event_generator())
