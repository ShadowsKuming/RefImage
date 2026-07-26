"""
api/project.py — Endpoints for saved projects

POST   /projects/create                    Save a new project to disk
GET    /projects/{id}                      Load full project data for the project page
GET    /projects/{id}/refs/{filename}      Serve a reference image file (no auth — img tag)
POST   /projects/{id}/extra-refs           Upload a supplementary reference image
GET    /projects/{id}/extra-refs/{file}    Serve a supplementary reference image (no auth — img tag)
GET    /projects/{id}/export               Export project as .refimg file
POST   /projects/{id}/chat                 AI planning assistant (multi-turn)
"""
import json
import mimetypes
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from api.auth import get_current_user
from services import project_service, guide_service, export_service, wardrobe_service, cover_service, avatar_service

router = APIRouter()


def _check_owner(project_id: str, user_id: str) -> None:
    """Raise HTTP 404/403 based on project existence and ownership."""
    try:
        project_service.assert_owner(project_id, user_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")


class ChatMessage(BaseModel):
    role: str     # 'user' | 'agent'
    text: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []
    reply_lang: str = "zh"


@router.post("/create")
async def create(
    images:         list[UploadFile] = File(...),
    extracted_i18n: str = Form(...),
    visual_spec:    str = Form(...),
    world:          str = Form(...),
    character:      str = Form(...),
    user_id:        str = Depends(get_current_user),
):
    """
    Persist a completed new-project session to disk.
    Returns: { project_id, character, series, created_at }
    Raises 429 if the user has reached PROJECT_LIMIT projects.
    """
    from config import PROJECT_LIMIT
    if PROJECT_LIMIT > 0:
        current = project_service.count_user_projects(user_id)
        if current >= PROJECT_LIMIT:
            raise HTTPException(
                status_code=429,
                detail=f"已达项目上限（{PROJECT_LIMIT} 个）。请先导出并删除旧项目，再新建。",
            )

    image_data  = [await f.read() for f in images]
    image_names = [f.filename or "image.jpg" for f in images]

    meta = project_service.create_project(
        images=image_data,
        image_names=image_names,
        extracted_i18n=json.loads(extracted_i18n),
        visual_spec=json.loads(visual_spec),
        world=json.loads(world),
        character=json.loads(character),
        owner_id=user_id,
    )
    return meta


@router.delete("/{project_id}")
def delete_project(project_id: str, user_id: str = Depends(get_current_user)):
    """Delete a project and all its data. Irreversible."""
    _check_owner(project_id, user_id)
    try:
        project_service.delete_project(project_id, user_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"ok": True}


@router.get("/{project_id}")
def get_project(project_id: str, user_id: str = Depends(get_current_user)):
    _check_owner(project_id, user_id)
    try:
        return project_service.get_project(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")


class PlanDataRequest(BaseModel):
    data: dict


@router.put("/{project_id}/plan")
def save_plan(
    project_id: str,
    req: PlanDataRequest,
    user_id: str = Depends(get_current_user),
):
    """Coarse save of the plan-panel data (equipment/notes/schedule/etc.)."""
    _check_owner(project_id, user_id)
    project_service.save_plan_data(project_id, req.data)
    return {"ok": True}


@router.put("/{project_id}/wardrobe")
def save_wardrobe(
    project_id: str,
    req: PlanDataRequest,
    user_id: str = Depends(get_current_user),
):
    """Coarse save of the costume/props data (left 设定 panel)."""
    _check_owner(project_id, user_id)
    wardrobe_service.save_wardrobe(project_id, req.data)
    return {"ok": True}


@router.post("/{project_id}/cover/grab")
def grab_cover(project_id: str, user_id: str = Depends(get_current_user)):
    """Auto-grab a work cover: image search → vision-pick → save locally.
    Returns { url, source, title }."""
    _check_owner(project_id, user_id)
    try:
        return cover_service.grab_cover(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/{project_id}/cover")
async def upload_cover(
    project_id: str,
    image: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
):
    """Replace the work cover with a user-uploaded image."""
    _check_owner(project_id, user_id)
    data = await image.read()
    url = cover_service.save_uploaded_cover(project_id, data, image.filename or "cover.jpg")
    return {"url": url}


@router.get("/{project_id}/cover")
def get_cover(project_id: str):
    """Serve the stored work cover — no auth (used via <img> tags)."""
    path = cover_service.cover_path(project_id)
    if not path:
        raise HTTPException(status_code=404, detail="No cover")
    media_type = mimetypes.guess_type(str(path))[0] or "image/jpeg"
    return FileResponse(path, media_type=media_type)


class AvatarCropRequest(BaseModel):
    x: float
    y: float
    size: float


@router.post("/{project_id}/characters/{cid}/avatar")
async def upload_avatar_source(
    project_id: str,
    cid: str,
    image: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
):
    """Upload a source image for a character avatar. Returns { src_url }."""
    _check_owner(project_id, user_id)
    data = await image.read()
    url = avatar_service.save_source(project_id, cid, data, image.filename or "avatar.jpg",
                                     image.content_type or "")
    return {"src_url": url}


@router.put("/{project_id}/characters/{cid}/avatar/crop")
def crop_avatar(
    project_id: str,
    cid: str,
    req: AvatarCropRequest,
    user_id: str = Depends(get_current_user),
):
    """Crop the uploaded source by a normalized square rect into the avatar."""
    _check_owner(project_id, user_id)
    try:
        url = avatar_service.apply_crop(project_id, cid, req.x, req.y, req.size)
    except FileNotFoundError:
        raise HTTPException(status_code=400, detail="No avatar source uploaded")
    return {"avatar_url": url}


@router.post("/{project_id}/characters/{cid}/avatar/auto")
def auto_avatar_crop(project_id: str, cid: str, user_id: str = Depends(get_current_user)):
    """Vision-model face-box guess → normalized { x, y, size } to seed the frame."""
    _check_owner(project_id, user_id)
    try:
        return avatar_service.auto_crop_guess(project_id, cid)
    except FileNotFoundError:
        raise HTTPException(status_code=400, detail="No avatar source uploaded")


@router.get("/{project_id}/characters/{cid}/avatar")
def get_avatar(project_id: str, cid: str):
    """Serve the cropped avatar — no auth (used via <img>)."""
    path = avatar_service.avatar_path(project_id, cid)
    if not path:
        raise HTTPException(status_code=404, detail="No avatar")
    return FileResponse(path, media_type="image/png")


@router.get("/{project_id}/characters/{cid}/avatar/source")
def get_avatar_source(project_id: str, cid: str):
    """Serve the avatar source image — no auth (used in the crop editor)."""
    path = avatar_service.source_path(project_id, cid)
    if not path:
        raise HTTPException(status_code=404, detail="No avatar source")
    media_type = mimetypes.guess_type(str(path))[0] or "image/jpeg"
    return FileResponse(path, media_type=media_type)


@router.get("/{project_id}/refs/{filename}")
def get_ref(project_id: str, filename: str):
    """Serve a reference image — no auth required (used via <img> tags)."""
    try:
        path = project_service.get_ref_path(project_id, filename)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Image not found")
    media_type = mimetypes.guess_type(str(path))[0] or "image/jpeg"
    return FileResponse(path, media_type=media_type)


@router.post("/{project_id}/extra-refs")
async def add_extra_ref(
    project_id: str,
    image: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
):
    _check_owner(project_id, user_id)
    image_bytes = await image.read()
    url = project_service.add_extra_ref(project_id, image_bytes, image.filename or "ref.jpg")
    return {"url": url}


@router.get("/{project_id}/extra-refs/{filename}")
def get_extra_ref(project_id: str, filename: str):
    """Serve supplementary reference image — no auth required (used via <img> tags)."""
    try:
        path = project_service.get_extra_ref_path(project_id, filename)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Image not found")
    media_type = mimetypes.guess_type(str(path))[0] or "image/jpeg"
    return FileResponse(path, media_type=media_type)


@router.get("/{project_id}/export")
def export_project(project_id: str, user_id: str = Depends(get_current_user)):
    _check_owner(project_id, user_id)
    try:
        data = export_service.export_project(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{project_id}.refimg"'},
    )


@router.post("/{project_id}/chat")
def project_chat(
    project_id: str,
    req: ChatRequest,
    user_id: str = Depends(get_current_user),
):
    _check_owner(project_id, user_id)
    try:
        result = guide_service.planning_chat(
            project_id,
            req.message,
            [m.model_dump() for m in req.history],
            req.reply_lang,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"reply": result["reply"], "brief": result["brief"], "plan": result.get("plan")}
