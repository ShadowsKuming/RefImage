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
        "name": "classify_ref",
        "description": (
            "当用户上传了参考图（r 节点）且你已经知道用户想参考什么时，调用此工具设置类型并启动处理。"
            "如果用户还没说清楚，先问用户：「这张图你想参考哪个方面？动作姿势、背景环境、武器道具，还是服装？」"
            "确认后再调用。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ref_id": {
                    "type": "string",
                    "description": "r 节点的 ID（从对话上下文中获取）",
                },
                "ref_type": {
                    "type": "string",
                    "enum": ["pose", "background", "weapon", "costume", "lighting", "expression"],
                    "description": (
                        "pose        — 动作/姿势参考 → 转成 mannequin 草图\n"
                        "background  — 背景/环境参考 → 抠掉人物留背景\n"
                        "weapon      — 武器/道具参考 → 提取道具白底图\n"
                        "costume     — 服装参考 → 保留服装换无脸人台\n"
                        "lighting    — 打光/机位参考 → 提取文字描述注入 prompt\n"
                        "expression  — 表情参考 → 提取文字描述注入 prompt"
                    ),
                },
            },
            "required": ["ref_id", "ref_type"],
        },
    },
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
                        "必填。生成前必须向用户确认画幅，不可自行决定。\n"
                        "square         = 1:1   方图（特殊构图时用）\n"
                        "portrait       = 2:3   竖图（全身、角色特写）\n"
                        "landscape      = 3:2   横图（场景、环境感）\n"
                        "landscape_wide = 16:9  宽横图（电影感）\n"
                        "用户说「竖图/竖版」→ portrait；「横图/横版」→ landscape；"
                        "「16:9/电影感」→ landscape_wide；方图罕见，只在用户明确说时用。"
                    ),
                },
                "ref_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "可选。用户框选的 r 节点 ID 列表（已处理完毕的参考图）。"
                        "只填已处理完成（status=ready）的 ref_id。"
                        "系统自动将处理后的图片（mannequin 草图/背景图/道具图/服装图）"
                        "加进生成输入，文字类型（lighting/expression）注入对应字段。"
                    ),
                },
            },
            "required": ["atmosphere", "scene", "pose", "composition", "orientation"],
        },
    },
]


def _build_system(project: dict, shot: dict, shot_refs: list[dict] | None = None, selected_ref_ids: list[str] | None = None) -> str:
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
        "- 方案细节足够后（有场景/姿势/构图/氛围）→ 先问用户「横图还是竖图？」（如果对话中还没确认过画幅）。",
        "  示例：「方案定了，最后确认一下——横图还是竖图？」",
        "- 用户确认画幅后 → 调用 generate_image，不再需要额外确认。",
        "- 如果用户在方案讨论中已经明确提到画幅（如「竖图」「横版」「16:9」），跳过画幅提问直接等确认生成。",
        "- 用户确认（「可以」「好的」「生成」「就这样」等）且画幅已知 → 调用 generate_image。",
        "- 禁止在未经用户确认的情况下调用 generate_image。",
        "- 【重要】用户提出修改请求（「可以吗」「能改成xxx吗」「想要xxx」「换成xxx」）≠ 确认生成。",
        "  收到修改请求后：一句话确认新方案，然后等用户说「可以」再生成。",
        "  示例：用户说「能换成竖图全身吗」→ 你回「好，改竖图全身，构图调整为xxx，帮你生成？」→ 等用户确认。",
        "",
        "你熟悉这个角色的性格、标志性瞬间和经典场景，主动把它们融入方案。",
        "提场景时必须匹配用户要求的氛围——用户要「战斗/帅气」就选战斗场景，不要推荐日常或学校场景。",
        "【审核风险】以下组合容易被图像安全审核拦截，设计方案时主动规避：",
        "- 短裙/暴露服装 + 竖图全身 + 仰拍或低机位（必须改为平视或略高机位）",
        "- 姿势含「躺」「趴」「坐地上」+ 竖图",
        "- 「裙摆随风飘扬/微扬」的描述在竖图全身构图下极易被拦截，改用「裙摆自然垂落」。",
        "【竖图全身姿势注意】竖图全身（portrait full body）时，避免「回眸」「扭腰大角度转身」等动作，",
        "  模型在这类构图下容易生成解剖学错误（脚反向、身体扭曲）。",
        "  推荐替代：正面站立微笑、3/4 侧面（身体与头同向）、背对镜头回头（头转<30度）。",
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

    # ── r-node context ────────────────────────────────────────────
    if shot_refs:
        pending = [r for r in shot_refs if r.get("status") == "pending_type"]
        ready   = [r for r in shot_refs if r.get("status") == "ready"]
        if pending:
            lines += ["", "═══ 待分类参考图 ═══"]
            for r in pending:
                lines.append(f"- ref_id={r['id']}（尚未分类，需要问用户想参考什么）")
        if ready:
            lines += ["", "═══ 可用参考图（已处理）═══"]
            _type_zh = {
                "pose": "动作姿势", "background": "背景环境",
                "weapon": "武器道具", "costume": "服装",
                "lighting": "打光/机位", "expression": "表情",
            }
            for r in ready:
                lines.append(f"- ref_id={r['id']} 类型={_type_zh.get(r['type'], r['type'])}")

    if selected_ref_ids:
        lines += ["", "═══ 本次框选的参考图 ═══"]
        sel_map = {r["id"]: r for r in (shot_refs or [])}
        for rid in selected_ref_ids:
            r = sel_map.get(rid)
            if r:
                status = r.get("status", "unknown")
                rtype  = r.get("type") or "未分类"
                lines.append(f"- ref_id={rid} 类型={rtype} 状态={status}")
            else:
                lines.append(f"- ref_id={rid}")
        lines.append(
            "生成时可在 generate_image 的 ref_ids 字段填入 status=ready 的 ref_id，"
            "系统会自动将处理后的图片纳入生成输入。"
        )

    return "\n".join(lines)


def chat(
    message: str,
    history: list[dict],
    project: dict,
    shot: dict,
    shot_refs: list[dict] | None = None,
    selected_ref_ids: list[str] | None = None,
) -> dict:
    """
    Process one shot-level chat message.

    Returns:
        { reply: str, generating: bool, prompt_parts: dict | None,
          classify_ref: dict | None }
    """
    system   = _build_system(project, shot, shot_refs, selected_ref_ids)
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
            **({"ref_ids":     inp["ref_ids"]}     if inp.get("ref_ids")     else {}),
        }
        return "生成指令已收到，正在生成参考例图，请在回复中告知用户稍等片刻。"

    def _execute_classify_ref(inp: dict) -> str:
        captured["classify_ref"] = {"ref_id": inp["ref_id"], "ref_type": inp["ref_type"]}
        _type_zh = {
            "pose": "动作姿势", "background": "背景环境",
            "weapon": "武器道具", "costume": "服装",
            "lighting": "打光/机位", "expression": "表情",
        }
        return f"已标记为「{_type_zh.get(inp['ref_type'], inp['ref_type'])}」，正在处理中，完成后即可使用。"

    tool_executor = {
        "web_search":     lambda inp: _web_search(inp["query"], lang=inp.get("lang", "zh-cn")),
        "generate_image": _execute_generate,
        "classify_ref":   _execute_classify_ref,
    }

    result = call_agent(
        messages=messages,
        system=system,
        tools=TOOLS,
        tool_executor=tool_executor,
        max_turns=6,
        max_tokens=800,
    )

    return {
        "reply":        result["text"],
        "generating":   captured.get("prompt_parts") is not None,
        "prompt_parts": captured.get("prompt_parts"),
        "classify_ref": captured.get("classify_ref"),
    }
