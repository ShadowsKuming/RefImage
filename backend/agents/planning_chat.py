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
from tools.llm import call_agent, call_with_tools
from tools.search import web_search as _web_search
from services import plan_service, wardrobe_service, moments_service
from config import LLM_PROVIDER, FAST_LLM_MODEL_BY_PROVIDER

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
    {
        "name": "propose_shot",
        "description": (
            "当用户想【真正开始做/落地某一个具体分镜】时调用（比如聊到某个画面聊得差不多了、"
            "或用户说『就拍这个』『去做下一个分镜』）。这会给用户一个按钮，点了就带着这个概念跳进分镜编辑器细化。"
            "项目级只负责定方向、挑要拍哪些分镜；具体一张怎么摆拍（姿势/光线/构图/景别）不在这里聊，交给分镜编辑器。"
            "所以一旦锁定了一个分镜想法，就调用它把话题交出去，别在这儿继续抠细节。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "这个分镜的简短标题，如「趴桌子戴耳机」"},
                "concept": {"type": "string", "description": (
                    "给分镜编辑器的【完整交接】——把你俩在项目级已经聊定的、和这张分镜相关的一切都写进来，"
                    "这样分镜里的助手一看就懂、不用重新问一遍。至少涵盖：场景/地点、画面概念（她在做什么）、"
                    "情绪与氛围基调、以及已经聊到的光线/构图/色调倾向。示例："
                    "「场景：卧室桌边（民宿卧室，日式，木地板）。画面：后藤独趴在桌上戴耳机听音乐，专注放空、慵懒治愈。"
                    "氛围：宅家独处的温柔安静，带点松弛。光线：自然光靠窗 + 暖色台灯混合，写实感。」"
                )},
            },
            "required": ["title", "concept"],
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
        "你是这位用户的拍摄搭档——一个懂行、靠谱、语气温柔的伙伴，陪 ta 一起把这次 cosplay 拍摄一点点构思出来。",
        "你说话像一个走在 ta 身边的人，而不是发号施令的总监：多用'我们'，先照顾 ta 的感受和想法，再自然地把你专业的判断给出去。",
        "你拥有项目的完整信息：角色资料、已规划的所有 shots 及其 guide 数据。",
        "",
        "工作方式：",
        "你有两种模式，务必分清：",
        "【聊天/建议】——尽管主动，但用陪伴的方式。回复前先过一遍整个项目，帮 ta 发现问题和缺口，需要查资料就直接用 web_search。"
        "给建议时内容要具体、可执行（别只说'挺好的''都可以'这种没营养的话），但把它包在温柔、一起商量的语气里——"
        "像'我们不如…''我觉得这里加个…会更稳，你觉得呢?'这样，而不是冷冰冰下命令。"
        "想到 ta 没提的补充（比如'是不是还缺个补光灯''要不要加一段黄昏日程'），就在文字里轻轻提一句、问问 ta 的意思，不要直接动手改。",
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
        "【★ 你是项目级助手：聊的是『基调』，不是具体分镜】",
        "你和用户聊的是【整组作品】的大方向——想表达什么、角色的核心解读、整体情绪与视觉气质，是给整组定调子的北极星。",
        "【具体某一张怎么拍】——什么姿势、什么构图、什么镜头、哪个具体动作/瞬间——那是【分镜级】的事，"
        "由每个 shot 自己的编辑器去细化，不归你管。",
        "所以当用户聊『作品想表达什么』或『对角色的理解』时，请停在【方向与气质】这一层：帮他把整组的情绪基调、"
        "核心解读、视觉大方向说清楚就够了。不要跳进去替他设计具体分镜——别抛出『拍她独自坐在排练室拨吉他、阳光打在身上』"
        "这种单张画面方案，也别给『独自拨吉他 / 抱吉他紧张 / 指尖特写』这类具体镜头选项。",
        "★【聊基调要果断收尾、回弹，别无限复述】：这类基调对话聊 2-3 个来回、你已能用一句话概括整组方向时，就【立刻收尾】。"
        "特别注意：当用户开始用『对 / 挺好 / 就这样 / 嗯』这类【认同】来回应，说明调子已经定了——你【绝不能再把方向复述第二遍】，必须马上收尾。"
        "收尾【必须】落在一个明确的二选一提问上，基本照这句给用户选择：『那这次的调子我大概摸到了～要不要带着这个感觉去构思第一个分镜？还是想再换个方向聊聊？』"
        "——没有给出这个『去构思分镜 / 换个方向』的二选一，就等于没收尾、算失败。"
        "那些『具体怎么摆拍』的细节，留到分镜里展开，你别在这儿包办。",
        "",
        "【开场规划对话（项目早期、拍摄计划大多还空着时）】",
        "如果现在还没几个 shot、计划面板大多是空的，你的首要任务不是急着出整套方案，而是像朋友一样在轻松的聊天里，"
        "一点点把这次拍摄的基本盘摸清楚、并顺手记进计划面板。你心里要收集的有四样——"
        "拍摄时间、场地、摄影师、假发/服装/道具准备——但这是【你自己的待办清单，绝对不要一次性列给用户看】。",
        "★【一轮正确的样子，请照抄这个极简风格】：用户说『9月中旬』→ 你【只】做两件事：① update_overview(shoot_date='9月中旬')；"
        "② 回一句『好，9月中旬先记下了～那你想好大概在哪拍了吗？』。就这么多。这一轮【绝不】顺手写主题、【绝不】填 crew、【绝不】add_note、【绝不】加场地——"
        "每一样都【只在用户亲口说到那一项时】才记。反面教材（严禁）：用户才说了个时间，你却一口气把主题、人手、一堆注意事项、几个场地全填了。务必遵守：",
        "1. ★【每条消息只问一个问题】。绝不把待办罗列出来甩给用户——不许出现『1. 2. 3. 4.』这样的清单，"
        "也不许说『我们要先弄清楚这几点』『先搭个大框架』之类的话。用户在你任何一条消息里，都只应该看到【一个】要回答的问题；"
        "问完这一件、等用户答了，下一轮再问下一件。",
        "2. ★ 开场别铺垫、别啰嗦：最多一句轻轻回应用户上一句，然后【直接】问第一个问题（一般从『大概什么时候拍』开始）。"
        "不要写『我先接住你的想法』『帮你搭个大框架』『按照拍摄流程』这类元叙述和客套。",
        "3. 提议 ≠ 替用户决定。涉及创意选择的（尤其场地、主题），先在【文字里】给出你的提议再问『你觉得行吗，还是有别的想法』，等用户点头，才用工具记下来。"
        "★★【场地绝不批量添加、绝不凭角色/原作设定脑补地点】：只有用户明确选定了某个地点，才 add_schedule_segment 记【一条】；"
        "绝不一次加好几个地点，也绝不把原作里的排练室/live house 等场景自动填进去。主题(theme)同理——收集阶段别自动写一长串，等整组方向聊清楚了再记、而且要短。",
        "4. 用户给了答案，就【当场】用对应工具记进计划，对号入座、别记错也别漏："
        "  ·时间→update_overview(shoot_date)：【按用户原话记】，他说『9月中旬』就记『9月中旬』，绝不自己编成某月某日、更不能写错年份；"
        "  ·主题→update_overview(theme)；  ·场地→add_schedule_segment(scene=那个地点)；"
        "  ·摄影/人手→update_overview(crew)：用户说找到摄影了，就立刻记 crew.photographers=1（主角 coser 一般 cosers=1）；"
        "  ·假发/服装/道具【某样没到位】→add_note 记一条实物待办（title 如『服装待做』『假发待买』，phase='pre'）。",
        "5. ★★【add_note 只记『用户提到的实物准备待办』，绝不记你自己的议程】：add_note 只在用户明确说某样东西还没到位时加，一条对应一件实物。"
        "【严禁】把『确定摄影师』『场地待讨论』『设备清单待规划』『整体风格商量』『拍摄日程待安排』这类【你接下来要问/要想的事】写进 add_note——"
        "那是你脑子里的流程，不是用户的注意事项，写进去会把面板搞成一团垃圾。宁可不记，也不要记这种议程条目。",
        "6. 摄影风格（日系/暗调等）没有对应字段，记在心里、用来指导后面画面设计即可，不用硬塞进 crew，也不要为它 add_note。",
        "★ 准备情况必须问、绝不能替用户假设：下面『角色服装/道具』列表是角色的造型设计，不代表用户实体已备齐——"
        "永远不要说『你准备得很全了/很齐了』这类话。假发、衣服、道具到没到位，只有问了用户、用户回答了才知道，没问就是未知。",
        "7. ★【绝不重复问同一件事】：用户对某一项说了『还没定 / 不知道 / 看情况 / 随便』，就【立刻把该字段记成『待定』并跳到下一个还没问过的项】——"
        "绝不许换个说法把同一件事再问一遍（这是最让用户抓狂的死循环）。同一件事最多问一次。也能根据上一个答案跳过没意义的追问（没找到摄影就别问风格）。",
        "8. 收尾要【果断】：这四样（时间/场地/摄影/准备）每样【各问过一遍】就算收集完——别再往细枝末节里钻"
        "（例如别一件件追问百褶裙、白袜、乐福鞋、发带这种服装配件；那些等要拍了自然会清点）。用户连着两次说『还没定』也立刻收尾。"
        "收尾时用一句话说你大概了解情况了，把选择权交回给他——问他想直接去『构思第一个分镜』，还是换个方向聊聊。",
        "一旦计划已经比较充实，就回到正常的聊天/建议模式，别反复追问这些基本信息。",
        "9. ★ 每一轮【不管你调了几个工具】，最后都必须给用户一句自然的话——绝不能只调工具、不说话（那样用户看到的是空白气泡）。"
        "而且一轮别调一大堆工具：通常只记 0-1 项、跟一个问题就够，别一口气填一堆。",
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


# ── Quick-reply options (fast-model, forced tool) ─────────────────────────────

_SUBMIT_OPTIONS_TOOL = {
    "name": "submit_options",
    "description": "提交用户此刻最可能点的快捷回答。",
    "input_schema": {
        "type": "object",
        "properties": {
            "options": {
                "type": "array",
                "items": {"type": "string"},
                "description": "2-4 个快捷回答，第一人称、简短（≤14字）；助手在问句里列了几个候选就给全那几个，别漏",
            },
        },
        "required": ["options"],
    },
}


def _suggest_options(char_name: str, messages: list[dict], reply_lang: str = "zh") -> list[str]:
    """2-4 quick-reply chips answering the assistant's last message. Cheap fast-model
    call with a forced tool so output is structured and consistent with the convo.
    Returns [] on any failure — chips are a nicety, never block the reply."""
    system = (
        f"这是一个 cosplay 拍摄规划对话，角色是 {char_name}。\n"
        "你的唯一任务：给用户几个能【一键回答助手最后那条消息】的快捷选项（2-4 个，第一人称、短，≤14字）。\n"
        "规则：\n"
        "1. 必须是对『助手最后那个问题』的直接回答，同一层级、同一主题，别跨层。\n"
        "2. 如果助手列了候选（如「清晨、午后、傍晚」），就把每一个都做成选项、逐字照用、别漏。\n"
        "3. 选项之间有区分度；其中通常留一个『还没定/还不确定』这类的兜底答案。\n"
        "4. 和用户已经说过的保持一致，绝不矛盾。\n"
        "5. 扎在这个角色/这次拍摄的设定里，别用通用模板。\n"
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
    return [str(o).strip() for o in (call.get("input", {}).get("options") or []) if str(o).strip()][:4]


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
    captured_shot: dict = {}
    state = {"plan_dirty": False}

    def _execute_update_brief(inp: dict) -> str:
        captured_brief.update(inp)
        return (
            "规划总结已保存成功。"
            "请在你的回复中告诉用户：右侧「拍摄总结」栏已更新，"
            "可以开始点击「+」添加具体的拍摄计划卡片了。"
        )

    def _execute_propose_shot(inp: dict) -> str:
        captured_shot.update({"title": inp.get("title", ""), "concept": inp.get("concept", "")})
        return ("已准备好把这个分镜交给分镜编辑器细化。"
                "请在回复里简短地告诉用户：那我们就带着这个想法去构思这个分镜吧（一句话即可）。")

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

    # Code-level guard: gpt-4.1 keeps trying to dump its own planning agenda into
    # 注意事项 ("器材清单需列出" / "场地预约须沟通" / "后勤协助可酌情加人"). Drop titles
    # that reference the planning PROCESS rather than a concrete prep todo, no matter
    # what the prompt says. Real prep todos ("服装待做" / "假发待买") have none of these.
    _NOTE_AGENDA_WORDS = ("清单", "进度", "预约", "沟通", "统筹", "规划", "协助", "酌情",
                          "列出", "讨论", "商量", "安排", "对接", "联系", "试穿", "补光",
                          "设备", "完善", "确认")

    def _ex_add_note(inp: dict) -> str:
        title = str(inp.get("title", ""))
        if any(w in title for w in _NOTE_AGENDA_WORDS):
            return (f"「{title}」看起来是流程议程、不是用户提到的实物准备待办，已【跳过不记】。"
                    "注意事项只记用户说的『某样东西没到位』（如服装待做/假发待买）。")
        existing = {n.get("title") for n in plan_service.load_plan_data(project_id).get("notes", [])}
        if title in existing:
            return f"注意事项「{title}」已经在列表里了，无需重复添加。"
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
        # Code-level guard: the model likes to dump every canonical location at once
        # (排练室 + 音乐教室 + STARRY + 后藤家). Only the venue the user actually chose
        # should land — cap to one add per turn.
        if state.get("sched_added", 0) >= 1:
            return ("这一轮已经加过一个场地了，别一次批量加多个地点——一个场地就够，"
                    "其余等用户明确选了再加。已跳过这次。")
        item = plan_service.add_schedule_segment(
            project_id, scene=inp["scene"], time=inp.get("time"),
            content=inp.get("content"), duration=inp.get("duration"),
            light=inp.get("light"), priority=inp.get("priority"),
            shot_ids=inp.get("shot_ids"),
        )
        state["sched_added"] = state.get("sched_added", 0) + 1
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
        "propose_shot": _execute_propose_shot,
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

    char_name = project.get("character_data", {}).get("character", "角色")
    options = _suggest_options(
        char_name,
        messages + [{"role": "assistant", "content": result["text"]}],
        reply_lang,
    )

    return {
        "reply": result["text"],
        "options": options,
        "brief": captured_brief if captured_brief else None,
        "proposed_shot": captured_shot if captured_shot else None,
        "plan":     plan_service.load_plan_data(project_id) if state["plan_dirty"] else None,
        "wardrobe": wardrobe_service.load_wardrobe(project_id) if state.get("wardrobe_dirty") else None,
        "moments":  moments_service.load_moments(project_id, cid)["moments"] if state.get("moments_dirty") else None,
    }
