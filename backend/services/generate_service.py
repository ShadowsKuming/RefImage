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
from pathlib import Path

from dotenv import load_dotenv

from services import project_service
from tools import image_gen

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../../.env"))

STORAGE_ROOT = Path(__file__).parent.parent / "storage" / "projects"


def generate_shot_image(project_id: str, shot_id: str, prompt_parts: dict) -> None:
    """
    Generate a reference image for a shot and persist it.
    Updates shot status: generating → done (or error).

    prompt_parts contains the LLM-generated variable fields:
        atmosphere, scene, pose, composition
    Fixed fields (style, character) are read from project context here.
    """
    project_service.update_shot_status(project_id, shot_id, "generating")
    try:
        full_parts = _assemble_prompt_parts(project_id, prompt_parts)
        image_bytes = image_gen.generate(project_id, full_parts)
        out_path = STORAGE_ROOT / project_id / "shots" / shot_id / "generated.png"
        out_path.write_bytes(image_bytes)
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
        "图片生成被安全审核系统拦截了。请根据我们刚才讨论的方案，分析最可能触发审核的原因，并给出具体的调整建议。",
        llm_history,
        project,
        shot,
    )
    project_service.append_shot_messages(project_id, shot_id, [
        {"role": "agent", "text": result["reply"]},
    ])


def _assemble_prompt_parts(project_id: str, variable_parts: dict) -> dict:
    """Merge fixed project context with LLM-generated variable parts."""
    ctx = STORAGE_ROOT / project_id / "context"

    vs = json.loads((ctx / "visual_spec.json").read_text())
    world = json.loads((ctx / "world.json").read_text())

    tone = world.get("worldSetting", {}).get("tone", {})
    default_style = tone.get("visual", "anime illustration")
    character = vs.get("prompt", vs.get("en", ""))

    return {
        "style":     variable_parts.pop("style", None) or default_style,
        "character": character,
        **variable_parts,
    }
