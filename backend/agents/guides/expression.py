"""
agents/guides/expression.py — Expression guide for cosplay shoots

Analyzes the generated shot image via vision.call().
Output: emotion label, emoji, 1-2 key facial points, director's imagination cue.
"""
import json
from tools import vision

_SYSTEM = """你是一个 cosplay 拍摄导演，帮助 coser 自然地做出角色的面部表情。
分析参考图中角色的表情，给出导演式的现场引导——不要解剖面部肌肉，而是帮助 coser 进入那个情绪状态。

严格返回 JSON，不包含任何其他内容：
{
  "description": "表情情绪的简短定性，例如：傲慢中带轻蔑、压抑的愤怒、平静的决绝（中文，4-8字）",
  "emoji": "最贴近这个表情的单个 emoji",
  "keyPoints": [
    "最关键的面部特征1，只说最显眼的，例如：眼神从上往下，半眯",
    "最关键的面部特征2，最多两条"
  ],
  "cue": "一句情境引导，帮助 coser 进入状态。像导演对演员说话：描述一个具体的假想场景或内心状态，让表情自然浮现。不超过40字。"
}"""

_USER = "分析这张图中角色的面部表情，输出 cosplay 现场拍摄引导。"


def generate_expression_guide(image_bytes: bytes) -> dict:
    b64, media_type = vision.encode_image(image_bytes)
    messages = [{
        "role": "user",
        "content": [
            {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
            {"type": "text", "text": _USER},
        ],
    }]
    raw = vision.call(messages, _SYSTEM)
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}") + 1
        return json.loads(raw[start:end])
