"""
Admin Configuration API – lets the frontend read & write runtime config overrides.

Routes
------
GET  /admin/config              – list all configurable keys + effective values
POST /admin/config              – create or update one config key
DELETE /admin/config/{key}      – revert a key to its static default
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from services.db import get_db
from services.config_service import (
    get_all_configs,
    set_dynamic_config,
    delete_dynamic_config,
    CONFIGURABLE_KEYS,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/config", tags=["Admin Config"])


# ── request / response models ────────────────────────────────────────────
class ConfigUpdateRequest(BaseModel):
    key: str
    value: str  # always sent as string; backend casts per type
    description: Optional[str] = None


class ConfigDeleteResponse(BaseModel):
    key: str
    reverted: bool
    message: str


# ── endpoints ────────────────────────────────────────────────────────────
@router.get("")
async def list_configs(db: AsyncSession = Depends(get_db)):
    """Return all configurable keys with their effective values."""
    configs = await get_all_configs(db)
    return {"configs": configs, "total": len(configs)}


@router.post("")
async def update_config(
    body: ConfigUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create or update a configuration override."""
    if body.key not in CONFIGURABLE_KEYS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown config key: '{body.key}'. "
                   f"Valid keys: {list(CONFIGURABLE_KEYS.keys())}",
        )

    row = await set_dynamic_config(db, body.key, body.value, body.description)
    logger.info("Config updated: %s = %s", body.key, body.value)
    return {
        "key": row.key,
        "value": row.value,
        "message": f"Config '{body.key}' updated successfully",
    }


@router.delete("/{key}")
async def revert_config(
    key: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a DB override so the key reverts to its static default."""
    if key not in CONFIGURABLE_KEYS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown config key: '{key}'.",
        )

    reverted = await delete_dynamic_config(db, key)
    if reverted:
        return ConfigDeleteResponse(
            key=key,
            reverted=True,
            message=f"Config '{key}' reverted to default",
        )
    return ConfigDeleteResponse(
        key=key,
        reverted=False,
        message=f"Config '{key}' was already using the default value",
    )
