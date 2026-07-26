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
from services import plan_service, wardrobe_service, moments_service

STORAGE_ROOT = Path(__file__).parent.parent / "storage" / "projects"

_LANG_NAMES = {"zh": "中文", "en": "English", "ja": "日本語"}
_PHASE_LABELS = {"pre": "拍摄前", "onsite": "拍摄当天", "other": "其他"}
_PRIO_LABELS = {"high": "高", "mid": "中", "low": "低"}

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


# ── Plan mutation tools (add / remove only — never a whole-list rewrite) ───────
# Each item's id (shown in the 拍摄计划总表 section of the system prompt) is the
# handle for removal. To "edit" an item, remove it by id then add the new one.

_PLAN_TOOLS = [
    {
        "name": "update_overview",
        "description": "更新拍摄计划总览：主题 theme、拍摄日期 shoot_date、参与人数 crew。只传你要改动的字段，未传的保持不变。",
        "input_schema": {
            "type": "object",
            "properties": {
                "theme":      {"type": "string", "description": "拍摄主题"},
                "shoot_date": {"type": "string", "description": "拍摄日期，如 2026/08/15"},
                "crew": {
                    "type": "object", "description": "参与人数（各角色人数）",
                    "properties": {
                        "photographers": {"type": "integer", "description": "摄影人数"},
                        "cosers":        {"type": "integer", "description": "coser 人数"},
                        "logistics":     {"type": "integer", "description": "后勤人数"},
                    },
                },
            },
        },
    },
    {
        "name": "add_equipment",
        "description": "往设备清单添加一项设备。",
        "input_schema": {
            "type": "object",
            "properties": {
                "name":     {"type": "string", "description": "设备名称，如 85mm 镜头"},
                "required": {"type": "boolean", "description": "是否必要设备，默认 true；可选设备传 false"},
                "desc":     {"type": "string", "description": "备注，如 适合特写"},
                "category": {"type": "string",
                             "enum": ["camera", "lens", "light", "reflector", "support",
                                      "power", "charger", "audio", "backdrop", "misc"],
                             "description": "设备分类"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "remove_equipment",
        "description": "按 id 从设备清单删除一项设备（id 形如 eq_xxxx，见拍摄计划总表）。修改某项设备＝先删后加。",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "设备 id"}},
            "required": ["id"],
        },
    },
    {
        "name": "add_note",
        "description": "往注意事项添加一条。",
        "input_schema": {
            "type": "object",
            "properties": {
                "title":    {"type": "string", "description": "事项标题，如 场地需提前申请"},
                "desc":     {"type": "string", "description": "细节说明"},
                "phase":    {"type": "string", "enum": ["pre", "onsite", "other"],
                             "description": "所属阶段：拍摄前 pre / 拍摄当天 onsite / 其他 other，默认 pre"},
                "priority": {"type": "string", "enum": ["high", "mid", "low"],
                             "description": "优先级，默认 mid"},
            },
            "required": ["title"],
        },
    },
    {
        "name": "remove_note",
        "description": "按 id 删除一条注意事项（id 形如 nt_xxxx）。修改＝先删后加。",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "注意事项 id"}},
            "required": ["id"],
        },
    },
    {
        "name": "add_schedule_segment",
        "description": "往拍摄日程添加一个时段（一个场景对应一段）。场地/光线信息随日程走。",
        "input_schema": {
            "type": "object",
            "properties": {
                "scene":    {"type": "string", "description": "场景/地点名，如 音乐教室窗边"},
                "time":     {"type": "string", "description": "时间段，如 14:00–14:40"},
                "content":  {"type": "string", "description": "这一段拍什么，如 日常练习与互动"},
                "duration": {"type": "string", "description": "时长，如 40 分钟"},
                "light":    {"type": "string", "description": "光线，如 自然光 / 灯光为主"},
                "priority": {"type": "string", "enum": ["high", "mid", "low"],
                             "description": "优先级（高＝必拍）"},
            },
            "required": ["scene"],
        },
    },
    {
        "name": "remove_schedule_segment",
        "description": "按 id 删除一个拍摄时段（id 形如 sg_xxxx）。修改＝先删后加。",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "日程时段 id"}},
            "required": ["id"],
        },
    },
]

# 服装/道具 + 名场面工具(角色设定层,和 plan 一样只增删,不整段重写)。
_SETTING_TOOLS = [
    {
        "name": "add_costume",
        "description": "往角色的服装清单添加一件。只在用户明确要求时调用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "name":      {"type": "string", "description": "服装名称,如 黑长直假发"},
                "category":  {"type": "string",
                              "enum": ["wig", "top", "bottom", "shoes", "accessory", "misc"],
                              "description": "分类:假发wig/上衣top/下装bottom/鞋袜shoes/配饰accessory/其他misc"},
                "note":      {"type": "string", "description": "备注,如 白衬衫+米色背心"},
                "essential": {"type": "boolean", "description": "必备(true,默认)还是备用(false)"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "add_prop",
        "description": "往角色的道具清单添加一件(乐器/手持物等)。只在用户明确要求时调用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "name":      {"type": "string", "description": "道具名称,如 左手贝斯"},
                "note":      {"type": "string", "description": "备注"},
                "essential": {"type": "boolean", "description": "必备(true,默认)还是备用(false)"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "remove_wardrobe_item",
        "description": "按 id 删除一件服装或道具(id 形如 cs_/pr_,见「服装 / 道具」列表)。修改＝先删后加。",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "服装或道具 id"}},
            "required": ["id"],
        },
    },
    {
        "name": "add_moment",
        "description": "往角色的名场面添加一条(设定参考,写事件+大概时间背景,不要写拍摄建议)。只在用户明确要求时调用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "title":       {"type": "string", "description": "简短标题"},
                "source":      {"type": "string", "description": "大概出处,如 第一季 第6话(不确定写模糊范围)"},
                "description": {"type": "string", "description": "详细描述:发生了什么、大概在故事什么阶段、前后背景"},
            },
            "required": ["title"],
        },
    },
    {
        "name": "remove_moment",
        "description": "按 id 删除一条名场面(id 形如 mo_xxxx)。修改＝先删后加。",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "名场面 id"}},
            "required": ["id"],
        },
    },
]


def _format_plan(plan: dict) -> list[str]:
    """Render the current plan.json (with item ids) so the AI knows the live
    state and can target removals by id."""
    lines = ["", "═══ 拍摄计划总表（可用下方工具增删）═══"]

    crew = plan.get("crew") or {}
    crew_txt = " ".join(
        f"{lbl}{crew[k]}" for k, lbl in
        (("photographers", "摄影"), ("cosers", "coser"), ("logistics", "后勤"))
        if crew.get(k)
    )
    lines.append(
        f"主题：{plan.get('theme') or '（未填）'}　"
        f"日期：{plan.get('shoot_date') or '（未填）'}　"
        f"参与：{crew_txt or '（未填）'}"
    )

    equip = plan.get("equipment") or []
    lines.append(f"设备（{len(equip)}）：" + ("" if equip else "（空）"))
    for e in equip:
        tag = "必要" if e.get("required", True) else "可选"
        desc = f" — {e['desc']}" if e.get("desc") else ""
        lines.append(f"  [{e.get('id')}] {e.get('name')}（{tag}，{e.get('category', 'misc')}）{desc}")

    sched = plan.get("schedule") or []
    lines.append(f"拍摄日程（{len(sched)} 段）：" + ("" if sched else "（空）"))
    for s in sched:
        prio = f" ·{_PRIO_LABELS.get(s.get('priority'), '')}优先" if s.get("priority") else ""
        light = f" ·{s['light']}" if s.get("light") else ""
        lines.append(
            f"  [{s.get('id')}] {s.get('time') or '时段未定'} {s.get('scene')}"
            f" · {s.get('content') or ''} · {s.get('duration') or ''}{light}{prio}"
        )

    notes = plan.get("notes") or []
    lines.append(f"注意事项（{len(notes)}）：" + ("" if notes else "（空）"))
    for n in notes:
        ph = _PHASE_LABELS.get(n.get("phase"), "")
        pr = _PRIO_LABELS.get(n.get("priority"), "")
        lines.append(f"  [{n.get('id')}] {n.get('title')}（{ph}，{pr}优先）")

    return lines


def _primary_cid(project: dict) -> str:
    chars = project.get("characters") or []
    return chars[0]["id"] if chars else "c1"


def make_dedup(seen: set):
    """Wrap a mutation executor so an identical (tool, args) call runs at most once
    per turn — the model sometimes emits the same mutation several times, which
    would create duplicate items. `seen` accumulates keys across all wrapped tools."""
    def wrap(name: str, fn):
        def wrapped(inp: dict) -> str:
            key = (name, json.dumps(inp, ensure_ascii=False, sort_keys=True))
            if key in seen:
                return "（这一步刚才已经处理过了，无需重复。）"
            seen.add(key)
            return fn(inp)
        return wrapped
    return wrap


def _format_wardrobe(w: dict) -> list[str]:
    """Render 服装/道具 (with ids) so the AI can add/remove by id."""
    lines = ["", "═══ 服装 / 道具（可用工具增删）═══"]
    costume = w.get("costume") or []
    lines.append(f"服装（{len(costume)}）：" + ("" if costume else "（空）"))
    for c in costume:
        tag = "必备" if c.get("essential", True) else "备用"
        note = f" — {c['note']}" if c.get("note") else ""
        lines.append(f"  [{c.get('id')}] {c.get('name')}（{c.get('category', 'misc')}，{tag}）{note}")
    props = w.get("props") or []
    lines.append(f"道具（{len(props)}）：" + ("" if props else "（空）"))
    for p in props:
        tag = "必备" if p.get("essential", True) else "备用"
        note = f" — {p['note']}" if p.get("note") else ""
        lines.append(f"  [{p.get('id')}] {p.get('name')}（{tag}）{note}")
    return lines


def _format_moments(moments: list) -> list[str]:
    lines = ["", "═══ 名场面（可用工具增删）═══" + ("" if moments else "（空）")]
    for m in moments:
        src = f"（{m['source']}）" if m.get("source") else ""
        lines.append(f"  [{m.get('id')}] {m.get('title')}{src}")
    return lines


# ── System prompt ─────────────────────────────────────────────────────────────

def _build_system(project: dict, project_id: str) -> str:
    char_data   = project.get("character_data", {})
    char_bg     = char_data.get("characterBackground", {})
    if not isinstance(char_bg, dict): char_bg = {}
    world       = project.get("world", {}).get("worldSetting", {})
    if not isinstance(world, dict): world = {}
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
        "你有两种模式，务必分清：",
        "【聊天/建议】——这里尽管主动。回复前先过一遍整个项目，主动发现问题和缺口、"
        "直接给出可执行的具体建议（不说'我建议你可以考虑'这类软话），需要查资料就直接用 web_search。"
        "想到用户没提的补充（比如'还缺个补光灯''要不要加一段黄昏日程'），就在文字回复里问/提，不要直接动手改。",
        "",
        "【编辑数据】——调用增删工具（add_/remove_ 等）时必须克制，严格遵守：",
        "1. 只做用户这一条消息里明确点名要改的那几项。用户没点名的，一律不碰——哪怕你觉得该加也只在文字里建议。",
        "2. 一个诉求对应最少的工具调用：加一件就调一次 add，删一件就调一次 remove。不要为了'顺手优化'多调。",
        "3. 绝不重复调用：同一个 add 不要调多次；一次 remove 后若返回'没找到/可能已删除'，说明已经删掉了，就此打住，不要换 id 反复试。",
        "4. 修改某一项才用'先按 id 删、再重新添加'（id 见下方各列表，形如 eq_/nt_/sg_/cs_/pr_/mo_）；纯新增不要先删任何东西。",
        "5. 绝不把用户已有的内容整批重建/翻新。",
        "",
        "可编辑的范围：",
        "- 拍摄计划：设备 add_equipment/remove_equipment，注意事项 add_note/remove_note，"
        "拍摄日程 add_schedule_segment/remove_schedule_segment，总览 update_overview。",
        "- 角色服装/道具 add_costume/add_prop/remove_wardrobe_item；名场面 add_moment/remove_moment。",
        "- update_brief 只用于'帮我总结/更新总结'这类明确请求，或核心场地/风格已定时提交一次总结；不要频繁调。",
        "- 场地卡片和室内外标签由日程自动生成，改日程即可，不用单独维护；地点实际地址只有用户知道，不要编造。",
        "- 如果话题跑偏，自然引导回拍摄规划。",
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

    plan_data = project.get("plan", {}).get("data") or plan_service.load_plan_data(project_id)
    lines += _format_plan(plan_data)

    cid = _primary_cid(project)
    lines += _format_wardrobe(wardrobe_service.load_wardrobe(project_id))
    lines += _format_moments(moments_service.load_moments(project_id, cid)["moments"])

    return "\n".join(lines)


# ── Main entry point ──────────────────────────────────────────────────────────

def chat(message: str, history: list[dict], project: dict, project_id: str,
         reply_lang: str = "zh") -> dict:
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
    system   = _build_system(project, project_id) + (
        f"\n\n【回复语言】始终使用{_LANG_NAMES.get(reply_lang, '中文')}回复用户，"
        "无论用户用什么语言提问都不要在回复里混用其他语言。"
        "（拍摄计划里的字段值按用户填写的原文保留，不用翻译。）"
    )
    messages = history + [{"role": "user", "content": message}]

    # Closure captures brief data when AI calls update_brief.
    # update_brief is an executor tool so the AI receives a confirmation
    # string and continues to produce a text reply in the same loop —
    # this avoids the empty-bubble bug caused by passthrough tools that
    # return no text when using OpenAI's chat completion format.
    captured_brief: dict = {}
    state = {"plan_dirty": False}

    def _execute_update_brief(inp: dict) -> str:
        captured_brief.update(inp)
        return (
            "规划总结已保存成功。"
            "请在你的回复中告诉用户：右侧「拍摄总结」栏已更新，"
            "可以开始点击「+」添加具体的拍摄计划卡片了。"
        )

    # Plan mutation executors: mutate plan.json via plan_service, flag dirty so
    # the caller reloads and returns the fresh plan to the frontend.
    def _dirty(msg: str) -> str:
        state["plan_dirty"] = True
        return msg

    def _ex_update_overview(inp: dict) -> str:
        plan_service.update_overview(
            project_id, theme=inp.get("theme"),
            shoot_date=inp.get("shoot_date"), crew=inp.get("crew"),
        )
        return _dirty("总览已更新。")

    def _ex_add_equipment(inp: dict) -> str:
        item = plan_service.add_equipment(
            project_id, name=inp["name"], required=inp.get("required", True),
            desc=inp.get("desc"), category=inp.get("category"),
        )
        return _dirty(f"已添加设备「{item['name']}」（id {item['id']}）。")

    def _ex_remove_equipment(inp: dict) -> str:
        r = plan_service.remove_equipment(project_id, inp["id"])
        if r is None:
            return f"没找到 id 为 {inp['id']} 的设备，可能已被删除。"
        return _dirty(f"已删除设备「{r['name']}」。")

    def _ex_add_note(inp: dict) -> str:
        item = plan_service.add_note(
            project_id, title=inp["title"], desc=inp.get("desc"),
            phase=inp.get("phase", "pre"), priority=inp.get("priority", "mid"),
        )
        return _dirty(f"已添加注意事项「{item['title']}」（id {item['id']}）。")

    def _ex_remove_note(inp: dict) -> str:
        r = plan_service.remove_note(project_id, inp["id"])
        if r is None:
            return f"没找到 id 为 {inp['id']} 的注意事项，可能已被删除。"
        return _dirty(f"已删除注意事项「{r['title']}」。")

    def _ex_add_schedule(inp: dict) -> str:
        item = plan_service.add_schedule_segment(
            project_id, scene=inp["scene"], time=inp.get("time"),
            content=inp.get("content"), duration=inp.get("duration"),
            light=inp.get("light"), priority=inp.get("priority"),
            shot_ids=inp.get("shot_ids"),
        )
        return _dirty(f"已添加拍摄时段「{item['scene']}」（id {item['id']}）。")

    def _ex_remove_schedule(inp: dict) -> str:
        r = plan_service.remove_schedule_segment(project_id, inp["id"])
        if r is None:
            return f"没找到 id 为 {inp['id']} 的拍摄时段，可能已被删除。"
        return _dirty(f"已删除拍摄时段「{r['scene']}」。")

    # 服装/道具 + 名场面 mutations (设定层). Flag separate dirty flags so the caller
    # reloads + returns only what changed.
    cid = _primary_cid(project)

    def _dirty_wd(msg: str) -> str:
        state["wardrobe_dirty"] = True
        return msg

    def _dirty_mo(msg: str) -> str:
        state["moments_dirty"] = True
        return msg

    def _ex_add_costume(inp: dict) -> str:
        item = wardrobe_service.add_costume(
            project_id, name=inp["name"], category=inp.get("category"),
            note=inp.get("note"), essential=inp.get("essential", True),
        )
        return _dirty_wd(f"已添加服装「{item['name']}」（id {item['id']}）。")

    def _ex_add_prop(inp: dict) -> str:
        item = wardrobe_service.add_prop(
            project_id, name=inp["name"], note=inp.get("note"), essential=inp.get("essential", True),
        )
        return _dirty_wd(f"已添加道具「{item['name']}」（id {item['id']}）。")

    def _ex_remove_wardrobe(inp: dict) -> str:
        r = wardrobe_service.remove_item(project_id, inp["id"])
        if r is None:
            return f"没找到 id 为 {inp['id']} 的服装/道具，可能已被删除。"
        return _dirty_wd(f"已删除「{r['name']}」。")

    def _ex_add_moment(inp: dict) -> str:
        item = moments_service.add_moment(
            project_id, cid, title=inp["title"],
            source=inp.get("source"), description=inp.get("description"),
        )
        return _dirty_mo(f"已添加名场面「{item['title']}」（id {item['id']}）。")

    def _ex_remove_moment(inp: dict) -> str:
        r = moments_service.remove_moment(project_id, cid, inp["id"])
        if r is None:
            return f"没找到 id 为 {inp['id']} 的名场面，可能已被删除。"
        return _dirty_mo(f"已删除名场面「{r['title']}」。")

    mutation_executors = {
        "update_overview":         _ex_update_overview,
        "add_equipment":           _ex_add_equipment,
        "remove_equipment":        _ex_remove_equipment,
        "add_note":                _ex_add_note,
        "remove_note":             _ex_remove_note,
        "add_schedule_segment":    _ex_add_schedule,
        "remove_schedule_segment": _ex_remove_schedule,
        "add_costume":             _ex_add_costume,
        "add_prop":                _ex_add_prop,
        "remove_wardrobe_item":    _ex_remove_wardrobe,
        "add_moment":              _ex_add_moment,
        "remove_moment":           _ex_remove_moment,
    }

    # Same-turn dedup guard: the model sometimes emits the *identical* mutation
    # call several times in one turn (e.g. add_moment ×4 with the same args, or
    # retrying a remove after it already succeeded). Executing them literally
    # creates duplicate items / wasted calls. So each (tool, args) runs at most
    # once per chat() turn; a repeat returns a note without re-executing.
    _dedup = make_dedup(set())

    tool_executor = {
        "web_search":   lambda inp: _web_search(inp["query"], lang=inp.get("lang", "zh-cn")),
        "update_brief": _execute_update_brief,
        **{name: _dedup(name, fn) for name, fn in mutation_executors.items()},
    }

    result = call_agent(
        messages=messages,
        system=system,
        tools=TOOLS + _PLAN_TOOLS + _SETTING_TOOLS,
        tool_executor=tool_executor,
        max_turns=8,
        max_tokens=1000,
    )

    return {
        "reply": result["text"],
        "brief": captured_brief if captured_brief else None,
        "plan":     plan_service.load_plan_data(project_id) if state["plan_dirty"] else None,
        "wardrobe": wardrobe_service.load_wardrobe(project_id) if state.get("wardrobe_dirty") else None,
        "moments":  moments_service.load_moments(project_id, cid)["moments"] if state.get("moments_dirty") else None,
    }
