"""
api/project.py — Endpoints for saved projects

POST   /projects/create                    Save a new project to disk
GET    /projects/{id}                      Load full project data for the project page
GET    /projects/{id}/refs/{filename}      Serve a reference image file
POST   /projects/{id}/extra-refs           Upload a supplementary reference image
GET    /projects/{id}/extra-refs/{file}    Serve a supplementary reference image
POST   /projects/{id}/chat                 AI planning assistant (multi-turn)
"""
import json
import mimetypes
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from services import project_service, guide_service, export_service

router = APIRouter()


class ChatMessage(BaseModel):
    role: str     # 'user' | 'agent'
    text: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []


@router.post("/create")
async def create(
    images:      list[UploadFile] = File(...),
    extracted:   str = Form(...),    # JSON — raw field-level extraction from Step 1
    visual_spec: str = Form(...),    # Plain text appearance description for LLM prompts
    world:       str = Form(...),    # JSON — { series, worldSetting }
    character:   str = Form(...),    # JSON — { character, series, characterBackground }
):
    """
    Persist a completed new-project session to disk.
    Returns: { project_id, character, series, created_at }
    """
    image_data  = [await f.read() for f in images]
    image_names = [f.filename or "image.jpg" for f in images]

    meta = project_service.create_project(
        images=image_data,
        image_names=image_names,
        extracted=json.loads(extracted),
        visual_spec=json.loads(visual_spec),  # multilang dict {zh, en, ja}
        world=json.loads(world),
        character=json.loads(character),
    )
    return meta


@router.get("/{project_id}")
def get_project(project_id: str):
    """
    Return the full project context for the project page.
    Merges meta.json, world.json, character.json, visual_spec.txt, and refs list.
    """
    try:
        return project_service.get_project(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")


@router.get("/{project_id}/refs/{filename}")
def get_ref(project_id: str, filename: str):
    """Serve an original reference image (used for visual spec extraction)."""
    try:
        path = project_service.get_ref_path(project_id, filename)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Image not found")

    media_type = mimetypes.guess_type(str(path))[0] or "image/jpeg"
    return FileResponse(path, media_type=media_type)


@router.post("/{project_id}/extra-refs")
async def add_extra_ref(project_id: str, image: UploadFile = File(...)):
    """Upload a supplementary reference image (not used for extraction)."""
    try:
        project_service.get_project(project_id)  # verify project exists
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")

    image_bytes = await image.read()
    url = project_service.add_extra_ref(project_id, image_bytes, image.filename or "ref.jpg")
    return {"url": url}


@router.get("/{project_id}/extra-refs/{filename}")
def get_extra_ref(project_id: str, filename: str):
    """Serve a supplementary reference image."""
    try:
        path = project_service.get_extra_ref_path(project_id, filename)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Image not found")

    media_type = mimetypes.guess_type(str(path))[0] or "image/jpeg"
    return FileResponse(path, media_type=media_type)


@router.get("/{project_id}/export")
def export_project(project_id: str):
    """Export a project as an encrypted .refimg file."""
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
def project_chat(project_id: str, req: ChatRequest):
    """AI planning assistant — delegates entirely to guide_service."""
    try:
        result = guide_service.planning_chat(
            project_id,
            req.message,
            [m.model_dump() for m in req.history],
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"reply": result["reply"], "brief": result["brief"]}


