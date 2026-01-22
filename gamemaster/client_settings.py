"""Per-client settings manager for the Gamemaster console.

This module provides a simple schema-based settings registry and per-client
storage saved to JSON in the mission directory.

Schema is kept under the special key "__schema__" inside the JSON file and
client values are stored under the client id keys.
"""

# TODO: Potentially this file could (should?) be moved to sbs_utils.

from __future__ import annotations

from typing import Any, Dict, Optional, List
from sbs_utils.fs import load_json_data, save_json_data, get_mission_dir_filename
import re

STORE_FILENAME = "client_settings.json"

# TODO: The schema system could be expanded to be used on a per-console basis, using different schemas for each console.
_SCHEMA_KEY = "__schema__"


def _load_store() -> Dict[str, Any]:
    data = load_json_data(get_mission_dir_filename(STORE_FILENAME))
    if data is None:
        return {}
    return data


def _save_store(data: Dict[str, Any]) -> None:
    save_json_data(get_mission_dir_filename(STORE_FILENAME), data)


def settings_get_schema() -> Dict[str, Dict[str, Any]]:
    """Return the settings schema (name -> metadata)."""
    store = _load_store()
    return store.get(_SCHEMA_KEY, {})


def settings_add_setting(name: str, stype: str = "string", description: str = "", default: Any = None, group: str = "General", choices: List[str] | str | None = None) -> Dict[str, Any]:
    """Register a new setting in the mission-wide schema.

    name (str): identifier (alphanumeric + underscore)
    stype (str): one of ('bool','int','float','string','select')
    description (str): human-readable description
    default (Any): default value (will be coerced for type)
    choices (str): list of choices for 'select' type

    Returns the created metadata dict.
    """
    if not re.match(r"^[A-Za-z0-9_]+$", name):
        raise ValueError("Setting name must be alphanumeric or underscore only")
    stype = stype.lower()
    if stype not in ("bool", "int", "float", "string", "select"):
        raise ValueError("Unsupported setting type")

    meta = {"type": stype, "default": _coerce_value(stype, default), "group": group, "description": description}
    if stype == "select":
        # choices may be provided as a comma-separated string or a list; normalize to string
        if isinstance(choices, list):
            choices_list = ",".join(choices)
        meta["choices"] = choices_list
    store = _load_store()
    schema = store.get(_SCHEMA_KEY, {})
    schema[name] = meta
    store[_SCHEMA_KEY] = schema
    # Ensure existing clients have at least default in their dicts (optional)
    for k, v in list(store.items()):
        if k == _SCHEMA_KEY:
            continue
        if name not in v:
            v[name] = meta["default"]
            store[k] = v
    _save_store(store)
    return meta


def settings_get_registered_names() -> List[str]:
    return list(settings_get_schema().keys())


def settings_get_client_settings(profile_id: str) -> Dict[str, Any]:
    """Return a dict of settings for a given profile_id, merged with defaults."""
    store = _load_store()
    schema = store.get(_SCHEMA_KEY, {})
    client = store.get(str(profile_id), {})
    result: Dict[str, Any] = {}
    for name, meta in schema.items():
        result[name] = client.get(name, meta.get("default"))
    return result


def settings_get_client_value(profile_id: str, name: str, default: Any = None) -> Any:
    client = _load_store().get(str(profile_id), {})
    if name in client:
        return client[name]
    schema = settings_get_schema()
    if name in schema:
        return schema[name].get("default", default)
    return default


def settings_set_client_value(profile_id: str, name: str, value: Any) -> None:
    """Set and persist a client setting (coerces type based on schema).
    
    If the value equals the default, the setting is removed from the profile to save space.
    """
    store = _load_store()
    schema = store.get(_SCHEMA_KEY, {})
    if name not in schema:
        raise KeyError("Setting not registered")
    stype = schema[name]["type"]
    coerced = _coerce_value(stype, value)
    default_val = schema[name].get("default")
    client = store.get(str(profile_id), {})
    if coerced == default_val:
        # Remove the setting if it's the default
        client.pop(name, None)
    else:
        client[name] = coerced
    store[str(profile_id)] = client
    _save_store(store)


def _coerce_value(stype: str, value: Any) -> Any:
    if value is None:
        return None
    stype = stype.lower()
    try:
        if stype == "bool":
            if isinstance(value, str):
                v = value.lower()
                return v in ("1", "true", "yes", "on", "active", "enabled")
            return bool(value)
        if stype == "int":
            return int(value)
        if stype == "float":
            return float(value)
        if stype == "string":
            return str(value)
        if stype == "select":
            return str(value)
    except Exception:
        # If coercion fails, fall back to the naive value
        return value
    return value


# Convenience functions for use from MAST
def settings_save_client(profile_id: str) -> None:
    """Explicit save (the set method already saves)."""
    # No-op because set saves immediately; present for API completeness
    return


# Pre-register a couple of helpful per-client settings (non-invasive defaults)
def _ensure_initial_schema():
    if not settings_get_schema():
        settings_add_setting("show_grid", "bool", True, group="Display")
        settings_add_setting("hud_scale", "float", 1.0, group="Display")
        settings_add_setting("nameplate", "string", "", group="UI")


_ensure_initial_schema()
