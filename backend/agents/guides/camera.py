"""
tools/camera_guide.py — Camera / composition guide for cosplay shoots

Analyzes the generated shot image with GPT-4o vision and returns
a structured photography plan covering framing, camera parameters,
subject orientation, composition, and key visual factors.
"""
import json
from tools import vision

_SYSTEM = """你是一个 cosplay 摄影导演。分析参考图，输��结构化的拍摄方案。
你的任务不是描述你看到了什么，而是从图片的视觉意图中提炼出可执行的摄影指导。

字段说明：
- orientation：竖图 或 横图
- framing：画面包含人体的哪个范围，用"从XX到XX"描述，例如"从头顶到大腿"
- shotType：从以下选一个 — 全身 / 四分之三身 / 半身 / 近景 / 特写 / 大特写

camera：
  - height：从以��选一个 — 高机位 / 平视 / 略低 / 低机���
  - heightReason：这个机位高度服务于什么视觉目的（例如"强化角色气场"、"让武器更突出"）
  - tilt：从以下选一个 — 水平 / 轻微荷兰角 / 荷兰角
  - lensSuggestion：根据透视关系和背景压缩感推断镜头风格（不要猜具体焦段，描述光学感觉，例如"长焦压缩感，背景扁平"或"轻微广角，边缘略有畸变"）

subject：
  - gazeDirection：人物视线方向（例如"直视镜头"、"望向画面左上方"、"看向右侧假想敌人"）
  - headDirection：头部相对于躯干的朝向（例如"向右转约30°"、"正面朝前"）
  - bodyOrientation：躯干相对于镜头的角度（例如"完全正面"、"轻微向左四分之三转"）

composition：
  - rule：从以下选一个 — 居中 / 三分法 / 对角线 / 三角构图 / 对称 / 偏心
  - subjectPlacement：人物在画面中的位置（例如"居中"、"略偏左"、"下三分之一"）
  - visualFlow：视线如何在画面中流动（例如"武器引导视线向上到达面部"、"从左下到右上的对角线"）

lightingMood：一句话描述光线氛围

keyVisualFactors：3-5个定义这张图视觉感受的关键决策——摄影师必须复现这些才能拍出同样的气场

executionTips：2-3条具体的现场执行要点

严格返回 JSON，不含 markdown，不含其他文字：
{
  "orientation": "",
  "framing": "",
  "shotType": "",
  "camera": {
    "height": "",
    "heightReason": "",
    "tilt": "",
    "lensSuggestion": ""
  },
  "subject": {
    "gazeDirection": "",
    "headDirection": "",
    "bodyOrientation": ""
  },
  "composition": {
    "rule": "",
    "subjectPlacement": "",
    "visualFlow": ""
  },
  "lightingMood": "",
  "keyVisualFactors": [],
  "executionTips": []
}"""

_USER = "分析这张参考图，输出结构化的 cosplay 拍摄方案。"


def generate_camera_guide(image_bytes: bytes) -> dict:
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
