"""
services/location_service.py — Project-level 取景地 pool

Real-world shooting locations are a SHARED project resource, not a per-shot guess.
If every shot invented its own locations, 10 shots → 30 unrelated places and the
project can't be planned. So locations live at the project level: a shot reuses an
existing one when it fits, and only when none fits does the user pick/add a new one
(which then joins the pool for later shots to reuse). This is what lets the plan
group shots by location.

Storage: plan/locations.json — { locations: [ { id, name, indoor_outdoor, note } ] }
"""
import json
import uuid
from pathlib import Path

STORAGE_ROOT = Path(__file__).parent.parent / "storage" / "projects"


def _path(project_id: str) -> Path:
    return STORAGE_ROOT / project_id / "plan" / "locations.json"


def load(project_id: str) -> dict:
    p = _path(project_id)
    if p.exists():
        try:
            data = json.loads(p.read_text())
            if isinstance(data, dict) and isinstance(data.get("locations"), list):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {"locations": []}


def list_locations(project_id: str) -> list[dict]:
    return load(project_id).get("locations", [])


def _write(project_id: str, data: dict) -> None:
    p = _path(project_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def add_location(project_id: str, name: str, indoor_outdoor: str = "均可", note: str = "") -> dict:
    """Add a location to the pool, or return the existing one if the name already
    exists (dedupe by name so shots converge on shared locations)."""
    name = (name or "").strip()
    if not name:
        raise ValueError("location name required")
    data = load(project_id)
    for loc in data["locations"]:
        if loc["name"] == name:
            return loc
    entry = {"id": "loc_" + uuid.uuid4().hex[:8], "name": name,
             "indoor_outdoor": indoor_outdoor or "均可", "note": note or ""}
    data["locations"].append(entry)
    _write(project_id, data)
    return entry
