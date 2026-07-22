"""
services/generate_service.py — Shot image generation orchestration

Responsible for:
  - Reading fixed prompt parts from project context (style, character)
  - Merging with LLM-generated variable parts (atmosphere, scene, pose, composition)
  - Status management, file persistence, error handling

Actual image generation and prompt building delegated to tools/image_gen.py.
Called from shot_service as a FastAPI BackgroundTask.
"""
import json
import os
import uuid
from pathlib import Path

from dotenv import load_dotenv

from services import project_service
from tools import image_gen

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../../.env"))

STORAGE_ROOT = Path(__file__).parent.parent / "storage" / "projects"


def generate_shot_image(
    project_id: str,
    shot_id: str,
    prompt_parts: dict,
    parent_version_ids: list[str] | None = None,
) -> None:
    """
    Generate a reference image for a shot and persist it as a new version node.
    Updates shot status: generating → done (or error).

    prompt_parts contains the LLM-generated variable fields:
        atmosphere, scene, pose, composition
    Fixed fields (style, character) are read from project context here.
    Optional field ref_ids: list of r-node IDs whose processed assets are included.

    parent_version_ids records which version(s) the user was viewing when they
    requested this generation (for DAG lineage tracking).
    """
    project_service.update_shot_status(project_id, shot_id, "generating")
    try:
        ref_ids = prompt_parts.pop("ref_ids", None) or []
        extra_ref_images, extra_ref_texts = _collect_ref_assets(project_id, shot_id, ref_ids)

        full_parts = _assemble_prompt_parts(project_id, prompt_parts, extra_ref_texts)
        image_bytes = image_gen.generate(project_id, full_parts, extra_images=extra_ref_images)

        version_id = uuid.uuid4().hex[:8]
        prompt_summary = prompt_parts.get("atmosphere") or prompt_parts.get("pose") or ""
        project_service.add_version(
            project_id, shot_id, version_id,
            parent_version_ids or [],
            prompt_summary,
            image_bytes,
        )

        image_url = f"/projects/{project_id}/shots/{shot_id}/image"
        project_service.append_shot_messages(project_id, shot_id, [
            {"role": "agent", "text": "例图已生成！点击图上的标注点查看各部分拍摄指南。"},
        ])
        project_service.update_shot_status(project_id, shot_id, "done", image_url)
    except Exception as e:
        error_type = _classify_error(e)
        project_service.update_shot_status(project_id, shot_id, "error", error_type=error_type)
        if error_type == "moderation":
            _analyze_moderation_error(project_id, shot_id)
        raise


def _classify_error(e: Exception) -> str:
    msg = str(e)
    if "moderation_blocked" in msg or "safety_violations" in msg:
        return "moderation"
    return "unknown"


def _analyze_moderation_error(project_id: str, shot_id: str) -> None:
    """Call LLM to analyze the moderation failure and append its analysis to chat history."""
    from agents.shot_chat import chat as _shot_chat

    project = project_service.get_project(project_id)
    shot    = next((s for s in project.get("shots", []) if s["shot_id"] == shot_id), {})

    history = project_service.get_shot_history(project_id, shot_id)
    llm_history = [
        {"role": "user" if t["role"] == "user" else "assistant", "content": t["text"]}
        for t in history if t.get("role") in ("user", "agent")
    ]

    result = _shot_chat(
        (
            "图片被安全审核拦截了（sexual 标签）。"
            "用一句话说明最可能的原因，然后给出调整后的方案，问用户「要按这个生成吗？」。"
            "回复不超过 60 字，不要列清单，不要解释原理。"
        ),
        llm_history,
        project,
        shot,
    )
    project_service.append_shot_messages(project_id, shot_id, [
        {"role": "agent", "text": result["reply"]},
    ])


def _collect_ref_assets(
    project_id: str, shot_id: str, ref_ids: list[str]
) -> "tuple[list[bytes], dict[str, str]]":
    """
    For a list of r-node IDs, return:
      - extra_images: list of processed PNG bytes (image-type refs)
      - extra_texts:  dict of field_name → text (text-type refs for prompt injection)
    """
    from tools.ref_extractor import IMAGE_TYPES, TEXT_TYPES
    extra_images: list[bytes] = []
    extra_texts:  dict[str, str] = {}

    if not ref_ids:
        return extra_images, extra_texts

    shot_file = STORAGE_ROOT / project_id / "shots" / shot_id / "shot.json"
    if not shot_file.exists():
        return extra_images, extra_texts
    shot = json.loads(shot_file.read_text())
    ref_map = {r["id"]: r for r in shot.get("shot_refs", [])}

    refs_dir = STORAGE_ROOT / project_id / "shots" / shot_id / "refs"
    _text_to_field = {"lighting": "atmosphere", "expression": "pose"}

    for rid in ref_ids:
        r = ref_map.get(rid)
        if not r or r.get("status") != "ready":
            continue
        rtype = r.get("type")
        if rtype in IMAGE_TYPES:
            proc = refs_dir / f"{rid}_proc.png"
            if proc.exists():
                extra_images.append(proc.read_bytes())
        elif rtype in TEXT_TYPES:
            proc = refs_dir / f"{rid}_proc.txt"
            if proc.exists():
                field = _text_to_field.get(rtype, "atmosphere")
                extra_texts[field] = extra_texts.get(field, "") + "\n" + proc.read_text()

    return extra_images, extra_texts


def _assemble_prompt_parts(project_id: str, variable_parts: dict, extra_texts: dict | None = None) -> dict:
    """Merge fixed project context with LLM-generated variable parts and optional ref text injections."""
    ctx = STORAGE_ROOT / project_id / "context"

    vs = json.loads((ctx / "visual_spec.json").read_text())
    world = json.loads((ctx / "world.json").read_text())

    tone = world.get("worldSetting", {}).get("tone", {})
    default_style = tone.get("visual", "anime illustration")
    character = vs.get("prompt", vs.get("en", ""))

    parts = {
        "style":     variable_parts.pop("style", None) or default_style,
        "character": character,
        **variable_parts,
    }
    # Inject text-type ref descriptions into appropriate fields
    for field, text in (extra_texts or {}).items():
        if text.strip():
            parts[field] = (parts.get(field, "") + "\n" + text.strip()).strip()
    return parts
