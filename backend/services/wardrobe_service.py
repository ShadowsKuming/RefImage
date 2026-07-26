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


def generate_wardrobe(project_id: str) -> dict:
    """LLM-generate an initial 服装/道具 list from the character's appearance
    (visual_spec already describes top/bottom/shoes/accessory/colors) + profile,
    then save. Replaces the stored list. Returns the fresh wardrobe.

    Structured output via a passthrough submit_wardrobe tool (same reliable
    pattern as moments). Cosplay-oriented: costume = what the coser wears, props =
    signature handheld items the character is known for. No web_search — the
    appearance spec is the source, so no fabrication risk."""
    from services import project_service
    from tools.llm import call_agent

    proj = project_service.get_project(project_id)  # raises FileNotFoundError
    name = proj.get("character") or ""
    series = proj.get("series") or ""
    vs = proj.get("visual_spec") or {}
    appearance = vs.get("zh") if isinstance(vs, dict) else str(vs)
    cb = (proj.get("character_data") or {}).get("characterBackground") or {}
    role = cb.get("role", "")

    tools = [{
        "name": "submit_wardrobe",
        "description": "提交整理好的服装 + 道具清单。",
        "input_schema": {"type": "object", "properties": {
            "costume": {
                "type": "array",
                "items": {"type": "object", "properties": {
                    "name":      {"type": "string", "description": "服装单品名,如 黑长直假发 / 樱丘高中校服上衣"},
                    "category":  {"type": "string", "enum": list(COSTUME_CATEGORIES),
                                  "description": "分类:假发wig/上衣top/下装bottom/鞋袜shoes/配饰accessory/其他misc"},
                    "note":      {"type": "string", "description": "cos 要点(材质/颜色/细节),简短"},
                    "essential": {"type": "boolean", "description": "必备(核心造型 true)还是备用(false)"},
                }, "required": ["name", "category"]},
            },
            "props": {
                "type": "array",
                "items": {"type": "object", "properties": {
                    "name":      {"type": "string", "description": "道具名,如 左手贝斯"},
                    "note":      {"type": "string", "description": "要点,简短"},
                    "essential": {"type": "boolean"},
                }, "required": ["name"]},
            },
        }, "required": ["costume", "props"]},
    }]

    system = (
        f"你是资深 cosplay 造型师。根据角色的外貌描述和资料,整理一份还原这个角色所需的"
        f"『服装』(穿戴类:假发/上衣/下装/鞋袜/配饰)和『道具』(角色标志性手持物/乐器等)清单。"
        f"目标角色:《{series}》的 {name}{('(' + role + ')') if role else ''}。"
        f"\n外貌描述:\n{appearance}\n"
        f"依据外貌把每个部位拆成具体单品(有假发/上衣/下装/鞋袜/配饰就分别列),"
        f"道具只列这个角色公认的标志性物件(没有就留空数组)。整理完调用 submit_wardrobe 提交。"
    )

    result = None
    for _ in range(2):
        res = call_agent(
            messages=[{"role": "user", "content": f"请为 {name} 整理服装道具清单,然后调用 submit_wardrobe 提交。"}],
            system=system, tools=tools, tool_executor={}, max_turns=3, max_tokens=1500,
        )
        call = next((c for c in res.get("tool_calls", []) if c.get("name") == "submit_wardrobe"), None)
        if call and isinstance(call.get("input"), dict):
            result = call["input"]
            break
    if not result:
        raise RuntimeError("服装道具生成失败(未能获取结果),请重试")

    data = _default_wardrobe()
    for c in (result.get("costume") or []):
        n = (c.get("name") or "").strip()
        if not n:
            continue
        cat = c.get("category") if c.get("category") in COSTUME_CATEGORIES else "misc"
        data["costume"].append({"id": _new_id("cs"), "name": n, "category": cat,
                                "note": (c.get("note") or "").strip(), "essential": bool(c.get("essential", True))})
    for p in (result.get("props") or []):
        n = (p.get("name") or "").strip()
        if not n:
            continue
        data["props"].append({"id": _new_id("pr"), "name": n,
                              "note": (p.get("note") or "").strip(), "essential": bool(p.get("essential", True))})
    _write(project_id, data)
    return load_wardrobe(project_id)
