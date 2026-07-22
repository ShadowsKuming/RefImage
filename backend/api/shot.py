"""
api/shot.py — Endpoints for shot-level operations

POST   /projects/{id}/shots                               Create a new shot
DELETE /projects/{id}/shots/{shot_id}                     Delete a shot
GET    /projects/{id}/shots/{shot_id}                     Current shot data (status polling)
GET    /projects/{id}/shots/{shot_id}/image               Serve the generated example image (no auth — img tag)
PUT    /projects/{id}/shots/{shot_id}/image               Replace image (frontend editor save)
PATCH  /projects/{id}/shots/{shot_id}/status              Update shot status (refined / done)
POST   /projects/{id}/shots/{shot_id}/chat                Per-shot AI assistant (image generation)
GET    /projects/{id}/shots/{shot_id}/guides/{type}       Get cached guide (404 if not generated)
POST   /projects/{id}/shots/{shot_id}/guides/{type}       Generate and cache guide
GET    /projects/{id}/shots/{shot_id}/guides/{type}.png   Serve guide sketch image (no auth — img tag)
"""
import mimetypes
import uuid
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
from api.auth import get_current_user
from services import project_service, shot_service, shot_guide_service

STORAGE_ROOT = Path(__file__).parent.parent / "storage" / "projects"

router = APIRouter()


def _check_owner(project_id: str, user_id: str) -> None:
    try:
        project_service.assert_owner(project_id, user_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")


class ChatRequest(BaseModel):
    message: str
    selected_version_ids: list[str] = []
    selected_ref_ids: list[str] = []


class CreateShotRequest(BaseModel):
    title: str
    mood: str = ""
    scene_description: str = ""


class UpdateStatusRequest(BaseModel):
    status: str


class RenameShotRequest(BaseModel):
    title: str


@router.post("/{project_id}/shots")
def create_shot(
    project_id: str,
    req: CreateShotRequest,
    user_id: str = Depends(get_current_user),
):
    _check_owner(project_id, user_id)
    try:
        shot = project_service.create_shot(project_id, req.title, req.mood, req.scene_description)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    return shot


@router.delete("/{project_id}/shots/{shot_id}")
def delete_shot(
    project_id: str,
    shot_id: str,
    user_id: str = Depends(get_current_user),
):
    _check_owner(project_id, user_id)
    try:
        project_service.delete_shot(project_id, shot_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Shot not found")
    return {"ok": True}


@router.get("/{project_id}/shots/{shot_id}")
def get_shot(
    project_id: str,
    shot_id: str,
    user_id: str = Depends(get_current_user),
):
    _check_owner(project_id, user_id)
    try:
        return project_service.get_shot(project_id, shot_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Shot not found")


@router.get("/{project_id}/shots/{shot_id}/image")
def get_shot_image(project_id: str, shot_id: str):
    """Serve the generated example image — no auth required (used via <img> tags)."""
    path = STORAGE_ROOT / project_id / "shots" / shot_id / "generated.png"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Image not generated yet")
    media_type = mimetypes.guess_type(str(path))[0] or "image/png"
    return FileResponse(path, media_type=media_type)


@router.put("/{project_id}/shots/{shot_id}/image")
async def save_shot_image(
    project_id: str,
    shot_id: str,
    file: UploadFile = File(...),
    parent_version_id: str | None = Form(default=None),
    user_id: str = Depends(get_current_user),
):
    """Save an image as a new version node.

    parent_version_id — pass the current active version ID when saving a crop/edit;
    omit (or pass empty) for a fresh user upload that should be an independent root node.
    """
    _check_owner(project_id, user_id)
    shot_dir = STORAGE_ROOT / project_id / "shots" / shot_id
    if not shot_dir.exists():
        raise HTTPException(status_code=404, detail="Shot not found")
    data = await file.read()
    parent_ids = [parent_version_id] if parent_version_id else []
    version_id = uuid.uuid4().hex[:8]
    project_service.add_version(project_id, shot_id, version_id, parent_ids, "user_edit", data)
    return {"ok": True, "version_id": version_id}


@router.patch("/{project_id}/shots/{shot_id}/title")
def rename_shot_endpoint(
    project_id: str,
    shot_id: str,
    req: RenameShotRequest,
    user_id: str = Depends(get_current_user),
):
    _check_owner(project_id, user_id)
    try:
        project_service.rename_shot(project_id, shot_id, req.title)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Shot not found")
    return {"ok": True}


@router.patch("/{project_id}/shots/{shot_id}/status")
def update_shot_status_endpoint(
    project_id: str,
    shot_id: str,
    req: UpdateStatusRequest,
    user_id: str = Depends(get_current_user),
):
    if req.status not in {"refined", "done"}:
        raise HTTPException(status_code=400, detail="status must be 'refined' or 'done'")
    _check_owner(project_id, user_id)
    try:
        project_service.update_shot_status(project_id, shot_id, req.status)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Shot not found")
    return {"ok": True}


@router.post("/{project_id}/shots/{shot_id}/chat")
def shot_chat(
    project_id: str,
    shot_id: str,
    req: ChatRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user),
):
    _check_owner(project_id, user_id)
    try:
        result = shot_service.shot_chat(
            project_id, shot_id, req.message,
            background_tasks,
            parent_version_ids=req.selected_version_ids,
            selected_ref_ids=req.selected_ref_ids,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project or shot not found")
    return {"reply": result["reply"], "generating": result["generating"]}


# ── Version tree ──────────────────────────────────────────────

@router.get("/{project_id}/shots/{shot_id}/versions")
def get_versions(
    project_id: str,
    shot_id: str,
    user_id: str = Depends(get_current_user),
):
    _check_owner(project_id, user_id)
    try:
        return project_service.list_versions(project_id, shot_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Shot not found")


@router.get("/{project_id}/shots/{shot_id}/versions/{version_id}")
def get_version_image(project_id: str, shot_id: str, version_id: str):
    """Serve a version image — no auth required (used via <img> tags)."""
    path = STORAGE_ROOT / project_id / "shots" / shot_id / "versions" / f"{version_id}.png"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Version image not found")
    return FileResponse(path, media_type="image/png")


@router.delete("/{project_id}/shots/{shot_id}/versions/{version_id}")
def delete_version(
    project_id: str,
    shot_id: str,
    version_id: str,
    user_id: str = Depends(get_current_user),
):
    _check_owner(project_id, user_id)
    try:
        project_service.delete_version(project_id, shot_id, version_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Shot or version not found")
    return {"ok": True}


@router.patch("/{project_id}/shots/{shot_id}/versions/{version_id}/activate")
def activate_version(
    project_id: str,
    shot_id: str,
    version_id: str,
    user_id: str = Depends(get_current_user),
):
    _check_owner(project_id, user_id)
    try:
        project_service.activate_version(project_id, shot_id, version_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"ok": True}


# ── Shot guides ───────────────────────────────────────────────

@router.get("/{project_id}/shots/{shot_id}/guides/{guide_type}.png")
def get_guide_sketch(project_id: str, shot_id: str, guide_type: str):
    """Serve the guide sketch image — no auth required (used via <img> tags)."""
    path = STORAGE_ROOT / project_id / "shots" / shot_id / "guides" / f"{guide_type}_sketch.png"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Sketch not found")
    return FileResponse(path, media_type="image/png")


@router.get("/{project_id}/shots/{shot_id}/guides/{guide_type}")
def get_guide(
    project_id: str,
    shot_id: str,
    guide_type: str,
    user_id: str = Depends(get_current_user),
):
    _check_owner(project_id, user_id)
    result = shot_guide_service.get_guide(project_id, shot_id, guide_type)
    if result is None:
        raise HTTPException(status_code=404, detail="Guide not generated yet")
    return result


@router.post("/{project_id}/shots/{shot_id}/guides/{guide_type}")
def generate_guide(
    project_id: str,
    shot_id: str,
    guide_type: str,
    user_id: str = Depends(get_current_user),
):
    _check_owner(project_id, user_id)
    try:
        return shot_guide_service.generate_guide(project_id, shot_id, guide_type)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Shot reference nodes (r-nodes) ────────────────────────────────────────────

class SetRefTypeRequest(BaseModel):
    ref_type: str


@router.post("/{project_id}/shots/{shot_id}/refs")
def upload_shot_ref(
    project_id: str,
    shot_id: str,
    background_tasks: BackgroundTasks,
    image: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
):
    """Upload a user reference image as an r-node. Type must be set separately."""
    _check_owner(project_id, user_id)
    try:
        entry = project_service.add_shot_ref(project_id, shot_id, image.file.read())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Shot not found")
    return entry


@router.get("/{project_id}/shots/{shot_id}/refs")
def list_shot_refs(
    project_id: str,
    shot_id: str,
    user_id: str = Depends(get_current_user),
):
    _check_owner(project_id, user_id)
    try:
        return project_service.list_shot_refs(project_id, shot_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Shot not found")


@router.patch("/{project_id}/shots/{shot_id}/refs/{ref_id}/type")
def set_ref_type(
    project_id: str,
    shot_id: str,
    ref_id: str,
    req: SetRefTypeRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user),
):
    """Set r-node type and kick off background processing."""
    _check_owner(project_id, user_id)
    valid = {"pose", "background", "weapon", "costume", "lighting", "expression"}
    if req.ref_type not in valid:
        raise HTTPException(status_code=400, detail=f"ref_type must be one of: {sorted(valid)}")
    try:
        background_tasks.add_task(
            project_service.set_shot_ref_type, project_id, shot_id, ref_id, req.ref_type
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"ok": True, "ref_id": ref_id, "ref_type": req.ref_type, "status": "processing"}


@router.get("/{project_id}/shots/{shot_id}/refs/{ref_id}/original")
def get_ref_original(project_id: str, shot_id: str, ref_id: str):
    """Serve the original r-node image — no auth (used via <img> tags)."""
    try:
        path = project_service.get_shot_ref_file(project_id, shot_id, ref_id, "original")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Ref not found")
    return FileResponse(path, media_type="image/png")


@router.get("/{project_id}/shots/{shot_id}/refs/{ref_id}/processed")
def get_ref_processed(project_id: str, shot_id: str, ref_id: str):
    """Serve the processed r-node image — no auth (used via <img> tags)."""
    try:
        path = project_service.get_shot_ref_file(project_id, shot_id, ref_id, "processed")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Processed ref not ready")
    return FileResponse(path, media_type="image/png")


@router.delete("/{project_id}/shots/{shot_id}/refs/{ref_id}")
def delete_shot_ref(
    project_id: str,
    shot_id: str,
    ref_id: str,
    user_id: str = Depends(get_current_user),
):
    _check_owner(project_id, user_id)
    try:
        project_service.delete_shot_ref(project_id, shot_id, ref_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Ref not found")
    return {"ok": True}
