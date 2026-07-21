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
from tools.llm import call_agent, call
from tools.search import web_search as _web_search
import tools.vision as vision


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
            "lang":  {"type": "string", "enum": ["zh-cn", "en", "ja"], "description": "搜索语言：zh-cn中文、en英文、ja日文"},
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

def _identify_from_image(image_bytes: bytes) -> str:
    """Ask the vision LLM to guess which character is in the image.
    Returns a short Chinese description of the identification result."""
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
                    "你能判断这是哪个动漫/游戏/影视作品中的角色吗？"
                    "如果能确认，请说明角色名和所属作品；如果有多个可能，列出前2个候选；"
                    "如果实在无法判断，描述能看到的最显著特征。"
                    "用中文回答，100字以内。"
                ),
            },
        ],
    }]
    return vision.call(messages, "你是一个熟悉动漫、游戏、影视作品的角色识别专家。")


# ── Main entry point ──────────────────────────────────────────────────────────

def chat(
    message: str,
    history: list[dict],
    visual_spec: str | None = None,
    current_profile: dict | None = None,
    session_id: str | None = None,
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

    Returns:
        { reply: str, profile: dict | None }
        profile is non-null only when the agent called update_profile this turn.
    """
    system = SYSTEM_PROMPT

    # Vision identification: run once per session on first chat turn, cache in session
    if session_id:
        from services import analyze_service
        session = analyze_service.get_session(session_id)
        if session:
            if session.get("char_hint") is None and session.get("first_image"):
                try:
                    session["char_hint"] = _identify_from_image(session["first_image"])
                except Exception:
                    session["char_hint"] = ""
            char_hint = session.get("char_hint") or ""
            if char_hint:
                system += (
                    f"\n\n【图像视觉识别】系统已对用户上传的参考图进行了初步识别：\n{char_hint}\n"
                    "【重要】在第一轮回复时，先把识别结果告诉用户并请求确认，例如：\n"
                    "  「图片里看起来是XXX（《作品名》），对吗？」\n"
                    "  或「从图片特征看，这可能是XXX或YYY，请问是哪个？」\n"
                    "  或「图片特征不太好确认，能告诉我是哪个角色吗？」\n"
                    "用户确认或纠正后，再调用 web_search 搜索建档。"
                    "禁止在用户确认前就调用 web_search 或 update_profile。"
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
            f"用一句口语化中文回复用户刚才的这条消息，自然地说你做了什么（比如报角色全名、说你改了什么字段）。"
            f"之前档案：{prev_json}。30字以内，禁止说套话。",
            max_tokens=120,
        )

    return {"reply": reply or "", "profile": profile}
