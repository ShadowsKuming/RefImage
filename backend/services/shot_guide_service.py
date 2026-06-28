"""
services/shot_guide_service.py — Shot-level guide generation and retrieval

Handles get/generate for all guide types.
Guides are cached under: storage/.../shots/{shot_id}/guides/

Files per guide type:
  {guide_type}.json         — structured text guide
  {guide_type}_sketch.png   — visual reference image (where applicable)
"""
import json
from pathlib import Path

STORAGE_ROOT = Path(__file__).parent.parent / "storage" / "projects"


def _guide_dir(project_id: str, shot_id: str) -> Path:
    return STORAGE_ROOT / project_id / "shots" / shot_id / "guides"


def _generated_png(project_id: str, shot_id: str) -> Path:
    return STORAGE_ROOT / project_id / "shots" / shot_id / "generated.png"


def get_guide(project_id: str, shot_id: str, guide_type: str) -> dict | None:
    """Return cached guide data, or None if not yet generated."""
    guide_file = _guide_dir(project_id, shot_id) / f"{guide_type}.json"
    if not guide_file.exists():
        return None
    data = json.loads(guide_file.read_text())
    return data


def generate_guide(project_id: str, shot_id: str, guide_type: str) -> dict:
    """Generate and cache a guide. Returns same shape as get_guide."""
    img_path = _generated_png(project_id, shot_id)
    if not img_path.exists():
        raise FileNotFoundError("generated.png not found — generate the shot image first")

    image_bytes = img_path.read_bytes()
    guide_dir   = _guide_dir(project_id, shot_id)
    guide_dir.mkdir(exist_ok=True)

    if guide_type == "action":
        result = _generate_action(image_bytes, guide_dir, project_id, shot_id)
    elif guide_type == "background":
        result = _generate_background(image_bytes)
    elif guide_type == "expression":
        result = _generate_expression(image_bytes)
    elif guide_type == "camera":
        result = _generate_camera(image_bytes)
    else:
        raise ValueError(f"Unsupported guide type: {guide_type!r}")

    # Cache to disk
    (guide_dir / f"{guide_type}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2)
    )
    return result


def _generate_camera(image_bytes: bytes) -> dict:
    from agents.guides.camera import generate_camera_guide
    guide = generate_camera_guide(image_bytes)
    return {"guide": guide, "sketch_url": None}


def _generate_expression(image_bytes: bytes) -> dict:
    from agents.guides.expression import generate_expression_guide
    guide = generate_expression_guide(image_bytes)
    return {"guide": guide, "sketch_url": None}


def _generate_background(image_bytes: bytes) -> dict:
    from agents.guides.background import generate_background_guide
    guide = generate_background_guide(image_bytes)
    return {"guide": guide, "sketch_url": None}


def _generate_action(image_bytes: bytes, guide_dir: Path, project_id: str, shot_id: str) -> dict:
    from agents.guides.action import generate_sketch, generate_text_guide

    # Generate both in parallel would be nice but keep it simple for now
    sketch_bytes = generate_sketch(image_bytes)
    text_guide   = generate_text_guide(image_bytes)

    sketch_path = guide_dir / "action_sketch.png"
    sketch_path.write_bytes(sketch_bytes)

    sketch_url = f"/projects/{project_id}/shots/{shot_id}/guides/action.png"

    return {
        "guide":      text_guide,
        "sketch_url": sketch_url,
    }
