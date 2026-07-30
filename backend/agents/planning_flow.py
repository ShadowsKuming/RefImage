"""
agents/planning_flow.py — state-machine-driven planning agent.

Design: CODE owns the skeleton (which state we're in, when to transition, what
field to write). The LLM works only inside the current state's narrow job:
  - parse:   turn the user's free-text answer into a structured value  (slot)
  - say:     phrase the next question warmly + suggest quick-reply options (slot)
  - converse: chat within a topic, staying at the 基调 level (converse)
Because each state's prompt is tiny and focused, the model obeys; because
transitions + recording are code, it can't over-fill or loop.

State kinds:
  slot     — ask → parse answer → record to a field → advance
  menu     — fixed action options; transitions via "__goto:<state>" messages
  converse — open chat within a topic; code wraps after direction is clear

Menu option labels are localized on the FRONTEND from `action`; slot/converse
option labels come from the LLM (already in reply_lang).
"""
import datetime
from services import plan_service, project_service, agent_state_service
from tools.llm import call_with_tools
from config import LLM_PROVIDER, FAST_LLM_MODEL_BY_PROVIDER

_LANG = {"zh": "中文", "en": "English", "ja": "日本語"}
ENTRY = "greet"
MAX_TONE_TURNS = 3


# ── slot recorders (return a short human ack for the next question) ────────────
def _rec_date(pid: str, value: str) -> str:
    v = value or "待定"
    plan_service.update_overview(pid, shoot_date=v)
    return f"拍摄时间：{v}"


def _rec_crew(pid: str, value: str) -> str:
    if value == "found":
        plan_service.update_overview(pid, crew={"photographers": 1, "cosers": 1})
        return "摄影已确定"
    if value == "self":
        plan_service.update_overview(pid, crew={"cosers": 1})
        return "本人自拍 / 三脚架"
    return "摄影：待定"


def _rec_wig(pid: str, value: str) -> str:
    if value == "not_ready":
        plan_service.add_note(pid, title="假发待入", phase="pre", priority="mid")
        return "假发还没到，已记待办"
    return "假发已到位"


def _rec_clothes(pid: str, value: str) -> str:
    if value == "not_ready":
        plan_service.add_note(pid, title="服装道具待准备", phase="pre", priority="mid")
        return "服装道具还没齐，已记待办"
    return "服装道具已就绪"


# ── state registries ──────────────────────────────────────────────────────────
SLOT_STATES: dict[str, dict] = {
    "plan_date": {
        "ask": "先温柔地问用户，这组大概打算什么时候拍（不用具体到某天，说个大致时间/月份也行）",
        "parse": "从用户的话里提取拍摄时间，并【算成具体的年月】：相对说法（'下个月'、'这周末'、'三个月后'）要"
                 "根据下面给的今天日期算成具体年月（如 '2026年8月'、'2026年8月中旬'）；只说了月份没说年份的（'10月2号'）"
                 "补上最近的合适年份；已是具体日期就保留。若用户说还没定/不知道/看情况/随便，输出 '待定'",
        "record": _rec_date, "next": "plan_crew",
    },
    "plan_crew": {
        "ask": "温柔地问用户，这次拍摄的摄影师有没有着落了",
        "parse": "判断用户的摄影安排：已经找到摄影师→'found'；打算自己拍/用三脚架→'self'；"
                 "还没找到/不确定→'none'。只输出这三个词之一",
        "record": _rec_crew, "next": "plan_wig",
    },
    "plan_wig": {
        "ask": "轻松地问用户，假发到手了吗",
        "parse": "判断假发准备情况：已经到手/买了/有了→'ready'；还没入/没买/没到→'not_ready'。只输出这两个词之一",
        "record": _rec_wig, "next": "plan_clothes",
    },
    "plan_clothes": {
        "ask": "接着问用户，衣服和道具准备好了吗",
        "parse": "判断服装道具准备情况：都准备好了/齐了→'ready'；还没做好/没买/还缺→'not_ready'。只输出这两个词之一",
        "record": _rec_clothes, "next": "plan_wrap",
    },
}

CONVERSE_STATES: dict[str, dict] = {
    "tone_feel": {"topic": "这组作品想表达什么、整体的情绪基调和气质", "covers": "feel"},
    "tone_take": {"topic": "用户对这个角色的独特理解、核心解读", "covers": "take"},
}

# menu options carry an `action` (frontend localizes the label) and optionally a
# `value` = the "__goto:<state>" message the frontend sends back to transition.
MENU_STATES: dict[str, dict] = {
    "greet": {
        "intent": "跟用户打个招呼：看到 ta 这次想拍的是 {char}，说一句温柔简短的开场，别多说别的",
        "options": [{"action": "go_shot"}, {"action": "chat", "value": "__goto:fork"}],
    },
    "fork": {
        "intent": "轻松地问用户：想从哪儿聊起呢",
        "topics": True,
    },
    "plan_wrap": {
        "intent": "用一句话说你大概了解 ta 的准备情况了，语气轻松，然后把选择权交回给 ta",
        "options": [{"action": "go_shot"}, {"action": "switch", "value": "__goto:fork"}],
    },
    "tone_wrap": {
        "intent": "用一句话简短复述你俩刚聊出来的方向/调子，然后把选择权交回给 ta",
        "options": [{"action": "go_shot"}, {"action": "switch", "value": "__goto:fork"}],
    },
    "midstage": {   # project mid-stage check-in; reply rendered contextually by _resume.
        # Only a "new shot" chip — to chat, the user just types (→ open free chat).
        # No topic-fork option: re-opening onboarding topics mid-project feels like a regression.
        "intent": "跟用户打个招呼，简短温柔",
        "options": [{"action": "new_shot"}],
    },
}
_TOPIC_OPT = {
    "feel": {"action": "topic_feel", "value": "__goto:tone_feel"},
    "plan": {"action": "topic_plan", "value": "__goto:plan_date"},
    "take": {"action": "topic_take", "value": "__goto:tone_take"},
}
# entering these states marks a topic as covered (so the fork won't re-offer it)
_COVERS = {"plan_date": "plan", "tone_feel": "feel", "tone_take": "take"}


# ── LLM helpers (structured, fast model, forced tool) ─────────────────────────
_PARSE_TOOL = {
    "name": "submit_value", "description": "提交从用户回答里提取出的结构化值。",
    "input_schema": {"type": "object", "properties": {"value": {"type": "string"}}, "required": ["value"]},
}
_SAY_TOOL = {
    "name": "say", "description": "你对用户说的一句话，加几个快捷回答建议。",
    "input_schema": {"type": "object", "properties": {
        "reply": {"type": "string", "description": "温柔、只问这一件事、≤2句"},
        "options": {"type": "array", "items": {"type": "string"},
                    "description": "2-4 个用户此刻最可能的快捷回答，第一人称、短(≤10字)，留一个'还没定/不确定'类"},
    }, "required": ["reply", "options"]},
}
_CONVERSE_TOOL = {
    "name": "chat", "description": "你对用户说的话 + 建议回答 + 是否该收尾。",
    "input_schema": {"type": "object", "properties": {
        "reply": {"type": "string", "description": "温柔、≤2句，接住用户上一句再往下带"},
        "options": {"type": "array", "items": {"type": "string"}, "description": "2-4 个用户可能的回应，短"},
        "done": {"type": "boolean", "description": "整组方向已清晰(能一句话概括)时为 true，这轮就收尾"},
    }, "required": ["reply", "options", "done"]},
}


def _fast():
    return FAST_LLM_MODEL_BY_PROVIDER.get(LLM_PROVIDER)


def _parse_value(user_message: str, parse_intent: str) -> str:
    today = datetime.date.today().isoformat()
    system = f"你从用户的一句话里提取信息。（今天是 {today}）{parse_intent}。只调用 submit_value 提交，别多说。"
    try:
        res = call_with_tools([{"role": "user", "content": user_message}], system,
                              [_PARSE_TOOL], max_tokens=80, force_tool="submit_value", model=_fast())
        call = next((c for c in res.get("tool_calls", []) if c.get("name") == "submit_value"), None)
        if call:
            return str(call.get("input", {}).get("value", "")).strip()
    except Exception:
        pass
    return ""


_GENDER_WORD = {"female": {"zh": "女生", "en": "female", "ja": "女性"},
                "male": {"zh": "男生", "en": "male", "ja": "男性"}}
_PRONOUN = {"female": {"zh": "她", "en": "she/her", "ja": "彼女"},
            "male": {"zh": "他", "en": "he/him", "ja": "彼"}}


def _detect_gender(project: dict) -> str | None:
    """Character gender is stated in the extracted visual_spec (e.g. '妆容: 女性…')."""
    vs = project.get("visual_spec") or {}
    text = (vs.get("zh", "") if isinstance(vs, dict) else str(vs))
    low = ((vs.get("en", "") if isinstance(vs, dict) else "")).lower()
    if "女性" in text or "女生" in text or "female" in low:
        return "female"
    if "男性" in text or "男生" in text or ("male" in low and "female" not in low):
        return "male"
    return None


def _gender_hint(project: dict, char_name: str, reply_lang: str) -> str:
    g = _detect_gender(project)
    if not g:
        return ""
    word = _GENDER_WORD[g].get(reply_lang, _GENDER_WORD[g]["zh"])
    pron = _PRONOUN[g].get(reply_lang, _PRONOUN[g]["zh"])
    return f"（{char_name} 是{word}，提到 ta 时务必用「{pron}」，绝不能弄错性别。）"


def _persona(char_name: str, gender_hint: str = "") -> str:
    return (f"你是用户的拍摄搭档——温柔、靠谱，像走在 ta 身边的朋友。这次拍的角色是 {char_name}。{gender_hint}")


def _say(char_name: str, ask_intent: str, reply_lang: str, ack: str | None = None,
         gender_hint: str = "") -> tuple[str, list[str]]:
    lang = _LANG.get(reply_lang, "中文")
    ackline = f"你刚帮用户记下了：{ack}。先用半句话自然地确认一下，再问下一件事。\n" if ack else ""
    system = (f"{_persona(char_name, gender_hint)}\n{ackline}你现在唯一要做的：{ask_intent}。\n"
              f"用{lang}回复。reply 只说这一件事、≤2句、口语温柔，别铺垫客套、别一次问两件事。\n"
              f"options 给 2-4 个用户此刻最可能点的快捷回答（第一人称、短），留一个'还没定/不确定'类。整理好调用 say。")
    try:
        res = call_with_tools([{"role": "user", "content": "（请开口）"}], system,
                              [_SAY_TOOL], max_tokens=300, force_tool="say", model=_fast())
        call = next((c for c in res.get("tool_calls", []) if c.get("name") == "say"), None)
        if call:
            reply = str(call.get("input", {}).get("reply", "")).strip()
            opts = [str(o).strip() for o in (call.get("input", {}).get("options") or []) if str(o).strip()][:4]
            return reply, opts
    except Exception:
        pass
    return "", []


def _menu_reply(char_name: str, intent: str, reply_lang: str, gender_hint: str = "") -> str:
    lang = _LANG.get(reply_lang, "中文")
    system = (f"{_persona(char_name, gender_hint)}\n你现在要做的：{intent}。"
              f"用{lang}回复，≤2句、温柔口语，只输出你对用户说的话本身，别加选项、别加引号。")
    try:
        from tools.llm import call as _call
        return _call([{"role": "user", "content": "（请开口）"}], system, max_tokens=160).strip()
    except Exception:
        return ""


def _converse(cfg: dict, char_name: str, history: list[dict], user_message: str | None,
              reply_lang: str, gender_hint: str = "") -> tuple[str, list[str], bool]:
    lang = _LANG.get(reply_lang, "中文")
    opening = user_message is None
    task = (f"温柔地邀请用户聊聊「{cfg['topic']}」，问一个开放的问题" if opening
            else f"接住用户刚说的，继续和 ta 聊「{cfg['topic']}」")
    system = (
        f"{_persona(char_name, gender_hint)}\n你在和用户聊【{cfg['topic']}】——这是【项目级基调】对话。\n"
        f"你的任务：{task}。\n"
        f"★停在方向和气质这一层：帮 ta 把整组的情绪基调/核心解读说清楚就够了。"
        f"【绝不】设计具体分镜、别给具体镜头/姿势/机位选项，那是分镜编辑器的事。\n"
        f"用{lang}回复。reply ≤2句、温柔、先接住再往下带。options 给 2-4 个 ta 可能的回应（短）。\n"
        f"当整组方向已经清晰（你能用一句话概括出基调）时，done=true，这轮 reply 就简短复述一下调子收个尾；"
        f"{'开场这轮 done 必须为 false。' if opening else '否则 done=false。'} 整理好调用 chat。")
    msgs = []
    for h in history[-6:]:
        msgs.append({"role": "user" if h.get("role") == "user" else "assistant", "content": h.get("text", "")})
    msgs.append({"role": "user", "content": user_message or "（请开口）"})
    try:
        res = call_with_tools(msgs, system, [_CONVERSE_TOOL], max_tokens=400, force_tool="chat", model=_fast())
        call = next((c for c in res.get("tool_calls", []) if c.get("name") == "chat"), None)
        if call:
            inp = call.get("input", {})
            reply = str(inp.get("reply", "")).strip()
            opts = [str(o).strip() for o in (inp.get("options") or []) if str(o).strip()][:4]
            done = bool(inp.get("done")) and not opening
            return reply, opts, done
    except Exception:
        pass
    return "", [], False


def _chip(label: str, value: str | None = None, action: str | None = None) -> dict:
    o = {"label": label, "value": value if value is not None else label}
    if action:
        o["action"] = action
    return o


def _shot_stats(project: dict) -> dict:
    shots = project.get("shots", []) or []
    done = [s for s in shots if s.get("completed")]
    last = (done[-1] if done else (shots[-1] if shots else {})).get("title", "")
    return {"total": len(shots), "completed": len(done), "last_title": last}


def _midstage(char_name: str, stats: dict, just_completed: bool, gender_hint: str,
              reply_lang: str) -> tuple[str, list[dict]]:
    lang = _LANG.get(reply_lang, "中文")
    praise = "用户刚完成了一个新分镜——先由衷地、具体地夸一句！" if just_completed else ""
    last = f"最新的分镜是「{stats['last_title']}」。" if stats["last_title"] else ""
    system = (
        f"{_persona(char_name, gender_hint)}\n{praise}\n"
        f"当前进度：这个项目一共 {stats['total']} 个分镜，其中 {stats['completed']} 个已完成。{last}\n"
        f"你要做的：{'先夸，再' if just_completed else ''}用一句话温柔地小结现在的进度，"
        f"然后问用户想继续构思下一个分镜、还是跟你聊聊 / 探讨点什么。用{lang}回复，≤3句、口语温柔，别啰嗦。"
    )
    try:
        from tools.llm import call as _call
        reply = _call([{"role": "user", "content": "（请开口）"}], system, max_tokens=220).strip()
    except Exception:
        reply = ""
    return reply, _menu_options("midstage", [])


def _resume(project: dict, project_id: str, char_name: str, gh: str, reply_lang: str,
            st: dict, history: list[dict]) -> dict:
    """Mid-stage check-in, kept in sync with the project via a signature (shot count
    + completed count). A NEW completion appends a fresh celebration; any other
    change (e.g. a deletion) silently REPLACES the last check-in with current numbers
    so it never goes stale; no change → no-op (empty reply)."""
    stats = _shot_stats(project)
    acked = int(st.get("acked_completed", 0))
    sig = [stats["total"], stats["completed"]]
    new_completion = stats["completed"] > acked
    changed = st.get("last_sig") != sig
    if not new_completion and not changed and history:
        return {"reply": "", "options": st.get("last_options", []),
                "state": st.get("state") or "open", "plan": None, "replace": False}

    reply, options = _midstage(char_name, stats, new_completion, gh, reply_lang)
    # Replace our own last check-in when it's just a refresh (edit/delete), not a
    # fresh completion worth a new celebration.
    replace = bool(history) and history[-1].get("checkin") and not new_completion
    agent_state_service.save_state(project_id, {
        "state": "midstage", "covered": st.get("covered", []), "tone_turn": 0,
        "acked_completed": stats["completed"], "last_sig": sig,
        "last_reply": reply, "last_options": options,
    })
    msg = {"role": "agent", "text": reply, "options": options, "checkin": True}
    hist = list(history)
    if replace:
        hist[-1] = msg
    else:
        hist.append(msg)
    project_service.save_chat_history(project_id, hist)
    return {"reply": reply, "options": options, "state": "midstage", "plan": None, "replace": replace}


def _menu_options(state: str, covered: list[str]) -> list[dict]:
    if state == "fork":
        opts = [dict(_TOPIC_OPT[t]) for t in ("feel", "plan", "take") if t not in covered]
        if not opts:
            opts = [{"action": "go_shot"}]
        return opts
    return [dict(o) for o in MENU_STATES[state]["options"]]


# ── engine ────────────────────────────────────────────────────────────────────
def run_step(project_id: str, message: str, reply_lang: str = "zh") -> dict:
    """One turn. Returns { reply, options:[{label?,value?,action?}], state, plan? }."""
    project = project_service.get_project(project_id)
    char_name = project.get("character_data", {}).get("character", "这个角色")
    gh = _gender_hint(project, char_name, reply_lang)
    history = list((project.get("plan") or {}).get("chat_history") or [])
    st = agent_state_service.load_state(project_id)
    cur = st.get("state")
    covered = list(st.get("covered", []))
    tone_turn = int(st.get("tone_turn", 0))
    plan_dirty = False
    ack = None
    inline: tuple[str, list[dict]] | None = None

    # Mid-stage check-in: explicit resume, or first entry into a project that
    # already has shots. Congratulates on new completions + summarizes progress.
    if message == "__resume" or (cur is None and project.get("shots")):
        return _resume(project, project_id, char_name, gh, reply_lang, st, history)

    # 1. process the current turn → decide next state
    if cur is None:
        nxt = ENTRY   # brand-new project (no shots) → onboarding greeting
    elif message.startswith("__goto:"):
        nxt = message.split(":", 1)[1]
    elif cur == "open":
        nxt = "open"
    elif cur in SLOT_STATES:
        cfg = SLOT_STATES[cur]
        ack = cfg["record"](project_id, _parse_value(message, cfg["parse"]))
        plan_dirty = True
        nxt = cfg["next"]
    elif cur in CONVERSE_STATES:
        tone_turn += 1
        r, o, done = _converse(CONVERSE_STATES[cur], char_name, history, message, reply_lang, gh)
        if done:
            # LLM chose to wrap — its reply is already a summary; attach wrap menu.
            nxt = "tone_wrap"
            inline = (r, _menu_options("tone_wrap", covered))
        elif tone_turn >= MAX_TONE_TURNS:
            # forced by turn cap — let tone_wrap render a proper summary reply.
            nxt = "tone_wrap"
        else:
            nxt = cur
            inline = (r, [_chip(x) for x in o])
    elif cur in MENU_STATES:
        # user typed free text instead of picking → drop into free chat
        nxt = "open" if message.strip() else cur
    else:
        nxt = cur

    if nxt in _COVERS and _COVERS[nxt] not in covered:
        covered.append(_COVERS[nxt])

    # 2. produce output for nxt (unless a converse turn already did)
    if inline is not None:
        reply, options = inline
    elif nxt == "open":
        if message.strip():
            from agents import planning_chat
            hist_llm = [{"role": "user" if h.get("role") == "user" else "assistant",
                         "content": h.get("text", "")} for h in history]
            res = planning_chat.chat(message, hist_llm, project, project_id, reply_lang)
            reply = res.get("reply", "")
            options = [_chip(o) for o in (res.get("options") or [])]
            if res.get("plan") is not None:
                plan_dirty = True
            # The AI decided the user's ready to make a specific shot → surface a
            # button that creates it (seeded with the concept) and jumps to the editor.
            shot = res.get("proposed_shot")
            if shot:
                title = shot.get("title") or "这个分镜"
                concept = shot.get("concept") or title
                options = [{"label": f"🎬 去构思「{title}」", "value": concept, "action": "make_shot"}] + options
        else:
            reply = _menu_reply(char_name, "跟用户打个招呼，说你随时能帮 ta 一起规划这次拍摄，简短温柔", reply_lang, gh)
            options = []
    elif nxt in SLOT_STATES:
        reply, opts = _say(char_name, SLOT_STATES[nxt]["ask"], reply_lang, ack=ack, gender_hint=gh)
        options = [_chip(o) for o in opts]
    elif nxt in CONVERSE_STATES:
        tone_turn = 0
        reply, opts, _ = _converse(CONVERSE_STATES[nxt], char_name, history, None, reply_lang, gh)
        options = [_chip(o) for o in opts]
    elif nxt in MENU_STATES:
        intent = MENU_STATES[nxt]["intent"].format(char=char_name)
        reply = _menu_reply(char_name, intent, reply_lang, gh)
        options = _menu_options(nxt, covered)
    else:
        reply, options = "", []

    st = {"state": nxt, "covered": covered, "tone_turn": tone_turn,
          "last_reply": reply, "last_options": options}
    agent_state_service.save_state(project_id, st)

    if message:
        history.append({"role": "user", "text": message})
    history.append({"role": "agent", "text": reply, "options": options})
    project_service.save_chat_history(project_id, history)

    return {
        "reply": reply, "options": options, "state": nxt,
        "plan": plan_service.load_plan_data(project_id) if plan_dirty else None,
    }
