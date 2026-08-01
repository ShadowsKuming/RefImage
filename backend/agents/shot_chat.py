"""
tools/shot_chat.py — Per-shot AI assistant (image generation + guide discussion)

The assistant helps the user refine their vision for a specific shot.
When the vision is clear it calls generate_image with a composed prompt —
the caller captures this via closure and returns it to the frontend,
which then triggers the actual image generation API call.
"""
from tools.llm import call_agent, call_with_tools
from tools.search import web_search as _web_search
from config import LLM_PROVIDER, FAST_LLM_MODEL_BY_PROVIDER

_LANG = {"zh": "中文", "en": "English", "ja": "日本語", "pt": "Português"}


_SUBMIT_OPTIONS_TOOL = {
    "name": "submit_options",
    "description": "提交用户此刻最可能点的快捷回答。",
    "input_schema": {
        "type": "object",
        "properties": {
            "options": {
                "type": "array",
                "items": {"type": "string"},
                "description": "2-6 个快捷回答，第一人称、简短（≤14字）；助手在问句里列了几个候选就给全这几个，别漏",
            },
        },
        "required": ["options"],
    },
}


def _canon_brief(project: dict) -> str:
    """A compact character summary for the (fast-model) options generator."""
    char_data = project.get("character_data", {}) or {}
    cb = char_data.get("characterBackground", {})
    if not isinstance(cb, dict):
        cb = {}
    ws = project.get("world", {}).get("worldSetting", {})
    if not isinstance(ws, dict):
        ws = {}
    name = char_data.get("character", "") or project.get("character", "")
    series = project.get("series", "")
    parts = [f"角色：{name}（{series}）"]
    p = cb.get("personality", {})
    if p.get("surface") or p.get("inner"):
        parts.append(f"气质：{p.get('surface','')}；{p.get('inner','')}")
    if cb.get("iconic_moments"):
        parts.append(f"标志瞬间：{'、'.join(cb['iconic_moments'])}")
    if ws.get("iconic_settings"):
        parts.append(f"经典场景：{'、'.join(ws['iconic_settings'])}")
    return "\n".join(parts)


# The photography step is a DIRECT-CONTROL phase, not chat: once the assistant
# reaches it, the frontend renders a compact camera panel (景别/画幅/机位 buttons
# with the current pick highlighted) instead of chat chips, and tapping a control
# is local state — no LLM call, no paragraph per click. Only 生成 hits the backend.
_SHOTS  = ("特写", "近景", "半身", "全身", "远景")
_ANGLES = ("平视", "俯视", "仰视")
_FRAMING_CONCRETE = _SHOTS + ("竖图", "横图", "竖版", "横版")
_FRAMING_ABSTRACT = ("景别", "机位", "画幅", "镜头", "构图")


def _is_camera_phase(reply: str) -> bool:
    """True only once the assistant is actually PROPOSING the shot's framing (the
    photography step → frontend shows the camera panel). A lone 景别 word inside a
    pose/scene sentence (e.g. "全身蜷缩在角落") must NOT trigger it, or the funnel's
    mood/expression questions lose their quick-reply chips."""
    r = reply.replace(" ", "")
    concrete = [t for t in _FRAMING_CONCRETE if t in r]
    has_ctx = any(t in r for t in _FRAMING_ABSTRACT)   # 景别/机位/画幅/镜头/构图
    reco = ("建议" in r) or ("生成" in r) or ("调" in r)
    # ≥2 framing terms (景别+画幅…) = a real framing proposal; or one term next to a
    # framing-context/recommendation word. One bare term alone is just description.
    if len(concrete) >= 2:
        return True
    if concrete and (has_ctx or reco):
        return True
    if has_ctx and reco:
        return True
    return False


def _extract_camera_suggestion(reply: str) -> dict:
    """Parse the assistant's proposal for suggested framing so the panel opens
    pre-selected on what the AI just recommended. Falls back to sensible defaults."""
    r = reply.replace(" ", "")
    shot = next((s for s in _SHOTS if s in r), "半身")
    if "横图" in r or "横版" in r:
        aspect = "横图"
    elif "竖图" in r or "竖版" in r:
        aspect = "竖图"
    else:
        aspect = "竖图"
    angle = next((a for a in _ANGLES if a in r), "平视")
    return {"shot": shot, "aspect": aspect, "angle": angle}


def _suggest_options(project: dict, messages: list[dict], reply_lang: str = "zh") -> list[str]:
    """Generate 2-4 context-consistent quick-reply chips for the user's next turn.

    Runs as a dedicated cheap fast-model call with a FORCED tool_choice, so the
    output is always structured (no verbalizing) and — because it sees the whole
    conversation — always consistent with what the user already said (say 合练 →
    every option involves teammates, never 独自一人)."""
    lang = _LANG.get(reply_lang, "中文")
    system = (
        f"{_canon_brief(project)}\n\n"
        f"用{lang}输出选项。\n"
        "你的唯一任务：给用户几个能【一键回答助手最后那条消息】的快捷选项（2-4 个，第一人称、短，≤14字）。\n"
        "规则：\n"
        "1. 选项必须是对『助手最后那个问题』的直接回答，和问题同一层级、同一主题——"
        "助手问大方向就给大方向，问具体动作才给动作，别跨层。\n"
        "2. 如果助手的消息里已经列了候选（如「舞台演出、校园日常、社团活动」），"
        "就把它列的【每一个】都做成选项、逐字照用、一个都别漏，也别自己另编。\n"
        "3. 选项之间要有区分度，别都往一个主题挤（别每个都「和队友一起…」）。\n"
        "4. 和用户已经说过的一致，绝不矛盾（用户说了独自，就别出现和队友；说了合练，就别出现独自）。\n"
        "5. 扎在这个角色的设定里，不要通用模板。\n"
        "6. 除非助手最后那句在明确问『要不要生成/这样行吗』，否则绝不能出现「生成」类选项——"
        "还在聊大方向/情节/场景/表演/镜头的任何一步，都只给该步的回答选项。\n"
        "整理好调用 submit_options。"
    )
    fast_model = FAST_LLM_MODEL_BY_PROVIDER.get(LLM_PROVIDER)
    try:
        res = call_with_tools(
            messages=messages, system=system, tools=[_SUBMIT_OPTIONS_TOOL],
            max_tokens=300, force_tool="submit_options", model=fast_model,
        )
    except Exception:
        return []
    call = next((c for c in res.get("tool_calls", []) if c.get("name") == "submit_options"), None)
    if not call:
        return []
    return [str(o).strip() for o in (call.get("input", {}).get("options") or []) if str(o).strip()][:6]


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
                "lang":  {"type": "string", "enum": ["zh-cn", "en", "ja", "pt"]},
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
                "params": {
                    "type": "object",
                    "description": (
                        "本张图对应的结构化参数（供生成后调整面板预填）。按对话里已确定的填，"
                        "拿不准的留空、系统会补默认值。只用下列中文值：\n"
                        "shot 景别: 特写/近景/半身/全身/远景；angle 机位: 俯视/平视/仰视；"
                        "facing 朝向: 正面/侧前/侧面/背面；aspect 画幅: 竖图/横图/方图；"
                        "pos 人物位置: 靠左/居中/靠右；scale 主体大小: 占满/适中/留白多；"
                        "bg 背景: 清晰/适中/虚化；expr 表情(可自定义)；gaze 视线: 看镜头/看别处/低垂；"
                        "pose 姿势(自定义文字)；temp 冷暖: 冷/偏冷/中性/偏暖/暖；mood 氛围(可自定义)。"
                    ),
                    "properties": {
                        k: {"type": "string"} for k in
                        ("shot", "angle", "facing", "aspect", "pos", "scale", "bg", "expr", "emphasis", "gaze", "pose", "temp", "grade", "maincolor", "mood")
                    },
                },
                "title": {
                    "type": "string",
                    "description": (
                        "这张分镜的简短标题（中文，4-10字，概括画面内容/情绪），"
                        "如「蜷缩抱吉他自闭」「天台黄昏独奏」。你在对话里已经清楚这张要拍什么，直接凝练成一个标题。"
                    ),
                },
            },
            "required": ["atmosphere", "scene", "pose", "composition", "orientation"],
        },
    },
]


def _build_system(project: dict, shot: dict, shot_refs: list[dict] | None = None,
                  selected_ref_ids: list[str] | None = None, reply_lang: str = "zh") -> str:
    char_data   = project.get("character_data", {})
    char_bg     = char_data.get("characterBackground", {})
    if not isinstance(char_bg, dict): char_bg = {}
    world_ws    = project.get("world", {}).get("worldSetting", {})
    if not isinstance(world_ws, dict): world_ws = {}
    visual_spec = project.get("visual_spec", {})

    char_name   = char_data.get("character", "未知角色")
    series_name = project.get("series", "")
    vs_text     = visual_spec.get("zh", "") if isinstance(visual_spec, dict) else str(visual_spec)

    lang = _LANG.get(reply_lang, "中文")
    lines = [
        "你是一个懂拍摄策划的动漫创意搭档，和用户一起把这张参考图【一起构思出来】——"
        "不是拿一张问卷让他逐项填，而是像一个有想法的策划在陪他聊。",
        f"【回复语言】始终使用{lang}回复用户，不要混用其他语言。",
        "",
        "【每一轮怎么说话 · 三段式，但要短】",
        "每轮回复【总共 2-3 句话、不超过 70 字】，自然连成一段，不要写成 1/2/3 列表，也不要长篇铺陈：",
        "① 接住：一句接住用户刚才的选择（别无视它直接问下一个）。",
        "② 想象：半句到一句，用角色性格点出这个选择的画面感或表现了她哪一面（让人觉得你在一起想，不是收集信息）。",
        "③ 引导：一句用【建议/邀请】语气把话题带到下一层，不要审问。",
        "  反例（审问，禁止）：「那她在干嘛？凝视窗外 / 喝茶 / 写歌词，你想要哪种？」",
        "  正例（简短构思）：「安静独处很像澪内向的一面。先别急着定镜头——这一刻是排练后她独自留下，还是趁没人悄悄写歌词？」",
        "- 宁可短、别啰嗦；一次只推进一层；用户也可以随时直接打字，顺着他写的接。",
        "",
        "【构思漏斗 · 五层，逐层收窄，别跳层也别过早定死细节】",
        "1. 大方向：想表现角色的哪一类内容/哪一面（如 舞台演出 / 校园日常 / 社团排练 / 安静独处）。",
        "2. 具体情节 narrative：这张具体【发生了什么】、她正处在事件的哪个时刻——是一个可想象的微型情节，"
        "不是单纯动作。如「排练结束后其他人都走了，她独自留下」而不是「弹贝斯」。",
        "3. 场景设定 setting：这个情节在【哪里、什么时间、环境什么状态、有哪些关键物件】。"
        "如「放学后的部室，夕阳照进来，同伴暂时离开」。这一层【只定环境，不要定姿势/表情/景别】。",
        "4. 人物表演 performance：到这里才定她此刻的【状态/动作/表情/情绪】——"
        "如「短暂走神、若有所思」还是「带一点不愿被发现的失落」。也可以顺带问这张更想突出人物、氛围还是互动。",
        "5. 摄影表达 photography：最后才是【景别/画幅】。这一层【绝对不要开放式一问一答】——"
        "你根据前面直接给【一个】具体建议（如 突出人物→近景·竖图；突出氛围→全身·横图；机位默认平视），"
        "一句话说完就停，等用户操作。系统会在你下面自动显示控件按钮（就这样生成 / 特写 / 近景 / 半身 / 全身 / 横图 / 竖图），"
        "所以你【不要在正文里写这些选项文字，也不要问『你想怎么调/还有别的机位想法吗』这类开放问题】。",
        "- 【关键】第 3 层只定场景，动作/表情留到第 4 层，景别/画幅留到第 5 层——别在场景那步就把姿势表情锁死。",
        "- 用户在摄影阶段点了某个景别/画幅（如「特写」「横图」）→ 只回【一句】这样改会怎样，其余不变，然后停，等他继续调或生成。别再抛新问题。",
        "- 用户确认生成（「可以」「就这样」「生成」等）→ 调用 generate_image。",
        "  外貌服装由项目数据自动带入，你只填 atmosphere/scene/pose/composition/orientation（画幅按第5层）。",
        "- 用户中途已经把画面说得很清楚，可以跳层，别机械走满五层。",
        "- 禁止在用户确认前调用 generate_image；用户提修改请求（「能改成xxx吗」）≠ 确认，先复述新方案再等确认。",
        "- 【通用】任何时候都不要把快捷选项的文字写进你的回复正文（选项由系统单独展示成按钮）。",
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
        lines.append(
            "★ 上面的【备注】是用户在项目级已经和你聊定的交接内容（场景/画面/氛围/光线等）。"
            "请【直接采纳、别把里面已经写明的再从头问一遍】——顺着它往下推进，只补它没覆盖的那几层"
            "（比如备注已给了场景和氛围，你就直接从表情/构图这类还没定的细节聊起）。"
            "★ 别复述备注、别说『我收到了 / 这张是想拍…』这类开场白——用户刚点进来当然知道自己选了什么，"
            "直接顺着已知方向问下一个还没定的细节就好，就像你俩本来就在聊这张一样自然。"
        )

    # ── r-node context ────────────────────────────────────────────
    _type_zh = {
        "pose": "动作姿势", "background": "背景环境",
        "weapon": "武器道具", "costume": "服装",
        "lighting": "打光/机位", "expression": "表情",
    }
    if shot_refs:
        pending = [r for r in shot_refs if r.get("status") == "pending_type"]
        ready   = [r for r in shot_refs if r.get("status") == "ready"]
        if pending:
            lines += ["", "═══ 待分类参考图（用户已上传，在画布上）═══"]
            lines.append("⚠️ 这些图已经上传到画布上了，不要让用户再发图。直接问用户「这张图你想参考哪个方面」，确认后调用 classify_ref。")
            for r in pending:
                lines.append(f"- ref_id={r['id']}（待分类）")
        if ready:
            lines += ["", "═══ 可用参考图（已处理）═══"]
            for r in ready:
                lines.append(f"- ref_id={r['id']} 类型={_type_zh.get(r['type'], r['type'])}")

    if selected_ref_ids:
        lines += ["", "═══ 本次用户框选的参考图 ═══"]
        lines.append("用户主动框选了这些图，说明他想用它们参考。如果是待分类状态，先问类型再调用 classify_ref；如果已 ready，生成时填入 ref_ids。")
        sel_map = {r["id"]: r for r in (shot_refs or [])}
        for rid in selected_ref_ids:
            r = sel_map.get(rid)
            if r:
                status = r.get("status", "unknown")
                rtype  = _type_zh.get(r.get("type") or "", r.get("type") or "未分类")
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
    framing: dict | None = None,
    reply_lang: str = "zh",
) -> dict:
    """
    Process one shot-level chat message.

    Returns:
        { reply: str, generating: bool, prompt_parts: dict | None,
          classify_ref: dict | None }
    """
    system   = _build_system(project, shot, shot_refs, selected_ref_ids, reply_lang)
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
        from services.shot_params import normalize as _norm_params
        captured["params"] = _norm_params(inp.get("params") or {})
        # The camera panel's explicit 景别/画幅/机位 are authoritative: force them
        # into the framing fields + params so the LLM can't quietly substitute its
        # own earlier recommendation. (Deterministic mapping = same one refine uses.)
        if framing:
            from services import shot_params as _sp
            shot_v, aspect_v, angle_v = framing.get("shot"), framing.get("aspect"), framing.get("angle")
            parts = captured["prompt_parts"]
            if aspect_v in _sp._ASPECT_TO_ORIENTATION:
                parts["orientation"] = _sp._ASPECT_TO_ORIENTATION[aspect_v]
            frag = ". ".join(x for x in (_sp._SHOT_EN.get(shot_v), _sp._ANGLE_EN.get(angle_v)) if x)
            if frag:
                parts["composition"] = frag + ". Frame so the character stays the clear visual focus."
            for k, v in (("shot", shot_v), ("aspect", aspect_v), ("angle", angle_v)):
                if v:
                    captured["params"][k] = v
        if inp.get("title"):
            captured["title"] = str(inp["title"]).strip()
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
        max_tokens=400,
    )

    generating = captured.get("prompt_parts") is not None

    # Quick-reply chips: a dedicated forced-tool fast-model call, given the full
    # conversation + the assistant's just-produced reply. Skipped while generating
    # an image or handling a ref-classification (no chips needed those turns).
    options: list[str] = []
    camera: dict | None = None
    stage = "chat"
    if not generating and not captured.get("classify_ref") and result["text"].strip():
        if _is_camera_phase(result["text"]):
            # Photography step → frontend shows a direct-control camera panel
            # (景别/画幅/机位) instead of chat chips; no chips, structured suggestion.
            stage = "camera"
            camera = _extract_camera_suggestion(result["text"])
        else:
            convo = messages + [{"role": "assistant", "content": result["text"]}]
            options = _suggest_options(project, convo, reply_lang)

    return {
        "reply":        result["text"],
        "options":      options,
        "stage":        stage,
        "camera":       camera,
        "generating":   generating,
        "prompt_parts": captured.get("prompt_parts"),
        "params":       captured.get("params"),
        "title":        captured.get("title"),
        "classify_ref": captured.get("classify_ref"),
    }
