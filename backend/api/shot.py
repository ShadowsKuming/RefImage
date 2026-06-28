"""
api/shot.py — Endpoints for shot-level operations

POST   /projects/{id}/shots                               Create a new shot
DELETE /projects/{id}/shots/{shot_id}                     Delete a shot
GET    /projects/{id}/shots/{shot_id}                     Current shot data (status polling)
GET    /projects/{id}/shots/{shot_id}/image               Serve the generated example image
PUT    /projects/{id}/shots/{shot_id}/image               Replace image (frontend editor save)
PATCH  /projects/{id}/shots/{shot_id}/status              Update shot status (refined / done)
POST   /projects/{id}/shots/{shot_id}/chat                Per-shot AI assistant (image generation)
GET    /projects/{id}/shots/{shot_id}/guides/{type}       Get cached guide (404 if not generated)
POST   /projects/{id}/shots/{shot_id}/guides/{type}       Generate and cache guide
GET    /projects/{id}/shots/{shot_id}/guides/{type}.png   Serve guide sketch image
"""
import mimetypes
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
from services import project_service, shot_service, shot_guide_service

STORAGE_ROOT = Path(__file__).parent.parent / "storage" / "projects"

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


class CreateShotRequest(BaseModel):
    title: str
    mood: str = ""
    scene_description: str = ""


class UpdateStatusRequest(BaseModel):
    status: str


@router.post("/{project_id}/shots")
def create_shot(project_id: str, req: CreateShotRequest):
    """Create a new shot under the project."""
    try:
        shot = project_service.create_shot(project_id, req.title, req.mood, req.scene_description)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    return shot


@router.delete("/{project_id}/shots/{shot_id}")
def delete_shot(project_id: str, shot_id: str):
    """Delete a shot and all its files."""
    try:
        project_service.delete_shot(project_id, shot_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Shot not found")
    return {"ok": True}


@router.get("/{project_id}/shots/{shot_id}")
def get_shot(project_id: str, shot_id: str):
    """Return current shot data (used by frontend to poll generation status)."""
    try:
        return project_service.get_shot(project_id, shot_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Shot not found")


@router.get("/{project_id}/shots/{shot_id}/image")
def get_shot_image(project_id: str, shot_id: str):
    """Serve the generated example image for a shot."""
    path = STORAGE_ROOT / project_id / "shots" / shot_id / "generated.png"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Image not generated yet")
    media_type = mimetypes.guess_type(str(path))[0] or "image/png"
    return FileResponse(path, media_type=media_type)


@router.put("/{project_id}/shots/{shot_id}/image")
async def save_shot_image(project_id: str, shot_id: str, file: UploadFile = File(...)):
    """Replace the generated image for a shot (called by the frontend image editor on Save)."""
    shot_dir = STORAGE_ROOT / project_id / "shots" / shot_id
    if not shot_dir.exists():
        raise HTTPException(status_code=404, detail="Shot not found")
    data = await file.read()
    (shot_dir / "generated.png").write_bytes(data)
    # Invalidate composition guide — framing/composition changes with every crop
    camera_cache = shot_dir / "guides" / "camera.json"
    if camera_cache.exists():
        camera_cache.unlink()
    return {"ok": True}


@router.patch("/{project_id}/shots/{shot_id}/status")
def update_shot_status_endpoint(project_id: str, shot_id: str, req: UpdateStatusRequest):
    """Update shot status — only allows refined ↔ done transitions from the frontend."""
    if req.status not in {"refined", "done"}:
        raise HTTPException(status_code=400, detail="status must be 'refined' or 'done'")
    try:
        project_service.update_shot_status(project_id, shot_id, req.status)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Shot not found")
    return {"ok": True}


@router.post("/{project_id}/shots/{shot_id}/chat")
def shot_chat(project_id: str, shot_id: str, req: ChatRequest, background_tasks: BackgroundTasks):
    """Per-shot AI assistant — decides when to generate the reference image."""
    try:
        result = shot_service.shot_chat(
            project_id, shot_id, req.message,
            background_tasks,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project or shot not found")
    return {"reply": result["reply"], "generating": result["generating"]}


# ── Shot guides ───────────────────────────────────────────────

@router.get("/{project_id}/shots/{shot_id}/guides/{guide_type}.png")
def get_guide_sketch(project_id: str, shot_id: str, guide_type: str):
    """Serve the guide sketch image."""
    path = STORAGE_ROOT / project_id / "shots" / shot_id / "guides" / f"{guide_type}_sketch.png"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Sketch not found")
    return FileResponse(path, media_type="image/png")


@router.get("/{project_id}/shots/{shot_id}/guides/{guide_type}")
def get_guide(project_id: str, shot_id: str, guide_type: str):
    """Return cached guide data, or 404 if not yet generated."""
    result = shot_guide_service.get_guide(project_id, shot_id, guide_type)
    if result is None:
        raise HTTPException(status_code=404, detail="Guide not generated yet")
    return result


@router.post("/{project_id}/shots/{shot_id}/guides/{guide_type}")
def generate_guide(project_id: str, shot_id: str, guide_type: str):
    """Generate and cache a guide for this shot."""
    try:
        return shot_guide_service.generate_guide(project_id, shot_id, guide_type)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
