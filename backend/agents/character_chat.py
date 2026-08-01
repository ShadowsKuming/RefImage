"""
tools/character_chat.py — Multi-turn character profile chat agent

Implements the Step 2 AI assistant: a conversational agent that builds a
structured character profile by searching the web and calling update_profile.

Tool design (two-tool pattern):
  web_search     — executor tool: called by the agent, result fed back in context
  update_profile — passthrough tool: not executed here; its input IS the profile
                   JSON that gets returned to the caller

Agentic loop strategy (see llm.py for details):
  - Turn 0 uses tool_choice="auto" so casual chat messages don't force a search
  - Turns 1+ use tool_choice="required" to keep the search loop running
  - Loop exits when update_profile is called (no more executor calls)

Hallucination guardrails baked into the system prompt:
  - Search results > training data (stated explicitly)
  - Ambiguous/unknown characters must ask for clarification, never guess
  - update_profile forbidden when multiple candidates found
  - key_events must come from search results, not inference
"""
import json
import re
from tools.llm import call_agent, call
from tools.search import web_search as _web_search
import tools.vision as vision

_LANG_NAMES = {"zh": "中文", "en": "English", "ja": "日本語", "pt": "Português"}


SYSTEM_PROMPT = """你是一个动漫/游戏/影视角色档案助手。

【信息来源优先级】
搜索结果 > 训练数据。具体事实（角色关系、剧情事件、组织名称等）必须以搜索结果为准。
搜索结果没有提到的字段才允许用训练数据补全，且要保守填写。

【工具】
- web_search：搜索角色信息，整理档案前先用
- update_profile：更新角色档案

【工作流程：用户提到角色和作品时】
1. web_search 至少3次，覆盖多语言：
   - zh-cn："{角色名} {作品名} 人物介绍 性格 剧情"
   - en："{character name} {series} character profile"
   - ja："{キャラ名} {作品名} キャラクター 性格"
2. 提取具体事实，多源一致优先，有矛盾优先英文/日文 Wiki
3. 调用 update_profile，key_events 必须来自搜索结果，禁止编造

【搜索结果无法确定唯一角色时——禁止强行总结】
如果搜索后出现以下任一情况，不得调用 update_profile，必须直接向用户提问：
- 找到多个同名角色（来自不同作品），无法确认用户指的是哪一个
- 用户只给了绰号/称谓（如"会长""主角""大姐"）但没说作品名
- 搜索结果互相矛盾且无法判断哪个可信
提问方式：简洁说明找到了哪几个候选，请用户告知作品名或其他区分信息。

【用户纠正时】直接调用 update_profile 更新，不需要重新搜索。

【语气——非常重要】
你是在和用户轻松聊天，不是在写报告。禁止"识别结果显示""根据分析""系统判断"这类机械措辞；
多用第一人称口语，比如"我看了看""我觉得""应该是"。可以自然地用语气词（呀/啦/呢/哦）和偶尔一个颜文字
（比如 (｡•ᴗ•｡) 、(≧∇≦)ﾉ、(´･ω･`)）让对话有温度，但不要每句话都加，保持自然不做作。

【回复风格——非常重要】
每次调用 update_profile，你必须在工具调用的同时写一句口语化的中文回复。
- 首次建档：报角色全名，简单说一句作品是什么。例如"找到了，会长是樱野玖璃梦，来自《学生会的一己之见》，已整理好档案。"
- 用户纠正：直接确认改了什么。例如"嗯对，成绩那里改了，她是靠人气不是成绩当上会长的。"
- 禁止说"档案已整理好，请查看右侧确认信息"这类套话。
- 不需要调用工具时：直接聊天回应，简洁自然。"""


# ── Tool schemas (Anthropic canonical format) ─────────────────────────────────

WEB_SEARCH_TOOL = {
    "name": "web_search",
    "description": "搜索动漫/游戏/影视角色和作品的相关信息。支持多语言搜索。",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键词"},
            "lang":  {"type": "string", "enum": ["zh-cn", "en", "ja", "pt"], "description": "搜索语言：zh-cn中文、en英文、ja日文、pt葡萄牙文"},
        },
        "required": ["query", "lang"],
    },
}

# update_profile is a passthrough tool — its structured input becomes the profile.
# The schema enforces the exact shape stored in context/character.json + world.json.
UPDATE_PROFILE_TOOL = {
    "name": "update_profile",
    "description": "更新角色档案。当获取到角色信息或用户修正档案内容时调用。",
    "input_schema": {
        "type": "object",
        "properties": {
            "character": {"type": "string"},
            "series":    {"type": "string"},
            "worldSetting": {
                "type": "object",
                "properties": {
                    "genre":    {"type": "string", "description": "作品类型，如：少女漫画·音乐剧情"},
                    "era":      {"type": "string", "description": "故事时代背景"},
                    "timeline": {"type": "string", "description": "一句话说明故事发生的时间地点，如：故事发生于2000年代初的东京"},
                    "tone": {
                        "type": "object",
                        "properties": {
                            "visual":    {"type": "string", "description": "视觉风格，如：朋克都市、清新校园"},
                            "narrative": {"type": "string", "description": "叙事风格，如：现实主义、热血少年"},
                            "emotion":   {"type": "string", "description": "情感基调，如：压抑细腻、轻松治愈"},
                        },
                        "required": ["visual", "narrative", "emotion"],
                    },
                    "synopsis":        {"type": "string", "description": "3-4句话概括整部作品的核心故事"},
                    "themes":          {"type": "array", "items": {"type": "string"}, "description": "3-5个核心主题标签"},
                    "iconic_settings": {"type": "array", "items": {"type": "string"}, "description": "作品中的标志性场景地点"},
                },
                "required": ["genre", "era", "timeline", "tone", "synopsis", "themes", "iconic_settings"],
            },
            "characterBackground": {
                "type": "object",
                "properties": {
                    "role":      {"type": "string", "description": "角色定位，如：主角·BLAST主唱"},
                    "age":       {"type": "string"},
                    "backstory": {"type": "string", "description": "2句话概括身世出身，只写原生背景不写剧情发展"},
                    "personality": {
                        "type": "object",
                        "properties": {
                            "surface":      {"type": "string", "description": "外在表现给他人的印象"},
                            "inner":        {"type": "string", "description": "内心深处真实的情感状态"},
                            "strength":     {"type": "string", "description": "最突出的性格优点"},
                            "weakness":     {"type": "string", "description": "最明显的性格弱点"},
                            "core_desire":  {"type": "string", "description": "内心最渴望得到的东西"},
                            "fear":         {"type": "string", "description": "最深的恐惧或不安"},
                        },
                        "required": ["surface", "inner", "strength", "weakness", "core_desire", "fear"],
                    },
                    "emotional_range": {
                        "type": "object",
                        "properties": {
                            "baseline":       {"type": "string", "description": "日常平静状态下的情绪表现"},
                            "stress":         {"type": "string", "description": "压力下的情绪反应"},
                            "breaking_point": {"type": "string", "description": "情绪崩溃时的表现"},
                            "recovery":       {"type": "string", "description": "如何自我修复和平静"},
                        },
                        "required": ["baseline", "stress", "breaking_point", "recovery"],
                    },
                    "behavior": {
                        "type": "object",
                        "properties": {
                            "speech_style": {
                                "type": "object",
                                "properties": {
                                    "tone":       {"type": "string", "description": "说话语气"},
                                    "volume":     {"type": "string", "description": "音量习惯"},
                                    "humor":      {"type": "string", "description": "幽默风格"},
                                    "vocabulary": {"type": "string", "description": "用词特点"},
                                },
                                "required": ["tone", "volume", "humor", "vocabulary"],
                            },
                            "habits":   {"type": "array", "items": {"type": "string"}, "description": "日常习惯和肢体语言"},
                            "values":   {"type": "array", "items": {"type": "string"}, "description": "核心价值观"},
                            "likes":    {"type": "array", "items": {"type": "string"}, "description": "喜好"},
                            "dislikes": {"type": "array", "items": {"type": "string"}, "description": "厌恶的事物"},
                        },
                        "required": ["speech_style", "habits", "values", "likes", "dislikes"],
                    },
                    "key_events":     {"type": "array", "items": {"type": "string"}, "description": "4-6个作品中真实发生的具体剧情事件"},
                    "iconic_moments": {"type": "array", "items": {"type": "string"}, "description": "3-5个最具代表性的场景或状态，用于拍摄参考"},
                    "relations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name":         {"type": "string"},
                                "relationship": {"type": "string", "description": "关系描述，如：Lover、Best friend、Rival"},
                                "importance":   {"type": "string", "description": "重要程度，如：Life-long love、Family-like、Complicated"},
                            },
                            "required": ["name", "relationship", "importance"],
                        },
                        "description": "重要关系人列表",
                    },
                },
                "required": ["role", "age", "backstory", "personality", "emotional_range", "behavior", "key_events", "iconic_moments", "relations"],
            },
        },
        "required": ["character", "series", "worldSetting", "characterBackground"],
    },
}


# ── Vision pre-identification ─────────────────────────────────────────────────

def _identify_from_image(image_bytes: bytes) -> dict:
    """Ask the vision LLM to guess which character is in the image.
    Returns {"confidence": "single"|"multiple"|"none", "text": <short Chinese description>}.
    confidence lets the caller tell "here's a specific guess to confirm" apart
    from "no guess, just ask the user" — the two need different frontend UI
    (a yes/no confirm chip only makes sense for the former)."""
    b64, media_type = vision.encode_image(image_bytes)
    messages = [{
        "role": "user",
        "content": [
            {
                "type": "image",
                "source": {"type": "base64", "media_type": media_type, "data": b64},
            },
            {
                "type": "text",
                "text": (
                    "这是一张角色参考图。根据图片中角色的外貌特征（发型、发色、服装、配饰等），"
                    "判断这是哪个动漫/游戏/影视作品中的角色。"
                    "严格按下面的 JSON 格式回答，不要输出任何其他内容、不要用 markdown 代码块包裹：\n"
                    '{"confidence": "single", "text": "..."}\n'
                    "confidence 三选一：\n"
                    "  single   —— 能确认唯一角色，text 里说明角色名和所属作品\n"
                    "  multiple —— 有2个左右可能候选，text 里列出候选\n"
                    "  none     —— 无法判断，text 里描述能看到的最显著特征\n"
                    "text 用中文，100字以内。"
                ),
            },
        ],
    }]
    raw = vision.call(messages, "你是一个熟悉动漫、游戏、影视作品的角色识别专家。只输出 JSON。")
    confidence, text = "none", raw
    match = re.search(r"\{.*\}", raw, re.S)
    if match:
        try:
            data = json.loads(match.group(0))
            if data.get("confidence") in ("single", "multiple", "none"):
                confidence = data["confidence"]
            text = data.get("text") or raw
        except Exception:
            pass
    return {"confidence": confidence, "text": text}


# ── Main entry point ──────────────────────────────────────────────────────────

def chat(
    message: str,
    history: list[dict],
    visual_spec: str | None = None,
    current_profile: dict | None = None,
    session_id: str | None = None,
    reply_lang: str = "zh",
) -> dict:
    """
    Process one user message and return an agent reply + optional profile update.

    Args:
        message:         The user's latest message.
        history:         Prior turns as [{ role, content }, ...] for context.
        visual_spec:     Compiled appearance description from Step 1 image analysis.
                         Included so the agent can flag if the uploaded image
                         doesn't match the character being profiled.
        current_profile: The full profile as it exists on the frontend right now,
                         including any manual edits the user made.  Sent on every
                         request so the LLM always works from the live state, not
                         just from chat history.
        reply_lang:      UI locale ('zh'/'en'/'ja') — the agent's conversational
                         reply follows this regardless of what language the user
                         types in; profile data itself stays as extracted (English
                         internally, translated separately for storage/display).

    Returns:
        { reply: str, profile: dict | None, awaiting_confirm: bool }
        profile is non-null only when the agent called update_profile this turn.
        awaiting_confirm is true when this reply is a plain yes/no identity-confirm
        question — single vision candidate, and the profile hasn't been built yet
        this session (covers both the first-turn ask and a later re-ask after the
        user corrects the guess) — the frontend uses it to decide whether a quick
        "yes" chip makes sense, vs an open-ended ask where only free text applies.
    """
    system = SYSTEM_PROMPT + (
        f"\n\n【回复语言】始终使用{_LANG_NAMES.get(reply_lang, '中文')}回复用户，"
        "无论用户用什么语言提问，也不要在回复里混用其他语言。"
    )

    awaiting_confirm = False

    # Vision identification: run once per session on first chat turn, cache in session
    session = None
    if session_id:
        from services import analyze_service
        session = analyze_service.get_session(session_id)
        if session:
            if session.get("char_hint") is None and session.get("first_image"):
                try:
                    session["char_hint"] = _identify_from_image(session["first_image"])
                except Exception:
                    session["char_hint"] = {"confidence": "none", "text": ""}
            char_hint_data = session.get("char_hint") or {"confidence": "none", "text": ""}
            char_hint = char_hint_data.get("text") or ""
            # A single confident vision guess keeps the confirm chip alive across
            # turns, not just turn 1 — a user CORRECTION loops back into ANOTHER
            # plain yes/no re-confirm ask (see the char_hint instructions below:
            # "纠正后...再确认一次"), which also deserves the chip. Only once the
            # profile is actually built does confirmation stop making sense.
            awaiting_confirm = (
                bool(char_hint)
                and char_hint_data.get("confidence") == "single"
                and not session.get("profile_confirmed")
            )
            if char_hint:
                lang_name = _LANG_NAMES.get(reply_lang, '中文')
                system += (
                    f"\n\n【图像视觉识别】你已经看过用户上传的参考图，心里对角色有个初步判断（以下描述本身是中文，"
                    f"仅供你参考图片内容，不代表你的回复语言）：\n{char_hint}\n"
                    f"【重要】第一轮回复必须全程使用{lang_name}，用你自己的话自然地说出来，"
                    "像是刚仔细看完图一样——比如「我仔细看了看，这个角色好像是……」，"
                    "禁止说「识别结果显示」「系统已识别」这类报告式开场白。"
                    "根据判断选择下面其中一种情况：\n"
                    "  - 能确认唯一角色：说出角色名和作品名，反问用户是否正确\n"
                    "  - 有多个可能候选：列出前2个候选，请用户选择\n"
                    "  - 无法判断：说明特征不足以确认，请用户直接告知角色名和作品名\n"
                    "整段回复只问一个问题——确认角色身份是否正确。不要额外插入"
                    "「你是想了解她吗」这类无关的开放式提问，用户在这个系统里的目的已经很明确"
                    "（建立角色拍摄档案），不需要征询。"
                    f"无论你判断依据本身是什么语言，说给用户的这句话都必须是{lang_name}，不要输出中文原文或混用其他语言。"
                    "\n【处理用户回应——务必区分「确认」和「纠正」】\n"
                    "  - 用户【确认】你判断正确（如「对」「没错」「是的」）→ 调用 web_search 核实后 update_profile 建档。\n"
                    "  - 用户【纠正】成了别的角色或作品（如「应该是XX吧」「不对，是XX」）→ 【绝对不要立刻建档】。"
                    "这一轮先调用 web_search 核实纠正后的角色，然后用一句话把纠正后的身份复述给用户再确认一次"
                    f"（如「对，应该是XX，来自《YY》，那我帮你把她的档案整理出来？」），只提问、这一轮不要调用 update_profile。"
                    "等用户对纠正后的身份再次点头，下一轮才调用 update_profile 建档。\n"
                    "禁止在用户对最终身份确认前调用 update_profile。"
                )

    if visual_spec:
        system += (
            f"\n\n用户已上传角色图片，外貌特征如下（供参考）：\n{visual_spec}\n"
            "整理完档案后，如果图片外貌与该角色的已知外貌明显不符（如性别、发色、发型差异很大），"
            "在回复末尾自然地提一句，比如「不过图片里是XX发色，和这个角色通常的形象不太一样，确认是同一角色吗？」。"
            "差异不明显或无法判断时不用提。"
        )

    if current_profile:
        # Remind the agent to treat the live profile as the source of truth and
        # only patch the fields the user explicitly asked to change.
        system += (
            f"\n\n【当前档案】（用户可能已手动修改部分字段）：\n"
            f"{json.dumps(current_profile, ensure_ascii=False)}\n"
            f"调用 update_profile 时必须以此为基础，逐字段保留所有未被用户要求修改的内容，"
            f"只更新用户明确要求改动的字段。"
        )

    messages = history + [{"role": "user", "content": message}]
    result = call_agent(
        messages, system,
        tools=[WEB_SEARCH_TOOL, UPDATE_PROFILE_TOOL],
        tool_executor={"web_search": lambda inp: _web_search(inp["query"], num=8, lang=inp.get("lang", "zh-cn"))},
        max_turns=8,
        max_tokens=4000,
    )

    # Extract the profile from the first update_profile passthrough call (if any)
    profile = None
    for tc in result["tool_calls"]:
        if tc["name"] == "update_profile":
            profile = tc["input"]
            break

    reply = result["text"]

    # gpt-4.1 often omits text content when it calls a tool.  Fall back to a
    # lightweight plain-text call to get a natural conversational reply.
    if not reply and profile:
        char = profile.get("character", "角色")
        prev_json = json.dumps(current_profile, ensure_ascii=False) if current_profile else "无"
        reply = call(
            [{"role": "user", "content": message}],
            f"你是一个动漫角色档案助手。你刚刚把「{char}」的档案整理/更新完了。"
            f"用一句口语化的{_LANG_NAMES.get(reply_lang, '中文')}回复用户刚才的这条消息，"
            f"自然地说你做了什么（比如报角色全名、说你改了什么字段）。"
            f"之前档案：{prev_json}。30字以内，禁止说套话。",
            max_tokens=120,
        )

    # A tool call this turn means the agent already resolved identity — there's
    # nothing left to confirm. Persist that on the session so later turns (now
    # free-form profile chat/edits) never bring the confirm chip back.
    if profile is not None:
        awaiting_confirm = False
        if session is not None:
            session["profile_confirmed"] = True

    return {"reply": reply or "", "profile": profile, "awaiting_confirm": awaiting_confirm}
