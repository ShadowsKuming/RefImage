"""
services/wardrobe_service.py — Costume & props data layer (character-level)

服装/道具 are what the coser wears / carries — they hang off the character, so
the UI lives in the left 设定 panel, not the right plan panel. But they're
shoot-related (unlike the step-1 context extraction, which is frozen), so the
storage sits under plan/ as its own file: plan/wardrobe.json (separate from
plan.json).

Like plan_service, this is LLM-free: pure functions on the JSON blob, unit-
testable, and shaped so granular AI-tool mutations can wrap it later. Items in
both collections carry a stable id (cs_ / pr_), assigned on first read.
"""
import json
import uuid
from pathlib import Path

STORAGE_ROOT = Path(__file__).parent.parent / "storage" / "projects"

_ID_COLLECTIONS = {"costume": "cs", "props": "pr"}

# costume categories (used for grouping in the UI). props are a flat list.
COSTUME_CATEGORIES = ("wig", "top", "bottom", "shoes", "accessory", "misc")


def _default_wardrobe() -> dict:
    # Pure reference (what the character wears / carries) — no prepared/progress
    # tracking; that belongs to the right-side plan (execution), not 设定.
    return {
        "costume": [],   # [ { id, name, category, note } ]
        "props": [],     # [ { id, name, note } ]
    }


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _ensure_ids(data: dict) -> bool:
    changed = False
    for coll, prefix in _ID_COLLECTIONS.items():
        for item in data.get(coll, []):
            if isinstance(item, dict) and not item.get("id"):
                item["id"] = _new_id(prefix)
                changed = True
    return changed


def _path(project_id: str) -> Path:
    return STORAGE_ROOT / project_id / "plan" / "wardrobe.json"


def _write(project_id: str, data: dict) -> None:
    plan_dir = STORAGE_ROOT / project_id / "plan"
    plan_dir.mkdir(exist_ok=True)
    _path(project_id).write_text(json.dumps(data, ensure_ascii=False, indent=2))


def load_wardrobe(project_id: str) -> dict:
    """Read plan/wardrobe.json merged over defaults; backfill+persist item ids."""
    data = _default_wardrobe()
    path = _path(project_id)
    if path.exists():
        try:
            data.update(json.loads(path.read_text()))
        except (json.JSONDecodeError, OSError):
            pass
    if _ensure_ids(data) and path.exists():
        _write(project_id, data)
    return data


def save_wardrobe(project_id: str, data: dict) -> dict:
    """Coarse save (frontend PUT). Merge over defaults, drop unknown keys,
    backfill ids. Returns the saved blob."""
    merged = _default_wardrobe()
    for k in merged:
        if k in data:
            merged[k] = data[k]
    _ensure_ids(merged)
    _write(project_id, merged)
    return merged
