"""
tools/vision.py — Provider-agnostic vision LLM client

Mirrors the structure of llm.py. Messages use Anthropic's canonical image format:
  {"type": "image", "source": {"type": "base64", "media_type": "...", "data": "..."}}

OpenAI format is derived internally. Switch providers with VISION_PROVIDER env var.

Public API:
  call(messages, system) -> str
  encode_image(bytes)    -> (b64_str, media_type)
"""
import base64
import os
from config import VISION_PROVIDER as PROVIDER, VISION_MODEL


# ── Helpers ───────────────────────────────────────────────────────────────────

def encode_image(data: bytes) -> tuple[str, str]:
    """Returns (base64_string, media_type)."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        media_type = "image/png"
    elif data[:3] == b"\xff\xd8\xff":
        media_type = "image/jpeg"
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        media_type = "image/webp"
    else:
        media_type = "image/jpeg"
    return base64.standard_b64encode(data).decode(), media_type


def _to_openai_messages(messages: list[dict]) -> list[dict]:
    """Convert Anthropic-format image content to OpenAI image_url format."""
    result = []
    for msg in messages:
        content = msg["content"]
        if isinstance(content, str):
            result.append(msg)
            continue
        converted = []
        for block in content:
            if block.get("type") == "image":
                src = block["source"]
                data_url = f"data:{src['media_type']};base64,{src['data']}"
                converted.append({"type": "image_url", "image_url": {"url": data_url}})
            else:
                converted.append(block)
        result.append({"role": msg["role"], "content": converted})
    return result


# ── Providers ─────────────────────────────────────────────────────────────────

def _call_claude(messages: list, system: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    response = client.messages.create(
        model=VISION_MODEL["claude"],
        max_tokens=2000,
        system=system,
        messages=messages,
    )
    return response.content[0].text


def _call_openai(messages: list, system: str | None) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    sys_msgs = [{"role": "system", "content": system}] if system else []
    response = client.chat.completions.create(
        model=VISION_MODEL["openai"],
        max_tokens=2000,
        messages=sys_msgs + _to_openai_messages(messages),
    )
    return response.choices[0].message.content


# ── Public interface ──────────────────────────────────────────────────────────

_PROVIDERS = {"claude": _call_claude, "openai": _call_openai}


def call(messages: list, system: str) -> str:
    """Call the configured vision LLM. Messages use Anthropic canonical format."""
    fn = _PROVIDERS.get(PROVIDER)
    if not fn:
        raise ValueError(f"Unknown VISION_PROVIDER: '{PROVIDER}'. Choose from: {list(_PROVIDERS)}")
    return fn(messages, system)
