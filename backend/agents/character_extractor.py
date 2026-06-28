"""
tools/character_extractor.py — Anime character visual feature extractor

Extracts 8 structured appearance fields from reference images using a vision LLM.
Supports multi-image sessions: each new image fills in missing fields from previous ones.

Entry points:
    extract_features(image_bytes, history, missing_fields) -> { updates, gender, message, updated_history }
    verify_same_character(image_bytes, existing_extracted)  -> { same: bool, reason: str }

FIELDS defines the 8 canonical slots. missing_fields is passed in from the session
so the LLM is told what to focus on and what to skip.
"""
import json
from tools import vision

FIELDS = [
    "hairstyle",
    "face_makeup",
    "upper_body",
    "lower_body",
    "shoes",
    "proportions",
    "distinctive",
    "color_palette",
]

SYSTEM_PROMPT = """你是一个动漫角色外貌特征提取专家。从参考图中提取角色的8个关键特征。

8个字段定义：
1. hairstyle       - Hair (color, length, style details)
2. face_makeup     - Face and makeup (state gender male/female first, then face shape, eye shape, skin tone, makeup style)
3. upper_body      - Upper body clothing (style, material, color, details)
4. lower_body      - Lower body clothing (pants/skirt style, material, color)
5. shoes           - Shoes (style, color) — only fill if feet/shoes are clearly visible
6. proportions     - Body proportions (head-to-body ratio, leg ratio) — only for full standing shots
7. distinctive     - Distinctive features (props, animal ears/tail, tattoos, special accessories) — fill "no distinctive features" if none
8. color_palette   - Color palette (primary and accent colors, include hex values where possible)

Rules:
- All field values must be in English
- Return null for any field not clearly visible in the image
- proportions requires a complete full-body standing pose, otherwise null

严格返回 JSON，不包含任何其他内容：
{
  "gender": "必填：male 或 female。裙子/蕾丝/蝴蝶结发饰/女装→female；西装/男款制服/男性体型→male。有任何女性服饰特征优先判定 female。",
  "updates": {
    "hairstyle": "English description or null",
    "face_makeup": "English description or null",
    "upper_body": "English description or null",
    "lower_body": "English description or null",
    "shoes": "English description or null",
    "proportions": "English description or null",
    "distinctive": "English description or null",
    "color_palette": "English description or null"
  },
  "message": "中文，直接对用户说话，语气简洁自然。只写一到两句：①一句话概括本张图提取到了哪些外貌信息；②如果有缺失，直接用指引语气告诉用户要补什么图。所有信息完整时只说一句'角色外貌信息已提取完整。'"
}"""


VERIFY_SYSTEM = """你是一个动漫角色一致性判断专家。
给定已知角色的外貌描述和一张新图片，判断新图片中的角色是否与已知描述是同一个角色。

判断标准：
- 发型颜色和样式相符
- 面部特征（眼睛颜色、脸型）相符
- 整体外貌或服装风格一致
- 即使角度不同、有换装，只要是同一角色就返回 true
- 如果是完全不同的角色（不同发色、不同脸型、不同风格）返回 false

严格返回 JSON，不包含其他内容：
{"same": true或false, "reason": "一句话说明判断依据"}"""


def verify_same_character(image_bytes: bytes, existing_extracted: dict) -> dict:
    """Quick check: does the new image show the same character as the existing session?"""
    b64, media_type = vision.encode_image(image_bytes)

    desc_parts = []
    for field, label in [
        ("hairstyle", "发型"), ("face_makeup", "脸型"), ("upper_body", "上身服装"), ("color_palette", "配色")
    ]:
        if existing_extracted.get(field):
            desc_parts.append(f"{label}：{existing_extracted[field]}")
    description = "；".join(desc_parts) if desc_parts else "暂无描述"

    messages = [{
        "role": "user",
        "content": [
            {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
            {"type": "text", "text": f"已知角色外貌特征：{description}。请判断图片中的角色是否与上述描述是同一个角色？"},
        ],
    }]

    raw = vision.call(messages, VERIFY_SYSTEM)
    return _parse(raw)


def _parse(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(text[start:end])
        raise ValueError(f"Could not parse response as JSON: {text[:200]}")


def extract_features(image_bytes: bytes, history: list, missing_fields: list[str]) -> dict:
    """
    Extract character features from one image, focusing on missing_fields.
    Returns: { updates: dict, message: str, updated_history: list }
    """
    b64, media_type = vision.encode_image(image_bytes)

    already_done = [f for f in FIELDS if f not in missing_fields]
    parts = ["请分析这张图片。"]
    if already_done:
        parts.append(f"以下字段已从之前的图片中提取完毕，无需再提及：{already_done}。")
    if missing_fields:
        parts.append(f"还缺少这些字段：{missing_fields}，请尽量从这张图中提取。")
    else:
        parts.append("所有字段已提取完毕，请确认并输出最终结果。")

    user_message = {
        "role": "user",
        "content": [
            {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
            {"type": "text", "text": " ".join(parts)},
        ],
    }

    messages = history + [user_message]
    raw = vision.call(messages, SYSTEM_PROMPT)
    result = _parse(raw)
    # print(result.get("message", {}))

    return {
        "updates":         result.get("updates", {}),
        "gender":          result.get("gender", "female"),
        "message":         result.get("message", ""),
        "updated_history": messages + [{"role": "assistant", "content": raw}],
    }
