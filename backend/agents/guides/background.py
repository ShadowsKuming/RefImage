"""
agents/guides/background.py — Background location scouting guide

Analyzes the generated shot image via vision.call() and returns real-world
location recommendations for the cosplay shoot. Text-only, shot-level.
"""
import json
from tools import vision

_SYSTEM = """你是一个 cosplay 实拍导演，专门帮助 coser 找到匹配参考图氛围的真实拍摄场地。
分析图片背景，给出具体可执行的选址建议。

严格返回 JSON，不包含任何其他内容：
{
  "description": "一句话描述背景氛围和场景类型（中文）",
  "locations": [
    "推荐场地1：具体说明找什么类型的地方，有什么关键视觉元素（中文）",
    "推荐场地2",
    "推荐场地3"
  ],
  "bestTime": "最佳拍摄时间段（例如：黄昏18:00-19:00，蓝调时刻）",
  "checkpoints": [
    "现场布置要点1",
    "现场布置要点2",
    "现场布置要点3"
  ]
}"""

_USER = "分析这张图的背景环境，给出 cosplay 实拍的选址建议。专注于背景，忽略角色本身。"


def generate_background_guide(image_bytes: bytes) -> dict:
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
