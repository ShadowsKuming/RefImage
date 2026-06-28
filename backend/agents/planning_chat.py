"""
tools/planning_chat.py — Cosplay photoshoot planning assistant (agentic)

Uses call_agent() with two tools:
  - web_search  (executor)   — look up locations, equipment, cosplay refs, etc.
  - update_brief (passthrough) — commit the crystallised plan to disk

The loop runs until the model either replies in plain text OR calls update_brief.
The caller (guide_service) handles persisting the brief and returning it to the API.
"""
import json
from pathlib import Path
from tools.llm import call_agent
from tools.search import web_search as _web_search

STORAGE_ROOT = Path(__file__).parent.parent / "storage" / "projects"

_GUIDE_LABELS = {
    "action":     "动作",
    "expression": "表情",
    "background": "背景",
    "camera":     "构图",
}


def _load_shot_guides(project_id: str, shot_id: str) -> dict:
    """Load all available guide data for a shot."""
    guides_dir = STORAGE_ROOT / project_id / "shots" / shot_id / "guides"
    result = {}
    for guide_type, label in _GUIDE_LABELS.items():
        path = guides_dir / f"{guide_type}.json"
        if path.exists():
            try:
                data = json.loads(path.read_text())
                result[label] = data.get("guide", data)
            except Exception:
                pass
    return result


# ── Tool schemas (Anthropic canonical format) ─────────────────────────────────

TOOLS = [
    {
        "name": "web_search",
        "description": (
            "搜索真实世界的信息，例如：拍摄地点详情、摄影设备推荐、"
            "cosplay 道具资源、特定角色的视觉参考。"
            "使用中文查询国内资源，使用英文/日文查询海外资源。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "lang":  {"type": "string", "enum": ["zh-cn", "en", "ja"], "description": "搜索语言，默认 zh-cn"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "update_brief",
        "description": (
            "当你和用户已经就拍摄规划达成足够共识时，调用此工具将规划内容写入项目档案。"
            "工具执行成功后，请在回复里告知用户总结已更新、可以开始添加拍摄卡片了。"
            "不需要等到计划100%完整，只要核心场地/风格/设备已确定即可调用。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "locations": {
                    "type": "array", "items": {"type": "string"},
                    "description": "拍摄地点列表（具体地名或类型）",
                },
                "equipment": {
                    "type": "array", "items": {"type": "string"},
                    "description": "推荐设备列表（相机/镜头/灯具等）",
                },
                "best_time": {
                    "type": "string",
                    "description": "最佳拍摄时段，如「清晨 6-8 点」「傍晚黄金时段」",
                },
                "props": {
                    "type": "array", "items": {"type": "string"},
                    "description": "道具/服装/配件清单",
                },
                "style_notes": {
                    "type": "string",
                    "description": "整体风格备注：色调、氛围、构图方向等",
                },
            },
            "required": ["locations", "equipment", "best_time", "props"],
        },
    },
]


# ── System prompt ─────────────────────────────────────────────────────────────

def _build_system(project: dict, project_id: str) -> str:
    char_data   = project.get("character_data", {})
    char_bg     = char_data.get("characterBackground", {})
    world       = project.get("world", {}).get("worldSetting", {})
    visual_spec = project.get("visual_spec", {})

    char_name   = char_data.get("character", "未知角色")
    series_name = project.get("series", "")

    vs_text = (
        visual_spec.get("zh", "")
        if isinstance(visual_spec, dict)
        else str(visual_spec)
    )

    lines = [
        "你是这个 cosplay 拍摄项目的创意总监，全面掌控项目的拍摄规划。",
        "你拥有项目的完整信息：角色资料、已规划的所有 shots 及其 guide 数据。",
        "",
        "工作方式：",
        "- 每次回复前先在脑子里过一遍整个项目，主动发现问题和缺口，不等用户问",
        "- 直接给出可执行的具体建议，不说'我建议你可以考虑'这类软话",
        "- 需要查资料时（地点/设备/参考图）直接使用 web_search，不需要告知用户",
        "- 随时调用 update_brief 更新拍摄总结——只要你认为当前信息足够写某个字段就写，不需要等用户确认",
        "- 用户说'帮我总结'或'更新总结'时，立即根据现有 shot 数据生成并提交总结",
        "- 如果话题跑偏，自然引导回拍摄规划",
        "",
        "═══ 角色资料 ═══",
        f"角色：{char_name}（{series_name}）",
    ]

    if world:
        tone      = world.get("tone", {})
        synopsis  = world.get("synopsis", "")
        iconic    = world.get("iconic_settings", [])
        themes    = world.get("themes", [])
        visual_t  = tone.get("visual", "")
        emotion_t = tone.get("emotion", "")
        narrative = tone.get("narrative", "")

        if visual_t or emotion_t:
            lines.append(f"作品基调：{visual_t}·{emotion_t}（{narrative}）")
        if synopsis:
            lines.append(f"故事概要：{synopsis}")
        if themes:
            lines.append(f"核心主题：{'、'.join(themes)}")
        if iconic:
            lines.append(f"标志场景：{'、'.join(iconic)}")

    if char_bg:
        personality = char_bg.get("personality", {})
        moments     = char_bg.get("iconic_moments", [])
        role        = char_bg.get("role", "")
        backstory   = char_bg.get("backstory", "")

        if role:
            lines.append(f"角色定位：{role}")
        if backstory:
            lines.append(f"背景：{backstory}")
        if personality:
            surface = personality.get("surface", "")
            inner   = personality.get("inner", "")
            desire  = personality.get("core_desire", "")
            if surface or inner:
                lines.append(f"气质：外在 {surface}；内心 {inner}")
            if desire:
                lines.append(f"内心渴望：{desire}")
        if moments:
            lines.append(f"标志性瞬间：{'；'.join(moments[:4])}")

    if vs_text.strip():
        lines += ["", "═══ 外貌特征（来自参考图提取）═══", vs_text.strip()]

    shots = project.get("shots", [])
    if shots:
        lines += ["", "═══ 当前拍摄计划 ═══"]
        for i, s in enumerate(shots, 1):
            mood = f"（{s['mood']}）" if s.get("mood") else ""
            desc = f" — {s['description']}" if s.get("description") else ""
            lines.append(f"{i}. {s['title']}{mood}{desc}  [{s.get('status', 'pending')}]")
            guides = _load_shot_guides(project_id, s["shot_id"])
            for label, guide in guides.items():
                # Flatten guide to key facts only, keep it concise
                parts = []
                if isinstance(guide, dict):
                    for key in ("description", "shotType", "framing", "emotion"):
                        if guide.get(key):
                            parts.append(str(guide[key]))
                    cam = guide.get("camera", {})
                    if isinstance(cam, dict) and cam.get("height"):
                        parts.append(f"机位:{cam['height']}")
                    comp = guide.get("composition", {})
                    if isinstance(comp, dict) and comp.get("rule"):
                        parts.append(f"构图:{comp['rule']}")
                    factors = guide.get("keyVisualFactors", [])
                    if factors:
                        parts.append(f"关键视觉:{'/'.join(factors[:3])}")
                if parts:
                    lines.append(f"   [{label}] {' · '.join(parts)}")
    else:
        lines += ["", "═══ 当前拍摄计划 ═══", "（尚未添加任何拍摄）"]

    return "\n".join(lines)


# ── Main entry point ──────────────────────────────────────────────────────────

def chat(message: str, history: list[dict], project: dict, project_id: str) -> dict:
    """
    Process one planning message and return a result dict.

    Args:
        message: The user's latest message.
        history: Prior turns as [{ role: 'user'|'assistant', content: str }].
        project: Full project dict from project_service.get_project().

    Returns:
        {
          reply: str,            — text reply to show the user
          brief: dict | None,    — populated if update_brief was called, else None
        }
    """
    system   = _build_system(project, project_id)
    messages = history + [{"role": "user", "content": message}]

    # Closure captures brief data when AI calls update_brief.
    # update_brief is an executor tool so the AI receives a confirmation
    # string and continues to produce a text reply in the same loop —
    # this avoids the empty-bubble bug caused by passthrough tools that
    # return no text when using OpenAI's chat completion format.
    captured_brief: dict = {}

    def _execute_update_brief(inp: dict) -> str:
        captured_brief.update(inp)
        return (
            "规划总结已保存成功。"
            "请在你的回复中告诉用户：右侧「拍摄总结」栏已更新，"
            "可以开始点击「+」添加具体的拍摄计划卡片了。"
        )

    tool_executor = {
        "web_search":    lambda inp: _web_search(inp["query"], lang=inp.get("lang", "zh-cn")),
        "update_brief":  _execute_update_brief,
    }

    result = call_agent(
        messages=messages,
        system=system,
        tools=TOOLS,
        tool_executor=tool_executor,
        max_turns=6,
        max_tokens=1000,
    )

    return {
        "reply": result["text"],
        "brief": captured_brief if captured_brief else None,
    }
