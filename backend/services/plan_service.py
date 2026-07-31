"""
services/plan_service.py — Plan-panel data layer (project-level, no AI)

The plan panel's structured data (overview / equipment / schedule / notes /
location metadata / checklist state) lives in plan/plan.json, separate from
brief.json (the planning chat's raw output). Field names are snake_case; the
frontend maps to camelCase.

This module is deliberately LLM-free so every mutation is a pure function on the
JSON blob and can be unit-tested deterministically. The planning-chat agent wraps
these as tools; the frontend hits them via the coarse PUT /plan save.

Granularity rule (agreed with product): collections support only add / remove —
never a whole-segment rewrite — so a user's manual edits survive an AI turn. An
"edit" is expressed as remove + add. remove targets a stable `id` (assigned on
first load), never a name, so duplicate names stay unambiguous.
"""
import json
import uuid
from pathlib import Path

STORAGE_ROOT = Path(__file__).parent.parent / "storage" / "projects"

# Collections whose items carry a stable id, with the id prefix for readability.
_ID_COLLECTIONS = {
    "equipment": "eq",
    "schedule":  "sg",
    "notes":     "nt",
}


def _default_plan_data() -> dict:
    return {
        "theme": "",
        "shoot_date": "",
        "shoot_time": "",           # rough start time of day (e.g. "傍晚", "下午3点") → schedule 时间列
        "crew": {},                 # { photographers, cosers, logistics }
        "equipment": [],            # [ { id, name, required, desc, category } ]
        "schedule": [],             # [ { id, time, scene, shot_ids, content, duration, light, priority } ]
        "notes": [],                # [ { id, title, desc, phase, priority } ]
        "location_meta": {},        # { <scene>: { address } }
        "prepared": [],             # equipment names checked off
        "notes_done": [],           # note titles confirmed
    }


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _ensure_ids(data: dict) -> bool:
    """Assign an id to any item in an id-carrying collection that lacks one.
    Returns True if anything was changed (so the caller can persist)."""
    changed = False
    for coll, prefix in _ID_COLLECTIONS.items():
        for item in data.get(coll, []):
            if isinstance(item, dict) and not item.get("id"):
                item["id"] = _new_id(prefix)
                changed = True
    return changed


def _plan_path(project_id: str) -> Path:
    return STORAGE_ROOT / project_id / "plan" / "plan.json"


def _write(project_id: str, data: dict) -> None:
    plan_dir = STORAGE_ROOT / project_id / "plan"
    plan_dir.mkdir(exist_ok=True)
    _plan_path(project_id).write_text(json.dumps(data, ensure_ascii=False, indent=2))


def load_plan_data(project_id: str) -> dict:
    """Read plan/plan.json merged over defaults, so callers always get a
    consistent shape even for projects created before this feature. Backfills
    missing item ids and persists them, so ids stay stable from first read."""
    data = _default_plan_data()
    path = _plan_path(project_id)
    if path.exists():
        try:
            data.update(json.loads(path.read_text()))
        except (json.JSONDecodeError, OSError):
            pass
    if _ensure_ids(data) and path.exists():
        _write(project_id, data)
    return data


def save_plan_data(project_id: str, data: dict) -> dict:
    """Persist the whole plan blob (coarse save, used by the frontend PUT).
    Merges over defaults + drops unknown keys, then backfills ids. Returns the
    saved (id-normalized) blob."""
    merged = _default_plan_data()
    for k in merged:
        if k in data:
            merged[k] = data[k]
    _ensure_ids(merged)
    _write(project_id, merged)
    return merged


# ── Granular mutations (the AI-tool surface; add / remove only) ─────────────────

def update_overview(project_id: str, theme: str | None = None,
                    shoot_date: str | None = None, crew: dict | None = None,
                    shoot_time: str | None = None) -> dict:
    """Overwrite the scalar overview fields that are provided (theme / date / time /
    crew). Overview isn't a collection, so this is a set-in-place, not add/remove."""
    data = load_plan_data(project_id)
    if theme is not None:
        data["theme"] = theme
    if shoot_date is not None:
        data["shoot_date"] = shoot_date
    if shoot_time is not None:
        data["shoot_time"] = shoot_time
    if crew is not None:
        data["crew"] = {k: v for k, v in crew.items() if v is not None}
    _write(project_id, data)
    return {"theme": data["theme"], "shoot_date": data["shoot_date"],
            "shoot_time": data.get("shoot_time", ""), "crew": data["crew"]}


def add_equipment(project_id: str, name: str, required: bool = True,
                  desc: str | None = None, category: str | None = None) -> dict:
    name = (name or "").strip()
    if not name:
        raise ValueError("equipment name is required")
    data = load_plan_data(project_id)
    item = {"id": _new_id("eq"), "name": name, "required": bool(required),
            "desc": desc or "", "category": category or "misc"}
    data["equipment"].append(item)
    _write(project_id, data)
    return item


def remove_equipment(project_id: str, id: str) -> dict | None:
    """Remove an equipment item by id. Also drops its name from the prepared
    checklist. Returns the removed item, or None if the id wasn't found."""
    data = load_plan_data(project_id)
    removed = _pop_by_id(data["equipment"], id)
    if removed is None:
        return None
    data["prepared"] = [n for n in data["prepared"] if n != removed.get("name")]
    _write(project_id, data)
    return removed


def add_note(project_id: str, title: str, desc: str | None = None,
             phase: str = "pre", priority: str = "mid") -> dict:
    title = (title or "").strip()
    if not title:
        raise ValueError("note title is required")
    if phase not in ("pre", "onsite", "other"):
        phase = "pre"
    if priority not in ("high", "mid", "low"):
        priority = "mid"
    data = load_plan_data(project_id)
    item = {"id": _new_id("nt"), "title": title, "desc": desc or "",
            "phase": phase, "priority": priority}
    data["notes"].append(item)
    _write(project_id, data)
    return item


def remove_note(project_id: str, id: str) -> dict | None:
    data = load_plan_data(project_id)
    removed = _pop_by_id(data["notes"], id)
    if removed is None:
        return None
    data["notes_done"] = [t for t in data["notes_done"] if t != removed.get("title")]
    _write(project_id, data)
    return removed


def add_schedule_segment(project_id: str, scene: str, time: str | None = None,
                         content: str | None = None, duration: str | None = None,
                         light: str | None = None, priority: str | None = None,
                         shot_ids: list[str] | None = None) -> dict:
    scene = (scene or "").strip()
    if not scene:
        raise ValueError("schedule segment scene is required")
    if priority is not None and priority not in ("high", "mid", "low"):
        priority = None
    data = load_plan_data(project_id)
    item = {"id": _new_id("sg"), "time": time or "", "scene": scene,
            "shot_ids": shot_ids or [], "content": content or "",
            "duration": duration or "", "light": light or "", "priority": priority}
    data["schedule"].append(item)
    _write(project_id, data)
    return item


def remove_schedule_segment(project_id: str, id: str) -> dict | None:
    data = load_plan_data(project_id)
    removed = _pop_by_id(data["schedule"], id)
    if removed is None:
        return None
    _write(project_id, data)
    return removed


def _pop_by_id(items: list[dict], id: str) -> dict | None:
    for i, item in enumerate(items):
        if item.get("id") == id:
            return items.pop(i)
    return None
