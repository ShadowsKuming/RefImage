"""
api/home.py — Home page endpoints

GET  /        List all projects as lightweight summaries
POST /import  Import a project from an encrypted .refimg file
"""
from fastapi import APIRouter, HTTPException, UploadFile, File
from services import home_service, export_service

router = APIRouter()


@router.get("/")
def list_projects():
    """Return all projects sorted newest first, as summary cards."""
    return home_service.list_projects()


@router.post("/import")
async def import_project(file: UploadFile = File(...)):
    """Decrypt and import a .refimg project file."""
    if not file.filename or not file.filename.endswith(".refimg"):
        raise HTTPException(status_code=400, detail="请上传 .refimg 文件")
    data = await file.read()
    try:
        result = export_service.import_project(data)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return result
