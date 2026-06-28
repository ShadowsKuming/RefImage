"""
tools/translate.py — Translate visual spec fields from English to other languages

Called once after all image extraction is complete (done=True).
A single LLM call translates all non-null fields to zh + ja simultaneously.
"""
import json
from tools.llm import call
from agents.character_extractor import FIELDS

_NULL_STRINGS = {
    "null", "none", "unknown", "n/a", "not visible",
    "cannot determine", "undetermined", "no distinctive features",
}

SYSTEM = (
    "你是一个动漫角色外貌描述翻译专家。"
    "将英文的角色外貌描述翻译成自然流畅的中文和日文，"
    "保留颜色、款式等专业术语的准确性，不要逐词直译。"
)


def _is_null(v) -> bool:
    return v is None or (isinstance(v, str) and v.strip().lower() in _NULL_STRINGS)


def translate_visual_spec(fields_en: dict) -> dict:
    """
    Translate English extracted visual spec fields to Chinese and Japanese.

    Args:
        fields_en: { field_name: English_value_or_None }

    Returns:
        {
          "zh": { field_name: zh_value_or_None },
          "en": { field_name: en_value },   # passthrough
          "ja": { field_name: ja_value_or_None },
        }
    """
    to_translate = {k: v for k, v in fields_en.items() if not _is_null(v)}

    null_result = {f: None for f in FIELDS}
    if not to_translate:
        return {"zh": null_result.copy(), "en": dict(fields_en), "ja": null_result.copy()}

    items = "\n".join(f'  "{k}": "{v}"' for k, v in to_translate.items())
    user_msg = (
        f"将以下动漫角色外貌描述从英文翻译成中文（zh）和日文（ja）：\n\n"
        f"{{\n{items}\n}}\n\n"
        f"返回 JSON，字段名保持英文不变：\n"
        f'{{"zh": {{"field": "中文翻译", ...}}, "ja": {{"field": "日文翻译", ...}}}}'
    )

    raw = call([{"role": "user", "content": user_msg}], SYSTEM, max_tokens=2000)

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}") + 1
        if start == -1 or end <= start:
            # Translation failed — fall back to English for all languages
            return {"zh": dict(fields_en), "en": dict(fields_en), "ja": dict(fields_en)}
        result = json.loads(raw[start:end])

    zh = {f: result["zh"].get(f) if f in to_translate else None for f in FIELDS}
    ja = {f: result["ja"].get(f) if f in to_translate else None for f in FIELDS}

    return {"zh": zh, "en": dict(fields_en), "ja": ja}
