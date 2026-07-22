"""
tools/ref_extractor.py — Reference image extraction (provider abstraction)

Converts a user-uploaded reference image into a character-neutral asset
that can be safely fed to image generation without causing character drift.

Image-output types  (return bytes):
  pose        — mannequin skeleton sketch (pose only, no character)
  background  — environment with all people removed
  weapon      — isolated weapon/prop on white background
  costume     — outfit on a faceless mannequin

Text-output types  (return str):
  lighting    — lighting and camera angle description for prompt injection
  expression  — facial expression description for prompt injection

Provider: REF_EXTRACTOR_PROVIDER env var ("openai" default).
Same swap-friendly pattern as image_gen.py and vision.py.
"""
import base64
import io
import os

from PIL import Image

# ── Provider routing ──────────────────────────────────────────────────────────

IMAGE_TYPES = {"pose", "background", "weapon", "costume"}
TEXT_TYPES  = {"lighting", "expression"}
ALL_TYPES   = IMAGE_TYPES | TEXT_TYPES


def process(image_bytes: bytes, ref_type: str) -> "bytes | str":
    """
    Process a reference image according to its declared type.

    Returns bytes for IMAGE_TYPES, str for TEXT_TYPES.
    Raises ValueError for unknown ref_type.
    """
    if ref_type not in ALL_TYPES:
        raise ValueError(f"Unknown ref_type {ref_type!r}. Must be one of: {sorted(ALL_TYPES)}")

    provider = os.getenv("REF_EXTRACTOR_PROVIDER", "openai")

    if ref_type in TEXT_TYPES:
        return _extract_text(image_bytes, ref_type)

    if provider == "openai":
        return _openai_image(image_bytes, ref_type)
    else:
        raise ValueError(f"Unknown REF_EXTRACTOR_PROVIDER: {provider!r}")


# ── Image extraction (gpt-image-2) ────────────────────────────────────────────

_IMAGE_PROMPTS = {
    "background": (
        "Remove every person, character, and figure from this image. "
        "Keep only the background: environment, architecture, furniture, "
        "landscape, and non-human props. "
        "Output a clean background plate with no people whatsoever. "
        "Fill any areas where people were with natural background content. "
        "No text, no watermarks."
    ),
    "weapon": (
        "Isolate the main weapon or hand-held prop from this image. "
        "Place it centered on a plain white background. "
        "Remove the character, body parts, clothing, and all other elements. "
        "Show the weapon/prop clearly from a neutral angle. "
        "No text, no watermarks."
    ),
    "costume": (
        "Keep the character's costume and clothing exactly as shown, "
        "but replace the head and face with a plain white oval. "
        "Replace all exposed skin with neutral light grey. "
        "Remove the background entirely — white background only. "
        "The outfit, accessories, and costume details must remain intact. "
        "No text, no watermarks."
    ),
}


def _to_png(image_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _openai_image(image_bytes: bytes, ref_type: str) -> bytes:
    if ref_type == "pose":
        # Reuse the existing mannequin sketch generator
        from agents.guides.action import generate_sketch
        return generate_sketch(image_bytes)

    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    png = _to_png(image_bytes)
    prompt = _IMAGE_PROMPTS[ref_type]

    from config import SKETCH_MODEL  # same gpt-image-2 model
    result = client.images.edit(
        model=SKETCH_MODEL,
        image=[("input.png", png, "image/png")],
        prompt=prompt,
        size="1024x1024",
        quality="low",
    )
    return base64.b64decode(result.data[0].b64_json)


# ── Text extraction (vision LLM) ──────────────────────────────────────────────

_TEXT_PROMPTS = {
    "lighting": (
        "Describe the lighting and camera angle in this image for use as a photography reference.\n"
        "Output a concise English description covering:\n"
        "- Light source direction (front / side / back / top / Rembrandt)\n"
        "- Light quality (hard / soft / diffused)\n"
        "- Key light color temperature (warm / neutral / cool)\n"
        "- Notable shadow patterns\n"
        "- Camera angle (eye-level / high / low / bird's eye)\n"
        "Max 80 words, no bullet points, continuous prose."
    ),
    "expression": (
        "Describe the facial expression in this image as a director giving instructions to an actor.\n"
        "Focus on:\n"
        "- Brow position (raised / furrowed / relaxed)\n"
        "- Eye shape and direction of gaze\n"
        "- Mouth position (open / closed / corner up/down)\n"
        "- Overall emotion conveyed\n"
        "Max 60 words, direct imperative tone (e.g. 'Raise the left brow slightly...')."
    ),
}


def _extract_text(image_bytes: bytes, ref_type: str) -> str:
    from tools import vision
    b64, media_type = vision.encode_image(image_bytes)
    messages = [{
        "role": "user",
        "content": [
            {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
            {"type": "text", "text": _TEXT_PROMPTS[ref_type]},
        ],
    }]
    return vision.call(messages, system=None).strip()
