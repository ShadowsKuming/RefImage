"""
api/home.py — Home page endpoints

GET  /        List all projects as lightweight summaries
POST /import  Import a project from an encrypted .refimg file
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from api.auth import get_current_user
from services import home_service, export_service, project_service

router = APIRouter()


@router.get("/")
def list_projects(user_id: str = Depends(get_current_user)):
    """Return current user's projects sorted newest first, as summary cards."""
    return home_service.list_projects(user_id)


@router.post("/import")
async def import_project(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
):
    """Decrypt and import a .refimg project file."""
    if not file.filename or not file.filename.endswith(".refimg"):
        raise HTTPException(status_code=400, detail="请上传 .refimg 文件")
    data = await file.read()
    try:
        result = export_service.import_project(data)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    project_service.set_project_owner(result["project_id"], user_id)
    return result
