"""
api/auth.py — Fixed-token authentication for RefImage

Configure tokens via REFIMG_TOKENS env var:
  REFIMG_TOKENS=token1:user_id1,token2:user_id2

  "token:user_id" → maps token to explicit user_id
  "token"         → token itself becomes the user_id

Endpoints:
  GET /auth/me   Return current user_id (used by login page to verify token)
"""
import os
from fastapi import APIRouter, Header, HTTPException, Depends

router = APIRouter()


def get_current_user(authorization: str | None = Header(default=None)) -> str:
    """FastAPI dependency — validates Bearer token and returns user_id."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    token = authorization[7:].strip()
    raw = os.getenv("REFIMG_TOKENS", "")
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if ":" in entry:
            t, uid = entry.split(":", 1)
            if t.strip() == token:
                return uid.strip()
        elif entry == token:
            return entry
    raise HTTPException(status_code=401, detail="Token 无效")


@router.get("/me")
def me(user_id: str = Depends(get_current_user)):
    """Return the current user's ID — used by login page to verify token."""
    return {"user_id": user_id}
