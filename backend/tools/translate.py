"""
tools/translate.py — Translate visual spec fields from English to other languages

Called once after all image extraction is complete (done=True).
A single LLM call translates all non-null fields to zh + ja + pt simultaneously.
"""
import json
from tools.llm import call
# Share the completeness/null definition with analyze_service so a value that
# counts as "present" (and therefore lights the figure dot) is also translated —
# otherwise it falls back to the untranslated English in the tooltip.
from agents.character_extractor import FIELDS, is_null_value as _is_null

SYSTEM = (
    "你是一个动漫角色外貌描述翻译专家。"
    "将英文的角色外貌描述翻译成自然流畅的中文、日文和葡萄牙文，"
    "保留颜色、款式等专业术语的准确性，不要逐词直译。"
)


def translate_visual_spec(fields_en: dict) -> dict:
    """
    Translate English extracted visual spec fields to Chinese, Japanese, and Portuguese.

    Args:
        fields_en: { field_name: English_value_or_None }

    Returns:
        {
          "zh": { field_name: zh_value_or_None },
          "en": { field_name: en_value },   # passthrough
          "ja": { field_name: ja_value_or_None },
          "pt": { field_name: pt_value_or_None },
        }
    """
    to_translate = {k: v for k, v in fields_en.items() if not _is_null(v)}

    null_result = {f: None for f in FIELDS}
    if not to_translate:
        return {"zh": null_result.copy(), "en": dict(fields_en), "ja": null_result.copy(), "pt": null_result.copy()}

    items = "\n".join(f'  "{k}": "{v}"' for k, v in to_translate.items())
    user_msg = (
        f"将以下动漫角色外貌描述从英文翻译成中文（zh）、日文（ja）和葡萄牙文（pt）：\n\n"
        f"{{\n{items}\n}}\n\n"
        f"返回 JSON，字段名保持英文不变：\n"
        f'{{"zh": {{"field": "中文翻译", ...}}, "ja": {{"field": "日文翻译", ...}}, "pt": {{"field": "tradução em português", ...}}}}'
    )

    raw = call([{"role": "user", "content": user_msg}], SYSTEM, max_tokens=2600)

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}") + 1
        if start == -1 or end <= start:
            # Translation failed — fall back to English for all languages
            return {"zh": dict(fields_en), "en": dict(fields_en), "ja": dict(fields_en), "pt": dict(fields_en)}
        result = json.loads(raw[start:end])

    zh = {f: result["zh"].get(f) if f in to_translate else None for f in FIELDS}
    ja = {f: result["ja"].get(f) if f in to_translate else None for f in FIELDS}
    pt = {f: result.get("pt", {}).get(f) if f in to_translate else None for f in FIELDS}

    return {"zh": zh, "en": dict(fields_en), "ja": ja, "pt": pt}


_ZH2EN_SYSTEM = (
    "你是一个动漫角色外貌描述翻译专家。"
    "将中文的角色外貌描述翻译成自然、准确的英文、日文和葡萄牙文，"
    "保留颜色、款式等专业术语，不要逐词直译。"
)


def translate_fields_to_en_ja(fields_zh: dict) -> dict:
    """User edited the Chinese appearance; re-derive English/Japanese/Portuguese for
    the changed fields so the image-gen prompt reflects the correction. One LLM call.

    Args:  { field: zh_value_or_None }
    Returns: { "en": { field: en }, "ja": { field: ja }, "pt": { field: pt } } for
             the given fields; falls back to the zh text on failure (so nothing is
             left blank).
    """
    to_translate = {k: v for k, v in fields_zh.items() if not _is_null(v)}
    if not to_translate:
        return {"en": {}, "ja": {}, "pt": {}}
    items = "\n".join(f'  "{k}": "{v}"' for k, v in to_translate.items())
    user_msg = (
        f"将以下动漫角色外貌描述从中文翻译成英文（en）、日文（ja）和葡萄牙文（pt）：\n\n"
        f"{{\n{items}\n}}\n\n"
        f"返回 JSON，字段名保持英文不变：\n"
        f'{{"en": {{"field": "English", ...}}, "ja": {{"field": "日本語", ...}}, "pt": {{"field": "português", ...}}}}'
    )
    try:
        raw = call([{"role": "user", "content": user_msg}], _ZH2EN_SYSTEM, max_tokens=1800)
        start, end = raw.find("{"), raw.rfind("}") + 1
        result = json.loads(raw if start == -1 else raw[start:end])
        en = {k: result.get("en", {}).get(k) for k in to_translate}
        ja = {k: result.get("ja", {}).get(k) for k in to_translate}
        pt = {k: result.get("pt", {}).get(k) for k in to_translate}
        # any field the model dropped → fall back to the zh text
        for k, v in to_translate.items():
            if _is_null(en.get(k)): en[k] = v
            if _is_null(ja.get(k)): ja[k] = v
            if _is_null(pt.get(k)): pt[k] = v
        return {"en": en, "ja": ja, "pt": pt}
    except Exception:
        return {"en": dict(to_translate), "ja": dict(to_translate), "pt": dict(to_translate)}


_ZH2EN_PROMPT_SYSTEM = (
    "你把简短的中文拍摄描述（姿势/表情/氛围）翻译成自然的英文图像提示词短语。"
    "只翻译，不加解释，保持简短。返回 JSON：字段名不变，值为英文。"
)


def translate_texts_to_en(texts: dict) -> dict:
    """Generic short zh→en for image-prompt phrases (custom pose/expr/mood the user
    typed). Returns { field: english }, falling back to the original on failure."""
    items = {k: str(v).strip() for k, v in texts.items() if str(v or "").strip()}
    if not items:
        return {}
    body = "\n".join(f'  "{k}": "{v}"' for k, v in items.items())
    user_msg = f"翻译成英文：\n{{\n{body}\n}}\n返回 JSON：{{\"field\": \"English\", ...}}"
    try:
        raw = call([{"role": "user", "content": user_msg}], _ZH2EN_PROMPT_SYSTEM, max_tokens=500)
        s, e = raw.find("{"), raw.rfind("}") + 1
        out = json.loads(raw if s == -1 else raw[s:e])
        return {k: (out.get(k) or items[k]) for k in items}
    except Exception:
        return dict(items)
