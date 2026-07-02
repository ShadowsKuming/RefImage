"""
tools/shot_chat.py — Per-shot AI assistant (image generation + guide discussion)

The assistant helps the user refine their vision for a specific shot.
When the vision is clear it calls generate_image with a composed prompt —
the caller captures this via closure and returns it to the frontend,
which then triggers the actual image generation API call.
"""
from tools.llm import call_agent
from tools.search import web_search as _web_search


TOOLS = [
    {
        "name": "web_search",
        "description": "搜索拍摄参考资料：场地实景、布光方案、pose 参考、cosplay 案例等。",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "lang":  {"type": "string", "enum": ["zh-cn", "en", "ja"]},
            },
            "required": ["query"],
        },
    },
    {
        "name": "generate_image",
        "description": (
            "当用户对这张拍摄图的效果描述足够清晰时，调用此工具生成参考例图。"
            "角色外貌和服装由参考图和项目数据自动提供，无需描述。"
            "只需填写四个字段：氛围色调、场景环境、姿势表情、构图视角。"
            "调用后请在回复中告知用户正在生成，稍等片刻。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "atmosphere": {
                    "type": "string",
                    "description": (
                        "色调与氛围，英文，三行：\n"
                        "Color tone: [warm golden / cool blue-grey / high contrast / desaturated]\n"
                        "Mood: [healing / melancholic / tense / romantic / energetic]\n"
                        "Genre feel: [school life / action / drama / fantasy / slice-of-life]"
                    ),
                },
                "scene": {
                    "type": "string",
                    "description": (
                        "物理场景，英文。包含：地点、时间/光线、"
                        "角色站在哪里/脚踩什么、背景环境元素。"
                        "示例：'School rooftop at golden hour. Character stands behind "
                        "a waist-height metal safety railing, feet planted on the rooftop floor. "
                        "City skyline softly blurred in the distance.'"
                    ),
                },
                "pose": {
                    "type": "string",
                    "description": (
                        "身体动作与表情，英文。描述手臂/腿/头部姿势和情绪表情。"
                        "示例：'Facing the camera, both forearms resting on top of the railing, "
                        "leaning forward slightly. Pensive expression, eyes looking gently to the side.'"
                    ),
                },
                "composition": {
                    "type": "string",
                    "description": (
                        "构图与相机，英文。必须同时说明：\n"
                        "① 相机高度（eye-level / slightly above / bird's eye）\n"
                        "② 镜头类型（close-up / medium shot / full body shot）\n"
                        "③ 相机角度（straight-on / 3/4 angle / profile）\n"
                        "④ 画面可见范围（角色可见到哪里、关键道具在画面位置）\n"
                        "示例：'Camera at eye level with her face, straight-on. "
                        "Medium shot: character visible from the knees up, "
                        "railing clearly at waist height.'"
                    ),
                },
                "style": {
                    "type": "string",
                    "description": (
                        "可选。仅当用户明确要求偏离默认画风时填写，英文。"
                        "默认画风由项目设定自动提供，无需填写。"
                        "示例：'retro film grain, muted palette' / 'dark fantasy illustration'"
                    ),
                },
                "orientation": {
                    "type": "string",
                    "enum": ["square", "portrait", "landscape", "landscape_wide"],
                    "description": (
                        "可选，默认 square（1:1）。根据构图自动判断，无需用户指定。\n"
                        "square         = 1:1   通用\n"
                        "portrait       = 2:3   全身站姿、角色特写\n"
                        "landscape      = 3:2   场景横图、环境感\n"
                        "landscape_wide = 16:9  电影宽画面"
                    ),
                },
            },
            "required": ["atmosphere", "scene", "pose", "composition"],
        },
    },
]


def _build_system(project: dict, shot: dict) -> str:
    char_data   = project.get("character_data", {})
    char_bg     = char_data.get("characterBackground", {})
    if not isinstance(char_bg, dict): char_bg = {}
    world_ws    = project.get("world", {}).get("worldSetting", {})
    if not isinstance(world_ws, dict): world_ws = {}
    visual_spec = project.get("visual_spec", {})

    char_name   = char_data.get("character", "未知角色")
    series_name = project.get("series", "")
    vs_text     = visual_spec.get("zh", "") if isinstance(visual_spec, dict) else str(visual_spec)

    lines = [
        "你是一个懂拍摄策划的动漫cos创意搭档，帮用户设计单张cos拍摄参考图。",
        "",
        "【对话风格】",
        "- 像创意导演，不像客服。你来主导方向，用户来拍板。",
        "- 禁止列多个问题让用户做选择题。每次回复最多提一个问题，或者直接给方案。",
        "- 禁止解释型长句（「这种风格会让xxx更突出，也贴合xxx」）。说结论，不说理由。",
        "- 语气短，直接，像在和朋友讨论拍摄策划。",
        "",
        "【推进逻辑】",
        "- 用户给出大概方向 → 你立刻定一个具体方案，让用户说「可以」或「换一下xxx」。",
        "  示例：「我先走赛博楼顶+双刀前冲这个方向，背景粉紫霓虹，低角度仰拍压迫感。你觉得呢？」",
        "- 用户说「没思路」「你来定」「给个例子」→ 给 2-3 个简短风格选项，用户选一个。",
        "  示例：「三个方向你选一个：① 楼顶突袭（霓虹背景，冲刺姿态）② 巷战瞬间（雨夜，刀光特写）③ 虚拟空间（星光碎片环绕，像宣传图）」",
        "- 方案细节足够后（有场景/姿势/构图/氛围）→ 一句话总结，问用户要不要生成。",
        "- 用户确认（「可以」「好的」「生成」「就这样」等）→ 调用 generate_image。",
        "- 禁止在未经用户确认的情况下调用 generate_image。",
        "",
        "你熟悉这个角色的性格、标志性瞬间和经典场景，主动把它们融入方案。",
        "提场景时必须匹配用户要求的氛围——用户要「战斗/帅气」就选战斗场景，不要推荐日常或学校场景。",
        "【审核风险】以下组合容易被图像安全审核拦截，发现时提前提醒：",
        "- 短裙/暴露服装 + 竖图 + 全身俯拍或仰拍",
        "- 姿势含「躺」「趴」「坐地上」+ 竖图",
        "",
        "═══ 角色 ═══",
        f"{char_name}（{series_name}）",
    ]

    tone = world_ws.get("tone", {})
    if tone:
        lines.append(f"作品基调：{tone.get('visual','')}·{tone.get('emotion','')}")

    if char_bg:
        personality = char_bg.get("personality", {})
        surface = personality.get("surface", "")
        inner   = personality.get("inner", "")
        if surface or inner:
            lines.append(f"气质：{surface}；{inner}")

        iconic = char_bg.get("iconic_moments", [])
        if iconic:
            lines.append(f"标志性瞬间：{'、'.join(iconic)}")

        habits = char_bg.get("behavior", {}).get("habits", [])
        if habits:
            lines.append(f"习惯/道具：{'、'.join(habits)}")

        emo_baseline = char_bg.get("emotional_range", {}).get("baseline", "")
        if emo_baseline:
            lines.append(f"情绪基线：{emo_baseline}")

    iconic_settings = world_ws.get("iconic_settings", [])
    if iconic_settings:
        lines.append(f"经典场景：{'、'.join(iconic_settings)}")

    if vs_text.strip():
        lines += ["", "═══ 外貌特征 ═══", vs_text.strip()]

    title = shot.get("title", "")
    mood  = shot.get("mood", "")
    desc  = shot.get("description", "")
    lines += ["", "═══ 本张拍摄 ═══", f"标题：{title}"]
    if mood:
        lines.append(f"氛围：{mood}")
    if desc:
        lines.append(f"备注：{desc}")

    return "\n".join(lines)


def chat(message: str, history: list[dict], project: dict, shot: dict) -> dict:
    """
    Process one shot-level chat message.

    Returns:
        { reply: str, generating: bool, prompt: str | None }
        generating is True when the AI called generate_image this turn.
        prompt is the captured image prompt (passed to the background task by the caller).
    """
    system   = _build_system(project, shot)
    messages = history + [{"role": "user", "content": message}]

    captured: dict = {}

    def _execute_generate(inp: dict) -> str:
        captured["prompt_parts"] = {
            "atmosphere":  inp.get("atmosphere", ""),
            "scene":       inp.get("scene", ""),
            "pose":        inp.get("pose", ""),
            "composition": inp.get("composition", ""),
            **({"style":       inp["style"]}       if inp.get("style")       else {}),
            **({"orientation": inp["orientation"]} if inp.get("orientation") else {}),
        }
        return "生成指令已收到，正在生成参考例图，请在回复中告知用户稍等片刻。"

    tool_executor = {
        "web_search":     lambda inp: _web_search(inp["query"], lang=inp.get("lang", "zh-cn")),
        "generate_image": _execute_generate,
    }

    result = call_agent(
        messages=messages,
        system=system,
        tools=TOOLS,
        tool_executor=tool_executor,
        max_turns=6,
        max_tokens=800,
    )

    prompt_parts = captured.get("prompt_parts")
    return {
        "reply":        result["text"],
        "generating":   prompt_parts is not None,
        "prompt_parts": prompt_parts,
    }
