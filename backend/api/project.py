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
from services import project_service, guide_service, export_service

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


@router.post("/create")
async def create(
    images:      list[UploadFile] = File(...),
    extracted:   str = Form(...),
    visual_spec: str = Form(...),
    world:       str = Form(...),
    character:   str = Form(...),
    user_id:     str = Depends(get_current_user),
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
        extracted=json.loads(extracted),
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
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"reply": result["reply"], "brief": result["brief"]}
