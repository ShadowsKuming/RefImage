"""
services/shot_plan_service.py — Stage-3 shot plan extraction

Once a final version is selected, extract a "拍摄方案卡" — the shooting plan for
the real photoshoot, organized into three classes:

  A. 相关信息   — synopsis / goal (priority is KNOWN, not AI)
  B. 拍摄物流   — scene(+室内外) / timing / crew / props / aux-gear / equipment
                 (this is what AGGREGATES back to the project plan)
  C. 拍摄要点   — expression / pose / composition / risks

Design principles baked in:
  - Don't re-derive what we already know. 镜头/构图 come from the version's params;
    角色道具 come from 设定 wardrobe — the service merges these, the AI doesn't guess.
  - Minimal aux-gear: the AI picks only a few items that the shot actually triggers,
    from gear_library (a curated dict — no hallucinated gear). User can add their own.
  - Everything in B is shot-level logistics meant to roll up to the workspace.

Cached at shots/{shot_id}/plan.json; regeneratable.
"""
import json
from pathlib import Path

STORAGE_ROOT = Path(__file__).parent.parent / "storage" / "projects"


def _path(project_id: str, shot_id: str) -> Path:
    return STORAGE_ROOT / project_id / "shots" / shot_id / "plan.json"


def load_plan(project_id: str, shot_id: str) -> dict | None:
    p = _path(project_id, shot_id)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return None


_EDITABLE_PATHS = {
    # dotted path in plan.json → the value must be a string
    "overview.synopsis", "overview.goal",
    "logistics.scene.place", "logistics.timing.best_time", "logistics.timing.weather",
    "logistics.crew.support",
    "technique.expression", "technique.composition", "technique.lighting",
}
_EDITABLE_LISTS = {
    # dotted path → the value is a list[str] (whole-list replace)
    "logistics.equipment",
    "logistics.props.character",
    "technique.pose_tips", "technique.risks",
}


def update_field(project_id: str, shot_id: str, path: str, value) -> dict:
    """User edited one plan field. `path` is a dotted key; strings and known
    list[str] fields are allowed (whitelist — no arbitrary structure writes)."""
    if path not in _EDITABLE_PATHS and path not in _EDITABLE_LISTS:
        raise ValueError(f"field not editable: {path}")
    plan = load_plan(project_id, shot_id)
    if plan is None:
        raise FileNotFoundError("plan not generated")
    if path in _EDITABLE_LISTS:
        value = [str(x).strip() for x in (value or []) if str(x).strip()]
    else:
        value = str(value or "").strip()
    keys = path.split(".")
    node = plan
    for k in keys[:-1]:
        node = node.setdefault(k, {})
    node[keys[-1]] = value
    _path(project_id, shot_id).write_text(json.dumps(plan, ensure_ascii=False, indent=2))
    return plan


def set_location(project_id: str, shot_id: str, name: str, indoor_outdoor: str = "均可") -> dict:
    """User picked/typed a 取景地 for this shot: add it to the project pool (dedupe)
    and set it on the shot's plan. Returns the updated plan."""
    from services import location_service
    plan = load_plan(project_id, shot_id)
    if plan is None:
        raise FileNotFoundError("plan not generated")
    location_service.add_location(project_id, name, indoor_outdoor)
    plan.setdefault("logistics", {}).setdefault("scene", {})["location"] = name.strip()
    _path(project_id, shot_id).write_text(json.dumps(plan, ensure_ascii=False, indent=2))
    return plan


def _gear_brief() -> str:
    from services import gear_library as g
    lines = ["【辅助器材库】(只在触发时挑几件，别全列；用户可自加)"]
    for cat in g.PER_SHOT.values():
        lines.append(f"- {cat['label']}（触发：{cat['when']}）：{'、'.join(cat['items'])}")
    lines.append(f"- 通用固定五金：{'、'.join(g.HARDWARE)}")
    lines.append("【不默认推荐】" + "；".join(g.RESTRICTED))
    return "\n".join(lines)


_TOOL = {
    "name": "submit_shot_plan",
    "description": "提交这张 shot 的拍摄方案（三大类）。",
    "input_schema": {"type": "object", "properties": {
        "synopsis":   {"type": "string", "description": "一句话内容梗概：这张在拍什么瞬间"},
        "goal":       {"type": "string", "description": "拍摄目标/定位，如 主视觉 / 氛围补充 / 关系刻画"},
        "scene_place":     {"type": "string", "description": "拍摄场景，如 轻音部部室（教室内景）"},
        "indoor_outdoor":  {"type": "string", "enum": ["室内", "室外", "均可"]},
        "matched_location": {"type": "string",
                             "description": "如果【项目已有取景地】里有一个适合这张场景的，填它的准确名字（照抄）；没有合适的就留空"},
        "new_candidates": {"type": "array", "items": {"type": "string"},
                           "description": "仅当项目已有取景地里没有合适的，才给 2-3 个新的真实取景地候选（可租借/可去）；有合适的就空数组"},
        "best_time":  {"type": "string", "description": "最佳拍摄时段（含光线理由），室内可写 均可"},
        "weather_note": {"type": "string", "description": "天气注意（室外才关键；室内写 不受天气影响）"},
        "support_reason": {"type": "string", "description": "是否需要后勤及原因（如 需人挑裙摆/扶姿势）；不需要就写 不需要"},
        "shot_props": {"type": "array", "items": {"type": "string"},
                       "description": "本张【从角色道具里】真正会用到的（只挑相关的，别全搬）"},
        "aux_gear":   {"type": "array", "items": {"type": "object", "properties": {
                          "item":   {"type": "string", "description": "从辅助器材库里挑，用库里的名字"},
                          "reason": {"type": "string", "description": "为什么这张需要它，简短"}},
                       "required": ["item", "reason"]},
                       "description": "只挑真正触发的 0-3 件；没有就空数组"},
        "equipment":  {"type": "array", "items": {"type": "string"},
                       "description": "拍摄设备要点，轻量，如 中焦压背景 / 一块反光板补暗面（0-2 条）"},
        "expression": {"type": "string", "description": "表情要点：情绪 + 视线朝向"},
        "pose_tips":  {"type": "array", "items": {"type": "string"}, "description": "姿势要点：争取什么/避免什么（1-3 条）"},
        "composition_note": {"type": "string", "description": "构图补充：人物在三分线何处、留白方向等（镜头参数已知，这里只补建议）"},
        "lighting": {"type": "string", "description": "布光/打光建议（真实拍摄怎么打光）：自然光还是人工光、光源方向（顺/侧/逆/顶）、软硬、是否需要反光板/柔光/补光。跟色调无关"},
        "risks":      {"type": "array", "items": {"type": "string"}, "description": "本张风险/注意（1-3 条，如 注重表情、裙摆动作易解剖学出错）"},
    }, "required": ["synopsis", "scene_place", "indoor_outdoor", "best_time", "expression"]},
}


def extract_plan(project_id: str, shot_id: str) -> dict:
    """LLM-extract the shot plan, merge with known data (priority / 镜头params /
    角色道具池), cache, and return. Retries once."""
    from services import project_service, location_service
    from tools.llm import call_agent

    proj = project_service.get_project(project_id)
    existing_locations = location_service.list_locations(project_id)
    shot = next((s for s in proj.get("shots", []) if s["shot_id"] == shot_id), None)
    if shot is None:
        raise FileNotFoundError(f"shot {shot_id!r} not found")

    fv = next((v for v in shot.get("versions", []) if v["id"] == shot.get("final_version_id")), None)
    params = (fv or {}).get("params", {}) or {}
    scene_prose = ((fv or {}).get("prompt_parts") or {}).get("scene", "")

    char_data = proj.get("character_data", {}) or {}
    cb = char_data.get("characterBackground", {}) if isinstance(char_data.get("characterBackground"), dict) else {}
    ws = proj.get("world", {}).get("worldSetting", {}) if isinstance(proj.get("world", {}).get("worldSetting"), dict) else {}
    name = char_data.get("character") or proj.get("character") or ""
    series = proj.get("series") or ""
    characters = [c.get("name") for c in proj.get("characters", []) if c.get("name")]
    wardrobe = proj.get("wardrobe") or {}
    char_props = [i.get("name") for i in wardrobe.get("props", []) if i.get("name")]

    ctx = (
        f"角色：{name}（{series}）  出镜人物：{'、'.join(characters) or name}\n"
        f"性格：{cb.get('personality', {}).get('surface', '')}；{cb.get('personality', {}).get('inner', '')}\n"
        f"经典场景：{'、'.join(ws.get('iconic_settings', []))}\n"
        f"这张 shot：标题「{shot.get('title', '')}」 氛围「{shot.get('mood', '')}」 备注「{shot.get('description', '')}」\n"
        f"画面内容：{scene_prose or '（见参数）'}\n"
        f"生成参数：{json.dumps(params, ensure_ascii=False)}\n"
        f"角色可用道具（从中挑本张会用到的）：{'、'.join(char_props) or '（无）'}\n"
        f"项目已有取景地（优先复用适合的，别另起炉灶）：{'、'.join(l['name'] for l in existing_locations) or '（暂无）'}\n\n"
        f"{_gear_brief()}"
    )
    system = (
        "你是资深 cosplay 拍摄执行策划。根据这张已选定的参考图资料，整理一份【拍摄方案】——"
        "给真实拍摄用。重点是可执行的物流信息（场景/时间/人/道具/设备），这些之后会汇总成整个项目的拍摄计划。\n"
        "原则：\n"
        "- 镜头/构图参数系统已知，你不用重复；composition_note 只补三分线/留白这类建议。\n"
        "- 角色道具从上面给的清单里挑本张真正会用到的，别搬全部、也别编。\n"
        "- 辅助器材只在画面真的需要时从库里挑 0-3 件（裙摆飘→钓鱼线+鼓风机这种），宁少勿多。\n"
        "- 场景要判断室内/室外，并给真实可去/可租的取景地建议。\n"
        "- 布光是真实拍摄怎么打光的指令（光源方向/软硬/补光），跟色调（冷暖氛围）分开，别混。\n"
        "- 风险提示写这张实际拍摄要注意的点。\n"
        "整理完调用 submit_shot_plan。\n\n"
        f"{ctx}"
    )

    result = None
    for _ in range(2):
        res = call_agent(
            messages=[{"role": "user", "content": f"为「{shot.get('title','')}」整理拍摄方案，然后调用 submit_shot_plan。"}],
            system=system, tools=[_TOOL], tool_executor={}, max_turns=3, max_tokens=1600,
        )
        call = next((c for c in res.get("tool_calls", []) if c.get("name") == "submit_shot_plan"), None)
        if call and isinstance(call.get("input"), dict):
            result = call["input"]
            break
    if not result:
        raise RuntimeError("拍摄方案生成失败，请重试")

    # Location: reuse an existing project location if the AI matched one; else the
    # user must pick from candidates (project pool + new suggestions) — kept
    # required & shared so shots converge on the same places (see location_service).
    matched = (result.get("matched_location") or "").strip()
    existing_names = [l["name"] for l in existing_locations]
    if matched and matched not in existing_names:
        # AI proposed reusing a name not yet in the pool → seed the pool with it
        location_service.add_location(project_id, matched, result.get("indoor_outdoor", "均可"))
    candidate_names = existing_names + [c for c in (result.get("new_candidates") or []) if c not in existing_names]

    plan = {
        "overview": {
            "synopsis": result.get("synopsis", ""),
            "goal":     result.get("goal", ""),
            "priority": shot.get("priority", "mid"),   # known
        },
        "logistics": {
            "scene":       {"place": result.get("scene_place", ""),
                            "indoor_outdoor": result.get("indoor_outdoor", "均可"),
                            "location": matched,              # resolved reuse, or "" → needs pick
                            "candidates": candidate_names},   # pool + new, for the picker
            "timing":      {"best_time": result.get("best_time", ""),
                            "weather": result.get("weather_note", "")},
            "crew":        {"cosers": characters or [name],           # known
                            "support": result.get("support_reason", "")},
            "props":       {"character": result.get("shot_props", []),  # picked from wardrobe
                            "aux": result.get("aux_gear", [])},
            "equipment":   result.get("equipment", []),
        },
        "technique": {
            "params":      params,                       # known — 镜头/构图快照
            "expression":  result.get("expression", ""),
            "pose_tips":   result.get("pose_tips", []),
            "composition": result.get("composition_note", ""),
            "lighting":    result.get("lighting", ""),
            "risks":       result.get("risks", []),
        },
    }
    _path(project_id, shot_id).write_text(json.dumps(plan, ensure_ascii=False, indent=2))
    return plan
