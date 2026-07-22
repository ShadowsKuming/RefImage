"""
tools/image_gen.py — Image generation tool (provider abstraction)

Entry point:
    generate(project_id, prompt_parts) -> bytes

prompt_parts keys:
    style       — art style from world.json (fixed per project)
    character   — character appearance from visual_spec.prompt (fixed per project)
    atmosphere  — color tone + mood + genre feel (per shot, LLM generated)
    scene       — physical location and environment (per shot, LLM generated)
    pose        — body action and expression (per shot, LLM generated)
    composition — camera position and framing (per shot, LLM generated)

Provider selected via IMAGE_PROVIDER env var: openai (default) | fal

Prompt structure and gpt-image-2 constraints reference:
    docs/openai_image_prompting_guide.md
"""
import base64
import io
import os
import urllib.request
from pathlib import Path

from PIL import Image

STORAGE_ROOT = Path(__file__).parent.parent / "storage" / "projects"


def generate(project_id: str, prompt_parts: dict, extra_images: list[bytes] | None = None) -> bytes:
    from config import IMAGE_GEN_PROVIDER
    if IMAGE_GEN_PROVIDER == "openai":
        return _openai(project_id, prompt_parts, extra_images or [])
    elif IMAGE_GEN_PROVIDER == "fal":
        return _fal(project_id, prompt_parts)
    else:
        raise ValueError(f"Unknown IMAGE_GEN_PROVIDER: {IMAGE_GEN_PROVIDER!r}. Use 'openai' or 'fal'.")


# ── OpenAI / gpt-image-2 ─────────────────────────────────────────────────────

def _build_prompt_openai(parts: dict, num_refs: int = 1, num_extra: int = 0) -> str:
    """Assemble the structured prompt for gpt-image-2."""
    style = parts.get("style", "anime illustration")
    char_note = (
        f"The first {num_refs} image(s) show the same character from different angles. "
        "Use them together as the character reference — reproduce this character exactly, "
        "do not mix features from other images."
    ) if num_refs > 1 else (
        "The first image is the character reference — reproduce this character exactly."
    )
    extra_note = ""
    if num_extra > 0:
        extra_note = (
            f"The remaining {num_extra} image(s) after the character reference(s) are "
            "pose/background/prop/costume guides. Use them for composition and context "
            "but do NOT copy any characters or faces from them."
        )
    sections = [
        f"Anime illustration, {style}.",
        "\n".join(filter(None, [
            "Character — do not change:",
            char_note,
            extra_note,
            parts["character"],
        ])),
    ]
    if parts.get("atmosphere"):
        sections.append(f"Atmosphere:\n{parts['atmosphere']}")
    if parts.get("scene"):
        sections.append(f"Scene:\n{parts['scene']}")
    if parts.get("pose"):
        sections.append(f"Pose / Expression:\n{parts['pose']}")
    if parts.get("composition"):
        sections.append(f"Composition:\n{parts['composition']}")
    sections.append(
        "Constraints:\n"
        "- No text, no watermarks\n"
        "- Anatomically correct: feet and body face the same base direction, "
        "no impossible torso twists, head turn no more than 45 degrees from shoulder line"
    )
    return "\n\n".join(sections)


# gpt-image-2 supports arbitrary sizes: both edges multiple of 16,
# aspect ratio ≤ 3:1, total pixels 655,360–8,294,400.
# Note: 9:16 portrait (864x1536) consistently triggers safety moderation
# with anime character content — excluded.
_ORIENTATION_TO_SIZE = {
    "square":          "1024x1024",   # 1:1
    "portrait":        "1024x1536",   # 2:3 — full body, character focus
    "landscape":       "1536x1024",   # 3:2 — scene / environment
    "landscape_wide":  "1536x864",    # 16:9 — cinematic wide
}


def _openai(project_id: str, parts: dict, extra_images: list[bytes] | None = None) -> bytes:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    size = _ORIENTATION_TO_SIZE[parts.get("orientation", "square")]

    # Character reference images always come first (project-level, locked)
    char_refs  = _all_ref_pngs(project_id)
    # Processed r-node assets (mannequin sketches, backgrounds, props, costumes) appended after
    all_images = char_refs + (extra_images or [])

    prompt = _build_prompt_openai(parts, num_refs=len(char_refs), num_extra=len(extra_images or []))
    from config import IMAGE_GEN_MODEL, IMAGE_GEN_PROVIDER
    result = client.images.edit(
        model=IMAGE_GEN_MODEL[IMAGE_GEN_PROVIDER],
        image=[(f"img{i+1}.png", b, "image/png") for i, b in enumerate(all_images)],
        prompt=prompt,
        size=size,
        quality="low",
    )
    return base64.b64decode(result.data[0].b64_json)


# ── Fal / FLUX.1 Kontext ─────────────────────────────────────────────────────

def _build_prompt_fal(parts: dict) -> str:
    """Flatten prompt_parts into a single string for FLUX Kontext."""
    chunks = []
    if parts.get("atmosphere"):
        chunks.append(parts["atmosphere"])
    if parts.get("scene"):
        chunks.append(parts["scene"])
    if parts.get("pose"):
        chunks.append(parts["pose"])
    if parts.get("composition"):
        chunks.append(parts["composition"])
    return " ".join(chunks)


def _fal(project_id: str, parts: dict) -> bytes:
    import fal_client
    os.environ.setdefault("FAL_KEY", os.getenv("FAL_API_KEY", ""))
    result = fal_client.subscribe(
        "fal-ai/flux-kontext/dev",
        arguments={
            "prompt":              _build_prompt_fal(parts),
            "image_url":           _ref_data_uri(project_id),
            "num_inference_steps": 35,
            "guidance_scale":      3.5,
        },
    )
    with urllib.request.urlopen(result["images"][0]["url"]) as r:
        return r.read()


# ── Reference image helpers ───────────────────────────────────────────────────

def _ref_paths(project_id: str) -> list[Path]:
    """Return all reference images: refs/ first, then extra_refs/."""
    ctx = STORAGE_ROOT / project_id / "context"
    refs = sorted(f for f in (ctx / "refs").iterdir() if f.is_file()) if (ctx / "refs").exists() else []
    if not refs:
        raise RuntimeError(f"No reference images found for project {project_id!r}")
    extra = sorted(f for f in (ctx / "extra_refs").iterdir() if f.is_file()) if (ctx / "extra_refs").exists() else []
    return refs + extra


def _all_ref_pngs(project_id: str) -> list[bytes]:
    result = []
    for path in _ref_paths(project_id):
        img = Image.open(path).convert("RGBA")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        result.append(buf.getvalue())
    return result


def _ref_data_uri(project_id: str, target_size: int = 1024) -> str:
    """For fal provider: use first ref only (fal accepts single image URL)."""
    path = _ref_paths(project_id)[0]
    img = Image.open(path).convert("RGB")
    w, h = img.size
    if w < target_size or h < target_size:
        scale = target_size / min(w, h)
        img = img.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}"
