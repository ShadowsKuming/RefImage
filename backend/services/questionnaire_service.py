"""
services/questionnaire_service.py — Shot "破冰问卷" generation (three-step funnel)

The shot page's main task is getting a satisfying reference image. To kill the
blank-page problem we greet the user with a short, progressively-narrowing survey
whose options are AI-generated FROM THE CHARACTER'S CANON — so they're specific to
this character, not generic templates.

The funnel (see the design demo we converged on):
  1. 大方向 (direction)   — 轻音部排练 / 舞台演出 / 校园日常 …
  2. 具体活动 (activity)   — 依赖上一步：排练时 → 独自弹贝斯 / 和队友交流 …
  3. 场景+氛围 (scene)     — 依赖上一步，一句话锁死动作+情绪（吸收了姿态/表情）
Then the frontend adds fixed universal dimensions the backend does NOT generate:
  4. 画面重心 (focus)      — 突出人物 / 氛围 / 互动（并预选景别+画幅）
  5. 景别 / 机位 / 画幅    — technical

So this service only produces the character-specific three-level tree (1→2→3).
Structured output via a passthrough submit tool (reliable JSON, same pattern as
moments/wardrobe). Cached per character at context/questionnaire/{cid}.json.
"""
import json
from pathlib import Path

STORAGE_ROOT = Path(__file__).parent.parent / "storage" / "projects"


def _dir(project_id: str) -> Path:
    return STORAGE_ROOT / project_id / "context" / "questionnaire"


def _path(project_id: str, cid: str) -> Path:
    return _dir(project_id) / f"{cid}.json"


def load_questionnaire(project_id: str, cid: str) -> dict:
    """Return { directions: [ { key, label, activities: [ { key, label, scenes[] } ] } ] },
    or empty directions if not generated yet."""
    p = _path(project_id, cid)
    if p.exists():
        try:
            data = json.loads(p.read_text())
            if isinstance(data, dict) and isinstance(data.get("directions"), list):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {"directions": []}


def _write(project_id: str, cid: str, data: dict) -> None:
    d = _dir(project_id)
    d.mkdir(parents=True, exist_ok=True)
    _path(project_id, cid).write_text(json.dumps(data, ensure_ascii=False, indent=2))


def generate_questionnaire(project_id: str, cid: str) -> dict:
    """LLM-generate the character-specific three-level funnel tree from the
    character's canon, save, and return. Retries once."""
    from services import project_service
    from tools.llm import call_agent

    proj = project_service.get_project(project_id)  # raises FileNotFoundError
    char = next((c for c in proj.get("characters", []) if c["id"] == cid), None)
    name = (char or {}).get("name") or proj.get("character") or ""
    series = (char or {}).get("series") or proj.get("series") or ""
    cb = ((char or {}).get("character_data") or proj.get("character_data") or {}).get("characterBackground") or {}
    ws = (proj.get("world") or {}).get("worldSetting") or {}
    vs = (char or {}).get("visual_spec") or proj.get("visual_spec") or {}
    appearance = vs.get("zh") if isinstance(vs, dict) else str(vs)

    ctx = (
        f"角色：{name}（{series}）\n"
        f"定位：{cb.get('role', '')}\n"
        f"性格：外在 {cb.get('personality', {}).get('surface', '')}；内心 {cb.get('personality', {}).get('inner', '')}\n"
        f"标志瞬间：{'、'.join(cb.get('iconic_moments', []))}\n"
        f"标志场景：{'、'.join(ws.get('iconic_settings', []))}\n"
        f"情绪光谱：日常「{cb.get('emotional_range', {}).get('baseline', '')}」压力「{cb.get('emotional_range', {}).get('stress', '')}」\n"
        f"外貌：{(appearance or '')[:150]}"
    )

    tools = [{
        "name": "submit_questionnaire",
        "description": "提交拍摄破冰问卷的三层漏斗树：大方向 → 具体活动 → 场景+氛围。",
        "input_schema": {"type": "object", "properties": {
            "directions": {"type": "array", "description": "3-5 个拍摄大方向", "items": {
                "type": "object", "properties": {
                    "label": {"type": "string", "description": "大方向名，如 轻音部排练 / 舞台演出 / 校园日常（4-8 字）"},
                    "activities": {"type": "array", "description": "这个方向下 2-3 个具体活动", "items": {
                        "type": "object", "properties": {
                            "label": {"type": "string", "description": "具体在干嘛，如 独自弹贝斯练习 / 和队友交流讨论（不超过 12 字）"},
                            "scenes": {"type": "array", "items": {"type": "string"},
                                       "description": "2-4 个具体场景，每个是一句话，同时点明【动作+情绪/氛围】，如「站着独自练贝斯，轻松愉快的氛围」"},
                        }, "required": ["label", "scenes"]},
                    },
                }, "required": ["label", "activities"]},
            },
        }, "required": ["directions"]},
    }]

    system = (
        "你是 cosplay 拍摄策划。根据下面这个角色的资料，设计一份『拍摄破冰问卷』——一棵三层漏斗树，"
        "帮用户从大方向一步步收窄到具体场景，快速定下第一张参考例图拍什么。\n"
        "三层结构：\n"
        "① 大方向(direction)：这个角色可拍的几大类情境（3-5 个）。\n"
        "② 具体活动(activity)：每个方向下他/她具体在干嘛（2-3 个）。\n"
        "③ 场景+氛围(scene)：每个活动下的具体画面，每个是一句话，"
        "务必同时点明【动作】和【情绪/氛围】（2-4 个）——因为这一句要同时把姿态和表情都定下来。\n"
        "全部必须贴合这个具体角色（用它的标志场景/瞬间/性格），不要写通用模板。"
        "景别、机位、画幅、画面重心这些通用维度不用你出（前端固定）。整理完调用 submit_questionnaire。\n\n"
        f"{ctx}"
    )

    directions = None
    for _ in range(2):
        res = call_agent(
            messages=[{"role": "user", "content": f"为 {name} 设计三层漏斗破冰问卷，然后调用 submit_questionnaire。"}],
            system=system, tools=tools, tool_executor={}, max_turns=3, max_tokens=3000,
        )
        call = next((c for c in res.get("tool_calls", []) if c.get("name") == "submit_questionnaire"), None)
        if call and isinstance(call.get("input", {}).get("directions"), list):
            directions = call["input"]["directions"]
            break
    if not directions:
        raise RuntimeError("问卷生成失败(未能获取结果),请重试")

    clean = []
    for di, d in enumerate(directions):
        if not isinstance(d, dict):
            continue
        dlabel = str(d.get("label") or "").strip()
        acts = []
        for ai, a in enumerate(d.get("activities") or []):
            if not isinstance(a, dict):
                continue
            alabel = str(a.get("label") or "").strip()
            scenes = [str(s).strip() for s in (a.get("scenes") or []) if str(s).strip()]
            if alabel and scenes:
                acts.append({"key": f"a{di}_{ai}", "label": alabel, "scenes": scenes})
        if dlabel and acts:
            clean.append({"key": f"d{di}", "label": dlabel, "activities": acts})
    if not clean:
        raise RuntimeError("问卷生成失败(结果为空),请重试")

    data = {"directions": clean}
    _write(project_id, cid, data)
    return data
