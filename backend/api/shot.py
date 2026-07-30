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


class RefineRequest(BaseModel):
    params: dict = {}


class CreateShotRequest(BaseModel):
    title: str
    mood: str = ""
    scene_description: str = ""
    character_id: str | None = None


class UpdateStatusRequest(BaseModel):
    status: str
    final_version_id: str | None = None


class RenameShotRequest(BaseModel):
    title: str


class ShotCharacterRequest(BaseModel):
    character_id: str


class ShotAttrsRequest(BaseModel):
    priority: str | None = None
    essential: bool | None = None


@router.post("/{project_id}/shots")
def create_shot(
    project_id: str,
    req: CreateShotRequest,
    user_id: str = Depends(get_current_user),
):
    _check_owner(project_id, user_id)
    try:
        shot = project_service.create_shot(
            project_id, req.title, req.mood, req.scene_description, req.character_id,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    return shot


@router.patch("/{project_id}/shots/{shot_id}/character")
def set_shot_character(
    project_id: str,
    shot_id: str,
    req: ShotCharacterRequest,
    user_id: str = Depends(get_current_user),
):
    _check_owner(project_id, user_id)
    try:
        project_service.set_shot_character(project_id, shot_id, req.character_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Shot not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


@router.patch("/{project_id}/shots/{shot_id}/attrs")
def set_shot_attrs(
    project_id: str,
    shot_id: str,
    req: ShotAttrsRequest,
    user_id: str = Depends(get_current_user),
):
    """Update a shot's priority (high|mid|low) and/or essential (必拍/可选)."""
    _check_owner(project_id, user_id)
    try:
        return project_service.set_shot_attrs(project_id, shot_id, req.priority, req.essential)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Shot not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


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
    # refined → record the chosen final version; done (unlock) → clear it.
    final = (req.final_version_id or "") if req.status == "refined" else ""
    try:
        project_service.update_shot_status(project_id, shot_id, req.status, final_version_id=final)
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
    return {"reply": result["reply"], "generating": result["generating"],
            "options": result.get("options", []),
            "stage": result.get("stage", "chat"), "camera": result.get("camera"),
            "title": result.get("title")}


@router.post("/{project_id}/shots/{shot_id}/versions/{version_id}/refine")
def refine_version(
    project_id: str,
    shot_id: str,
    version_id: str,
    req: RefineRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user),
):
    """Refine panel → regenerate: same content as this version, new visual params,
    branched as a new version. Returns immediately; frontend polls for the result."""
    _check_owner(project_id, user_id)
    try:
        return shot_service.refine_version(project_id, shot_id, version_id, req.params, background_tasks)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Shot or version not found")


# ── Stage 3: shot plan (拍摄方案) ──────────────────────────────

@router.get("/{project_id}/shots/{shot_id}/plan")
def get_shot_plan(project_id: str, shot_id: str, user_id: str = Depends(get_current_user)):
    """Cached shot plan, or null if not extracted yet."""
    _check_owner(project_id, user_id)
    from services import shot_plan_service
    return shot_plan_service.load_plan(project_id, shot_id)


@router.post("/{project_id}/shots/{shot_id}/plan")
def extract_shot_plan(project_id: str, shot_id: str, user_id: str = Depends(get_current_user)):
    """Extract the shooting plan for the selected final version (stage-3 提取)."""
    _check_owner(project_id, user_id)
    from services import shot_plan_service
    try:
        return shot_plan_service.extract_plan(project_id, shot_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Shot not found")
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


class SetLocationRequest(BaseModel):
    name: str
    indoor_outdoor: str = "均可"


@router.put("/{project_id}/shots/{shot_id}/plan/location")
def set_shot_location(project_id: str, shot_id: str, req: SetLocationRequest,
                      user_id: str = Depends(get_current_user)):
    """User picks/adds this shot's 取景地 → joins the project pool + set on the plan."""
    _check_owner(project_id, user_id)
    from services import shot_plan_service
    try:
        return shot_plan_service.set_location(project_id, shot_id, req.name, req.indoor_outdoor)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=404, detail=str(e))


class UpdatePlanFieldRequest(BaseModel):
    path: str
    value: object = ""


@router.put("/{project_id}/shots/{shot_id}/plan/field")
def update_plan_field(project_id: str, shot_id: str, req: UpdatePlanFieldRequest,
                      user_id: str = Depends(get_current_user)):
    """User edited a plan field (whitelisted dotted path)."""
    _check_owner(project_id, user_id)
    from services import shot_plan_service
    try:
        return shot_plan_service.update_field(project_id, shot_id, req.path, req.value)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Handbook sheet (Overleaf-style compile → project PDF page) ──

@router.get("/{project_id}/shots/{shot_id}/sheet")
def get_shot_sheet(project_id: str, shot_id: str, user_id: str = Depends(get_current_user)):
    """The compiled handbook page snapshot, or null if never compiled."""
    _check_owner(project_id, user_id)
    from services import shot_plan_service
    return shot_plan_service.load_sheet(project_id, shot_id)


@router.post("/{project_id}/shots/{shot_id}/sheet")
def compile_shot_sheet(project_id: str, shot_id: str, user_id: str = Depends(get_current_user)):
    """Compile: snapshot the current plan into the frozen handbook page."""
    _check_owner(project_id, user_id)
    from services import shot_plan_service
    try:
        return shot_plan_service.compile_sheet(project_id, shot_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


class SetCompletedRequest(BaseModel):
    completed: bool = True


@router.put("/{project_id}/shots/{shot_id}/completed")
def set_shot_completed(project_id: str, shot_id: str, req: SetCompletedRequest,
                       user_id: str = Depends(get_current_user)):
    """Mark 已完成 (only meaningful once the handbook page is compiled)."""
    _check_owner(project_id, user_id)
    from services import project_service, shot_plan_service
    if req.completed and shot_plan_service.load_sheet(project_id, shot_id) is None:
        raise HTTPException(status_code=400, detail="compile the sheet first")
    try:
        project_service.set_shot_completed(project_id, shot_id, req.completed)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Shot not found")
    return {"completed": req.completed}


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
