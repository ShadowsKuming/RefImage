"""
services/export_service.py — Project export / import in encrypted .refimg format

Export: project folder → zip → Fernet-encrypted → .refimg bytes
Import: .refimg bytes → decrypt → validate structure → extract to storage

Encryption: Fernet (AES-128-CBC + HMAC-SHA256).
Key source: REFIMG_SECRET_KEY env var (Fernet base64 key).

.refimg internal structure (zip contents):
    meta.json
    context/
    plan/
    shots/
"""
import io
import json
import os
import shutil
import uuid
import zipfile
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../../.env"))

STORAGE_ROOT = Path(__file__).parent.parent / "storage" / "projects"

REQUIRED_ENTRIES = {"meta.json", "context/"}


def _fernet() -> Fernet:
    key = os.getenv("REFIMG_SECRET_KEY")
    if not key:
        raise RuntimeError("REFIMG_SECRET_KEY not set in environment")
    return Fernet(key.encode())


def export_project(project_id: str) -> bytes:
    """
    Pack a project into an encrypted .refimg blob.
    Raises FileNotFoundError if the project doesn't exist.
    """
    project_dir = STORAGE_ROOT / project_id
    if not project_dir.exists():
        raise FileNotFoundError(f"Project {project_id!r} not found")

    # Zip the project directory in memory
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(project_dir.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(project_dir))
    zip_bytes = buf.getvalue()

    return _fernet().encrypt(zip_bytes)


def import_project(data: bytes) -> dict:
    """
    Decrypt and extract a .refimg blob into storage.
    Returns the new project's summary { project_id, character, series }.
    Raises:
        ValueError   — wrong format / decryption failed / invalid structure
        RuntimeError — key not configured
    """
    try:
        zip_bytes = _fernet().decrypt(data)
    except InvalidToken:
        raise ValueError("无法解密文件，可能不是有效的 .refimg 文件或已损坏")

    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile:
        raise ValueError("解密后的数据不是有效的 zip 文件")

    _validate_structure(zf)

    # Read meta to get original project_id and character info
    meta = json.loads(zf.read("meta.json"))
    original_id = meta.get("project_id", "")

    # Use original ID if slot is free, otherwise generate a new one
    target_id = original_id if original_id and not (STORAGE_ROOT / original_id).exists() else str(uuid.uuid4())
    target_dir = STORAGE_ROOT / target_id
    target_dir.mkdir(parents=True, exist_ok=True)

    try:
        zf.extractall(target_dir)
    except Exception as e:
        shutil.rmtree(target_dir, ignore_errors=True)
        raise ValueError(f"解压失败：{e}")

    # Update meta.json with the (possibly new) project_id
    if target_id != original_id:
        meta["project_id"] = target_id
        (target_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))

    return {
        "project_id": target_id,
        "character":  meta.get("character", ""),
        "series":     meta.get("series", ""),
    }


def _validate_structure(zf: zipfile.ZipFile) -> None:
    """Raise ValueError if the zip is missing required entries."""
    names = set(zf.namelist())
    if "meta.json" not in names:
        raise ValueError("导入失败：文件缺少 meta.json，不是有效的 RefImage 项目")
    has_context = any(n.startswith("context/") for n in names)
    if not has_context:
        raise ValueError("导入失败：文件缺少 context/ 目录，不是有效的 RefImage 项目")
