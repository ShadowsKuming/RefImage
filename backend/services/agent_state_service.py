"""
services/agent_state_service.py — per-project conversational state for the
state-machine planning agent (agents/planning_flow.py).

The engine owns "which state we're in / what's been covered / the pending
question"; this module just persists that so a page reload resumes mid-flow.
Lives at plan/agent_state.json, next to chat_history.json.
"""
import json
from pathlib import Path

STORAGE_ROOT = Path(__file__).parent.parent / "storage" / "projects"


def _path(project_id: str) -> Path:
    return STORAGE_ROOT / project_id / "plan" / "agent_state.json"


def _default() -> dict:
    return {"state": None, "covered": [], "last_reply": "", "last_options": []}


def load_state(project_id: str) -> dict:
    p = _path(project_id)
    if p.exists():
        try:
            data = json.loads(p.read_text())
            if isinstance(data, dict):
                return {**_default(), **data}
        except (json.JSONDecodeError, OSError):
            pass
    return _default()


def save_state(project_id: str, st: dict) -> None:
    p = _path(project_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(st, ensure_ascii=False, indent=2))


def reset_state(project_id: str) -> None:
    _path(project_id).unlink(missing_ok=True)
