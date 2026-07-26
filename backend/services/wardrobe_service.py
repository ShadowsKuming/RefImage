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
    # essential: 必备(true) vs 备用(false). image: user-uploaded thumbnail URL.
    return {
        "costume": [],   # [ { id, name, category, note, essential, image? } ]
        "props": [],     # [ { id, name, note, essential, image? } ]
    }


def _item_image_url(project_id: str, item_id: str) -> str | None:
    d = STORAGE_ROOT / project_id / "plan" / "wardrobe_images"
    for ext in ("png", "jpg", "webp"):
        p = d / f"{item_id}.{ext}"
        if p.exists():
            return f"/projects/{project_id}/wardrobe/items/{item_id}/image?v={int(p.stat().st_mtime)}"
    return None


def item_image_path(project_id: str, item_id: str) -> Path | None:
    d = STORAGE_ROOT / project_id / "plan" / "wardrobe_images"
    for ext in ("png", "jpg", "webp"):
        p = d / f"{item_id}.{ext}"
        if p.exists():
            return p
    return None


_IMG_EXT = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}


def save_item_image(project_id: str, item_id: str, data: bytes, filename: str, content_type: str = "") -> str:
    """Store a thumbnail for one wardrobe item. Returns its serving URL."""
    ext = _IMG_EXT.get(content_type.split(";")[0].strip())
    if not ext:
        tail = filename.rsplit(".", 1)[-1].lower() if "." in filename else "png"
        ext = tail if tail in _IMG_EXT.values() else "png"
    d = STORAGE_ROOT / project_id / "plan" / "wardrobe_images"
    d.mkdir(parents=True, exist_ok=True)
    for old in d.glob(f"{item_id}.*"):
        old.unlink(missing_ok=True)
    (d / f"{item_id}.{ext}").write_bytes(data)
    return _item_image_url(project_id, item_id) or ""


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
    # decorate each item with its stored image URL (not persisted in the json —
    # derived from the wardrobe_images/ dir) + default essential=True
    for coll in _ID_COLLECTIONS:
        for item in data.get(coll, []):
            if not isinstance(item, dict):
                continue
            item.setdefault("essential", True)
            item["image"] = _item_image_url(project_id, item.get("id", ""))
    return data


def save_wardrobe(project_id: str, data: dict) -> dict:
    """Coarse save (frontend PUT). Merge over defaults, drop unknown keys,
    backfill ids. Returns the saved blob."""
    merged = _default_wardrobe()
    for k in merged:
        if k in data:
            merged[k] = data[k]
    _strip_images(merged)  # `image` is derived from wardrobe_images/, not stored
    _ensure_ids(merged)
    _write(project_id, merged)
    return load_wardrobe(project_id)


def _strip_images(data: dict) -> None:
    for coll in _ID_COLLECTIONS:
        for item in data.get(coll, []):
            if isinstance(item, dict):
                item.pop("image", None)


# ── Granular mutations (the AI-tool surface; add / remove only) ─────────────────
# Same discipline as plan_service: stable ids, add/remove only, no wholesale
# rewrite, so a user's manual edits survive an AI turn.

def add_costume(project_id: str, name: str, category: str | None = None,
                note: str | None = None, essential: bool = True) -> dict:
    name = (name or "").strip()
    if not name:
        raise ValueError("costume name is required")
    if category not in COSTUME_CATEGORIES:
        category = "misc"
    data = load_wardrobe(project_id)
    _strip_images(data)
    item = {"id": _new_id("cs"), "name": name, "category": category,
            "note": note or "", "essential": bool(essential)}
    data["costume"].append(item)
    _write(project_id, data)
    return item


def add_prop(project_id: str, name: str, note: str | None = None,
             essential: bool = True) -> dict:
    name = (name or "").strip()
    if not name:
        raise ValueError("prop name is required")
    data = load_wardrobe(project_id)
    _strip_images(data)
    item = {"id": _new_id("pr"), "name": name, "note": note or "", "essential": bool(essential)}
    data["props"].append(item)
    _write(project_id, data)
    return item


def remove_item(project_id: str, id: str) -> dict | None:
    """Remove a costume or prop by id. Returns the removed item, or None."""
    data = load_wardrobe(project_id)
    _strip_images(data)
    for coll in _ID_COLLECTIONS:
        for i, item in enumerate(data[coll]):
            if item.get("id") == id:
                removed = data[coll].pop(i)
                _write(project_id, data)
                return removed
    return None
