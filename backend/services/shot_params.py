"""
services/shot_params.py — Structured shot parameters ↔ image prompt translation

Every generated version stores a structured `params` object (景别/机位/冷暖…) so
the post-generation refine panel can open pre-filled on that version's actual
settings. This module is the single source of truth for:
  - PARAM_SCHEMA: the parameter keys + their allowed values (frontend + backend
    both reference this so the panel and the generator never drift apart)
  - translate_params(): turn the semantic zh values into English prompt fragments
    (景别=半身 → "medium shot, waist up") merged into the fields image_gen expects

The refine flow keeps the parent version's CONTENT (scene prose from the
interview) and only overrides the VISUAL params from the panel — so tweaking
参数 varies the rendering of the same moment, not the moment itself.

Open-ended params (表情/姿势/氛围) accept a free-text custom value; presets are
mapped to curated English, custom text is passed through (translated upstream if
需要). Pose uploads are handled by the ref system, not here.
"""

# key → { label, values: [zh, ...], default }. "open": True means custom text allowed.
PARAM_SCHEMA = {
    # 镜头
    "shot":   {"group": "镜头", "label": "景别", "values": ["特写", "近景", "半身", "全身", "远景"], "default": "半身"},
    "angle":  {"group": "镜头", "label": "机位", "values": ["俯视", "平视", "仰视"], "default": "平视"},
    "facing": {"group": "镜头", "label": "朝向", "values": ["正面", "侧前", "侧面", "背面"], "default": "侧前"},
    "aspect": {"group": "镜头", "label": "画幅", "values": ["竖图", "横图", "方图"], "default": "竖图"},
    # 构图
    "pos":    {"group": "构图", "label": "人物位置", "values": ["靠左", "居中", "靠右"], "default": "居中"},
    "scale":  {"group": "构图", "label": "主体大小", "values": ["占满", "适中", "留白多"], "default": "适中"},
    "bg":     {"group": "构图", "label": "背景", "values": ["清晰", "适中", "虚化"], "default": "适中"},
    # 人物
    "expr":     {"group": "人物", "label": "表情", "values": ["害羞", "微笑", "认真", "失落", "俏皮"], "default": "害羞", "open": True},
    "emphasis": {"group": "人物", "label": "表情强度", "values": ["微弱", "适中", "明显"], "default": "适中"},
    "gaze":     {"group": "人物", "label": "视线", "values": ["看镜头", "略偏左", "略偏右", "低头", "望向远处"], "default": "看镜头"},
    "pose":     {"group": "人物", "label": "姿势", "values": [], "default": "", "open": True},  # upload or free text
    # 色调 · 氛围
    "temp":      {"group": "色调", "label": "色温", "values": ["冷", "偏冷", "中性", "偏暖", "暖"], "default": "中性"},
    "grade":     {"group": "色调", "label": "整体色调", "values": ["自然真实", "清新明亮", "温暖柔和", "冷峻清冷", "复古胶片", "高对比"], "default": "自然真实"},
    "maincolor": {"group": "色调", "label": "主色", "values": [], "default": "", "open": True},  # named color or hex
    "mood":      {"group": "色调", "label": "氛围", "values": ["平淡", "适中", "戏剧化", "温暖治愈", "孤独疏离"], "default": "适中", "open": True},
}

_ASPECT_TO_ORIENTATION = {"竖图": "portrait", "横图": "landscape", "方图": "square"}

_SHOT_EN = {
    "特写": "extreme close-up, face and shoulders only",
    "近景": "close-up shot, chest up",
    "半身": "medium shot, waist up",
    "全身": "full body shot, the whole figure visible head to feet",
    "远景": "wide shot, the character appears small within the environment",
}
_ANGLE_EN = {
    "俯视": "camera slightly above eye level looking gently down",
    "平视": "camera at eye level, straight-on",
    "仰视": "camera slightly below eye level looking gently up",
}
_FACING_EN = {
    "正面": "body facing the camera front-on",
    "侧前": "body turned three-quarters toward the camera",
    "侧面": "body in profile, side view",
    "背面": "back toward the camera, head turned slightly over the shoulder",
}
_POS_EN = {
    "靠左": "subject positioned on the left third of the frame",
    "居中": "subject centered in the frame",
    "靠右": "subject positioned on the right third of the frame",
}
_SCALE_EN = {
    "占满": "subject fills most of the frame",
    "适中": "balanced ratio of subject to surrounding space",
    "留白多": "subject kept small with generous negative space around",
}
_BG_EN = {
    "清晰": "background in sharp focus",
    "适中": "background slightly softened",
    "虚化": "background heavily blurred, shallow depth of field",
}
_EXPR_EN = {
    "害羞": "shy, faint blush",
    "微笑": "a gentle soft smile",
    "认真": "serious, focused expression",
    "失落": "melancholic, downcast expression",
    "俏皮": "playful, mischievous expression",
}
_GAZE_EN = {
    "看镜头": "looking directly at the camera",
    "略偏左": "gaze directed slightly to the left",
    "略偏右": "gaze directed slightly to the right",
    "低头": "head lowered, looking down",
    "望向远处": "gazing into the distance",
    # legacy values (kept so old versions still translate)
    "看别处": "gaze directed off to the side",
    "低垂": "eyes lowered",
}
_EMPHASIS_EN = {
    "微弱": "subtle",
    "适中": "moderate",
    "明显": "pronounced",
}
_TEMP_EN = {
    "冷": "cool blue color tone",
    "偏冷": "slightly cool color tone",
    "中性": "neutral color tone",
    "偏暖": "warm golden color tone",
    "暖": "warm amber color tone",
}
_GRADE_EN = {
    "自然真实": "natural, true-to-life color",
    "清新明亮": "fresh and bright",
    "温暖柔和": "warm and soft tones",
    "冷峻清冷": "cool and crisp",
    "复古胶片": "vintage film look",
    "高对比": "high contrast, punchy colors",
}
_COLOR_EN = {
    "粉红": "pink", "橙": "orange", "黄": "yellow",
    "绿": "green", "蓝": "blue", "紫": "purple",
}
_MOOD_EN = {
    "平淡": "calm, understated mood",
    "适中": "balanced mood",
    "戏剧化": "dramatic, high-contrast mood",
    "温暖治愈": "warm, healing mood",
    "孤独疏离": "lonely, distant, isolated mood",
}


def normalize(params: dict | None) -> dict:
    """Fill missing keys with schema defaults so a partial/old params dict is safe."""
    params = params or {}
    return {k: (params.get(k) if params.get(k) not in (None, "") else v["default"])
            for k, v in PARAM_SCHEMA.items()}


def _open_value(raw: str, preset_map: dict) -> str:
    """Preset value → curated English; anything else is a custom string, pass through."""
    return preset_map.get(raw, raw)


def translate_params(params: dict) -> dict:
    """Translate structured params → English prompt fragments in the shape
    image_gen expects (atmosphere / pose / composition + orientation). Returns
    only the VISUAL fields; the caller merges these over the parent version's
    content (scene prose) to regenerate the same moment with new framing/mood."""
    p = normalize(params)

    composition = ". ".join([
        _SHOT_EN.get(p["shot"], p["shot"]),
        _ANGLE_EN.get(p["angle"], p["angle"]),
        _FACING_EN.get(p["facing"], p["facing"]),
        _POS_EN.get(p["pos"], p["pos"]),
        _SCALE_EN.get(p["scale"], p["scale"]),
        _BG_EN.get(p["bg"], p["bg"]),
    ]) + "."

    atmo_bits = [
        f"Color temperature: {_TEMP_EN.get(p['temp'], p['temp'])}",
        f"Color grading: {_GRADE_EN.get(p.get('grade', ''), p.get('grade', 'natural'))}",
    ]
    maincolor = str(p.get("maincolor") or "").strip()
    if maincolor:
        atmo_bits.append(f"Dominant color accent: {_COLOR_EN.get(maincolor, maincolor)}")
    atmo_bits.append(f"Mood: {_open_value(p['mood'], _MOOD_EN)}")
    atmosphere = "\n".join(atmo_bits)

    emphasis = _EMPHASIS_EN.get(p.get("emphasis", "适中"), "moderate")
    pose_bits = [
        f"Expression ({emphasis} intensity): {_open_value(p['expr'], _EXPR_EN)}",
        _GAZE_EN.get(p["gaze"], p["gaze"]),
    ]
    if p.get("pose") and not str(p["pose"]).startswith("上传:"):
        pose_bits.append(str(p["pose"]))
    pose = ". ".join(pose_bits) + "."

    return {
        "atmosphere":  atmosphere,
        "composition": composition,
        "pose":        pose,
        "orientation": _ASPECT_TO_ORIENTATION.get(p["aspect"], "portrait"),
    }
