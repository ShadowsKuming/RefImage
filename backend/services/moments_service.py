"""
services/moments_service.py — Character 名场面 (signature scenes) as canon reference

名场面 are a character's most iconic, fan-recognized scenes — richer than the
generic iconic_moments extracted in step 1. They're character-level canon (设定),
NOT shoot instructions: each has { title, source (rough episode/where),
description (the event + timing/context) } — no shoot tips (those belong to the
shot editor). They give later shots inspiration and give the user a thinking
reference.

Generated via LLM + web_search (verified, multi-language), then editable/
regeneratable. Stored per character at context/moments/{cid}.json (character-
scoped, alongside avatars; ready for multiple characters).

generate_moments() uses the LLM layer, so this module isn't part of the offline
unit-test suite; load/save are pure and could be.
"""
import json
import uuid
from pathlib import Path

STORAGE_ROOT = Path(__file__).parent.parent / "storage" / "projects"


def _dir(project_id: str) -> Path:
    return STORAGE_ROOT / project_id / "context" / "moments"


def _path(project_id: str, cid: str) -> Path:
    return _dir(project_id) / f"{cid}.json"


def _new_id() -> str:
    return f"mo_{uuid.uuid4().hex[:8]}"


def _ensure_ids(moments: list[dict]) -> bool:
    changed = False
    for m in moments:
        if isinstance(m, dict) and not m.get("id"):
            m["id"] = _new_id()
            changed = True
    return changed


def load_moments(project_id: str, cid: str) -> dict:
    """Return { moments: [ { id, title, source, description } ] }; backfill ids."""
    data = {"moments": []}
    p = _path(project_id, cid)
    if p.exists():
        try:
            loaded = json.loads(p.read_text())
            if isinstance(loaded, dict) and isinstance(loaded.get("moments"), list):
                data["moments"] = loaded["moments"]
        except (json.JSONDecodeError, OSError):
            pass
    if _ensure_ids(data["moments"]) and p.exists():
        _write(project_id, cid, data)
    return data


def _write(project_id: str, cid: str, data: dict) -> None:
    d = _dir(project_id)
    d.mkdir(parents=True, exist_ok=True)
    _path(project_id, cid).write_text(json.dumps(data, ensure_ascii=False, indent=2))


def save_moments(project_id: str, cid: str, moments: list[dict]) -> dict:
    """Coarse save (edits/reorder/delete/manual add). Keeps only known fields."""
    clean = []
    for m in moments:
        if not isinstance(m, dict):
            continue
        clean.append({
            "id":          m.get("id") or _new_id(),
            "title":       (m.get("title") or "").strip(),
            "source":      (m.get("source") or "").strip(),
            "description": (m.get("description") or "").strip(),
        })
    data = {"moments": clean}
    _write(project_id, cid, data)
    return data


def add_moment(project_id: str, cid: str, title: str,
               source: str | None = None, description: str | None = None) -> dict:
    """Add one 名场面 (AI-tool surface; add/remove only)."""
    title = (title or "").strip()
    if not title:
        raise ValueError("moment title is required")
    data = load_moments(project_id, cid)
    item = {"id": _new_id(), "title": title,
            "source": (source or "").strip(), "description": (description or "").strip()}
    data["moments"].append(item)
    _write(project_id, cid, data)
    return item


def remove_moment(project_id: str, cid: str, id: str) -> dict | None:
    """Remove a 名场面 by id. Returns the removed item, or None."""
    data = load_moments(project_id, cid)
    for i, m in enumerate(data["moments"]):
        if m.get("id") == id:
            removed = data["moments"].pop(i)
            _write(project_id, cid, data)
            return removed
    return None


def generate_moments(project_id: str, cid: str) -> dict:
    """Research the character's 名场面 via LLM + web_search and save them.
    Replaces the stored list. Returns { moments: [...] }.

    Structured output comes via a passthrough `submit_moments` tool (same pattern
    as character_chat's update_profile) — the tool's input IS the data, so there's
    no fragile free-text JSON parsing/truncation. Retries once if the model never
    submits."""
    from services import project_service
    from tools.llm import call_agent
    from tools.search import web_search

    proj = project_service.get_project(project_id)  # raises FileNotFoundError
    char = next((c for c in proj.get("characters", []) if c["id"] == cid), None)
    name = (char or {}).get("name") or proj.get("character") or ""
    series = (char or {}).get("series") or proj.get("series") or ""

    tools = [
        {
            "name": "web_search",
            "description": "搜索角色相关信息,支持中/日/英多语言。",
            "input_schema": {"type": "object", "properties": {
                "query": {"type": "string"},
                "lang": {"type": "string", "enum": ["zh-cn", "en", "ja"]},
            }, "required": ["query"]},
        },
        {
            "name": "submit_moments",
            "description": "查证完成后,提交整理好的名场面列表(4-6 条)。",
            "input_schema": {"type": "object", "properties": {
                "moments": {
                    "type": "array",
                    "items": {"type": "object", "properties": {
                        "title":       {"type": "string", "description": "简短标题"},
                        "source":      {"type": "string", "description": "大概出处(第几季/第几话/剧场版等,不确定写模糊范围,不要硬编精确话数)"},
                        "description": {"type": "string", "description": "详细描述:发生了什么、大概在故事什么阶段、前后背景(2-4句)"},
                    }, "required": ["title", "source", "description"]},
                },
            }, "required": ["moments"]},
        },
    ]
    executor = {"web_search": lambda inp: web_search(inp["query"], lang=inp.get("lang", "zh-cn"))}

    system = (
        f"你是资深 ACG 编辑,负责整理角色的『名场面』——最具代表性、粉丝公认的经典场景。"
        f"这是角色设定参考资料,不是拍摄指南,不要写任何拍摄/运镜/表情建议。"
        f"目标角色:《{series}》的 {name}。"
        f"先用 web_search 多次(中/日/英)查证,不要凭空编造场景;"
        f"查证完成后调用 submit_moments 提交 4-6 条名场面。source 只写大概出处(不要放网址)。"
    )

    arr = None
    for _ in range(2):  # one retry if the model never calls submit_moments
        res = call_agent(
            messages=[{"role": "user", "content": f"请查证并整理 {name} 的名场面,然后调用 submit_moments 提交。"}],
            system=system, tools=tools, tool_executor=executor, max_turns=8, max_tokens=1500,
        )
        call = next((c for c in res.get("tool_calls", []) if c.get("name") == "submit_moments"), None)
        if call and isinstance(call.get("input", {}).get("moments"), list):
            arr = call["input"]["moments"]
            break
    if not arr:
        raise RuntimeError("名场面生成失败(未能获取结果),请重试")

    moments = []
    for m in arr:
        if not isinstance(m, dict) or not (m.get("title") or "").strip():
            continue
        moments.append({
            "id":          _new_id(),
            "title":       str(m.get("title", "")).strip(),
            "source":      str(m.get("source", "")).strip(),
            "description": str(m.get("description", "")).strip(),
        })
    if not moments:
        raise RuntimeError("名场面生成失败(结果为空),请重试")
    data = {"moments": moments}
    _write(project_id, cid, data)
    return data
