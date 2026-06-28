"""
tools/action_guide.py — Action/pose guide generation

Two outputs per call:
  1. Pose sketch (gpt-image-2 images.edit) — mannequin line-art from generated.png
  2. Text guide (Claude Vision) — structured directions for the cosplayer

See docs/pose_sketch_prompting_guide.md for prompt rationale.
"""
import base64, io, json, os
from PIL import Image
from tools import vision

SKETCH_PROMPT = """\
Task:
Convert the reference illustration into a cosplay pose guide.
The output should function as a human pose reference for a cosplayer, not as an illustration.
The sketch should clearly communicate balance, center of gravity, limb orientation, and weight distribution.

Subject:
Replace the human body with a neutral artist mannequin.
Represent the body using simple cylinders, spheres, and joint markers. No muscles, no anatomy, no clothing folds.
Blank mannequin head. No hair, no facial features.
Match the original pose as precisely as possible.

Constraints:
- Preserve camera viewpoint and perspective exactly
- Keep the original framing. If legs or feet are cropped, expand the canvas downward only — do not recompose or change camera position or distance
- Full body from head to feet must be visible
- White background only
- Black outlines only
- No background elements
- No text, no watermarks"""

_TEXT_SYSTEM = """你是一个 cosplay 拍摄导演，专门帮助 coser 还原动漫角色的姿势。
从参考图中分析角色的肢体动作，给出具体的现场拍摄指导。

严格返回 JSON，不包含任何其他内容：
{
  "description": "一句话概括整体姿势和动作感（中文）",
  "directions": [
    "具体口头指令1（对 coser 说，中文，例如：重心压在右脚，左脚向前半步）",
    "具体口头指令2",
    "具体口头指令3",
    "具体口头指令4",
    "具体口头指令5"
  ],
  "checkpoints": [
    "现场核对要点1（中文，例如：双手握具位置在腰部两侧）",
    "现场核对要点2",
    "现场核对要点3"
  ]
}"""

_TEXT_USER = """分析这张图中角色的肢体姿势，输出 cosplay 现场拍摄指导。
专注于：重心分布、脊柱角度、手臂位置、腿部姿势、头部方向。
指令要具体可执行，像在现场对 coser 说话。"""


def generate_sketch(image_bytes: bytes) -> bytes:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    from config import SKETCH_MODEL
    result = client.images.edit(
        model=SKETCH_MODEL,
        image=[("input.png", buf.getvalue(), "image/png")],
        prompt=SKETCH_PROMPT,
        size="1024x1024",
        quality="low",
    )
    return base64.b64decode(result.data[0].b64_json)


def generate_text_guide(image_bytes: bytes) -> dict:
    b64, media_type = vision.encode_image(image_bytes)
    messages = [{
        "role": "user",
        "content": [
            {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
            {"type": "text", "text": _TEXT_USER},
        ],
    }]
    raw = vision.call(messages, _TEXT_SYSTEM)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}") + 1
        return json.loads(raw[start:end])
