"""
Dynamic Configuration Service.

Provides runtime-configurable settings by reading overrides from the
`system_configs` database table.  If no DB override exists for a given key,
falls back to the static default in ``utils/config.py``.

Usage
-----
    from services.config_service import get_dynamic_config, set_dynamic_config

    threshold = await get_dynamic_config(db, "FACE_MATCH_THRESHOLD", 0.7)
    await set_dynamic_config(db, "FACE_MATCH_THRESHOLD", 0.8)
"""
import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.sql_models import SystemConfig
from utils import config as static_config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Registry of configurable keys with metadata (for the admin UI)
# ---------------------------------------------------------------------------
# Each entry: key -> { default, type, description }
#   - 'default' is the attribute name on the static config module
#   - 'type' is the Python type to cast the DB string to
CONFIGURABLE_KEYS: Dict[str, dict] = {
    # Face matching
    "FACE_MATCH_THRESHOLD": {
        "default_attr": "FACE_MATCH_THRESHOLD",
        "type": "float",
        "description": "Face match similarity threshold (0.0-1.0)",
    },
    # Liveness detection
    "LIVENESS_ENABLED": {
        "default_attr": "LIVENESS_ENABLED",
        "type": "bool",
        "description": "Enable or disable liveness checks",
    },
    "LIVENESS_THRESHOLD": {
        "default_attr": "LIVENESS_THRESHOLD",
        "type": "float",
        "description": "Overall liveness confidence threshold (0.0-1.0)",
    },
    # Face quality
    "FACE_QUALITY_ENABLED": {
        "default_attr": "FACE_QUALITY_ENABLED",
        "type": "bool",
        "description": "Enable face quality checks",
    },
    "FACE_QUALITY_MIN_CONFIDENCE": {
        "default_attr": "FACE_QUALITY_MIN_CONFIDENCE",
        "type": "float",
        "description": "Minimum face detection confidence (0.0-1.0)",
    },
    # OCR
    "OCR_CONFIDENCE_THRESHOLD": {
        "default_attr": "OCR_CONFIDENCE_THRESHOLD",
        "type": "float",
        "description": "OCR confidence threshold (0.0-1.0)",
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _cast(value_str: str, type_name: str) -> Any:
    """Cast a string value from the DB to the appropriate Python type."""
    if type_name == "float":
        return float(value_str)
    if type_name == "int":
        return int(value_str)
    if type_name == "bool":
        return value_str.lower() in ("true", "1", "yes")
    if type_name == "json":
        return json.loads(value_str)
    return value_str  # str


def _get_static_default(key: str) -> Any:
    """Retrieve the default value from ``utils/config.py``."""
    meta = CONFIGURABLE_KEYS.get(key)
    if meta and hasattr(static_config, meta["default_attr"]):
        return getattr(static_config, meta["default_attr"])
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
async def get_dynamic_config(
    db: AsyncSession, key: str, default: Any = None
) -> Any:
    """
    Get a config value.  DB override wins; otherwise falls back to *default*
    (which itself defaults to the static ``config.py`` value).
    """
    if default is None:
        default = _get_static_default(key)

    result = await db.execute(
        select(SystemConfig).where(SystemConfig.key == key)
    )
    row = result.scalar_one_or_none()

    if row is None:
        return default

    meta = CONFIGURABLE_KEYS.get(key, {})
    type_name = meta.get("type", "str")
    try:
        return _cast(row.value, type_name)
    except (ValueError, json.JSONDecodeError):
        logger.warning("Bad DB value for %s (%r); using default", key, row.value)
        return default


async def set_dynamic_config(
    db: AsyncSession,
    key: str,
    value: Any,
    description: Optional[str] = None,
) -> SystemConfig:
    """Create or update a config override in the database."""
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.key == key)
    )
    row = result.scalar_one_or_none()

    str_value = str(value)

    if row:
        row.value = str_value
        if description is not None:
            row.description = description
    else:
        desc = description or CONFIGURABLE_KEYS.get(key, {}).get("description", "")
        row = SystemConfig(key=key, value=str_value, description=desc)
        db.add(row)

    await db.flush()
    return row


async def get_all_configs(db: AsyncSession) -> List[dict]:
    """Return every configurable key with its effective (DB or default) value."""
    # Fetch all DB overrides in one query
    result = await db.execute(select(SystemConfig))
    db_rows = {r.key: r for r in result.scalars().all()}

    configs = []
    for key, meta in CONFIGURABLE_KEYS.items():
        default = _get_static_default(key)
        db_row = db_rows.get(key)

        if db_row:
            type_name = meta.get("type", "str")
            try:
                effective = _cast(db_row.value, type_name)
            except (ValueError, json.JSONDecodeError):
                effective = default
            source = "database"
        else:
            effective = default
            source = "default"

        configs.append({
            "key": key,
            "value": effective,
            "default_value": default,
            "source": source,
            "type": meta.get("type", "str"),
            "description": meta.get("description", ""),
        })

    return configs


async def delete_dynamic_config(db: AsyncSession, key: str) -> bool:
    """Remove a DB override so the key reverts to its static default."""
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.key == key)
    )
    row = result.scalar_one_or_none()
    if row:
        await db.delete(row)
        await db.flush()
        return True
    return False
