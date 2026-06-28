"""
api/new_project.py — Endpoints for the new-project creation flow (Steps 1 & 2)

Step 1 — image upload & analysis:
  POST /new-project/verify-character   Check if a new image matches the existing session
  POST /new-project/analyze-image      Extract visual features; call repeatedly until done=True

Step 2 — character profile chat:
  POST /new-project/chat               Send a message to the profile agent; get reply + optional profile
"""
from fastapi import APIRouter, UploadFile, File, Form
from pydantic import BaseModel
from services import analyze_service

router = APIRouter()


# ── Step 2: profile chat ──────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message:         str
    history:         list[dict] = []
    visual_spec:     str | None = None
    current_profile: dict | None = None


@router.post("/chat")
async def chat(req: ChatRequest):
    """
    One turn of the character profile agent.
    The frontend sends the full chat history and current profile state on every
    request so the agent always has the live context (including manual edits).
    """
    return analyze_service.profile_chat(
        req.message, req.history, req.visual_spec, req.current_profile
    )


# ── Step 1: image analysis ────────────────────────────────────────────────────

@router.post("/verify-character")
async def verify_character(
    file:       UploadFile = File(...),
    session_id: str        = Form(...),
):
    """
    Check if an image shows the same character as the current session.
    Called before queuing a new image for extraction; fails open (returns
    same=True) if verification itself errors, to avoid blocking the user.
    """
    image_bytes = await file.read()
    return analyze_service.verify_character(image_bytes, session_id)


@router.post("/analyze-image")
async def analyze_image(
    file:       UploadFile  = File(...),
    session_id: str | None  = Form(default=None),
):
    """
    Extract visual features from a reference image.
    Omit session_id on the first call to start a new session; pass the returned
    session_id on subsequent calls to add more images to the same session.
    Returns done=True once all visual fields are filled.
    """
    image_bytes = await file.read()
    return analyze_service.start_or_continue(image_bytes, session_id)
