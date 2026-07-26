"""
services/cover_service.py — Auto-grab a cover image for the work (作品设定)

Pipeline: Serper image search (work scene / key-visual) → download candidates →
vision model picks the best landscape banner → save locally to context/cover.<ext>
so the frontend serves a stable local URL (dodges hotlink 403s and keeps the
picked image even if the source vanishes).

This is the 作品 (work) cover — a landscape atmospheric/world image, NOT the
character portrait. It uses the LLM/vision layer, so (unlike plan_service) it is
not part of the offline unit-test suite.
"""
import json
from pathlib import Path

import requests

from tools import vision
from tools.search import image_search

STORAGE_ROOT = Path(__file__).parent.parent / "storage" / "projects"

_UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                     "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"}
_EXT_BY_TYPE = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif"}


def cover_path(project_id: str) -> Path | None:
    """Path to the stored cover file, or None if none grabbed yet."""
    ctx = STORAGE_ROOT / project_id / "context"
    for ext in ("jpg", "png", "webp", "gif"):
        p = ctx / f"cover.{ext}"
        if p.exists():
            return p
    return None


def cover_url(project_id: str) -> str | None:
    """Frontend URL for the cover, or None. Cache-busted by file mtime so a
    re-grab (same filename) actually refreshes in the browser."""
    p = cover_path(project_id)
    if not p:
        return None
    return f"/projects/{project_id}/cover?v={int(p.stat().st_mtime)}"


def save_uploaded_cover(project_id: str, data: bytes, filename: str) -> str | None:
    """Replace the cover with a user-uploaded image. Returns the new cover URL."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
    if ext not in _EXT_BY_TYPE.values():
        ext = "jpg"
    old = cover_path(project_id)
    if old:
        old.unlink(missing_ok=True)
    ctx = STORAGE_ROOT / project_id / "context"
    ctx.mkdir(parents=True, exist_ok=True)
    (ctx / f"cover.{ext}").write_bytes(data)
    return cover_url(project_id)


def _candidate_queries(series: str, world: dict) -> list[tuple[str, str, str]]:
    iconic = world.get("iconic_settings") or []
    queries = [
        (f"{series} キービジュアル", "jp", "ja"),
        (f"{series} 场景 背景", "cn", "zh-cn"),
    ]
    if iconic:
        queries.append((f"{series} {iconic[0]}", "jp", "ja"))
    return queries


def _gather_candidates(series: str, world: dict, want: int = 6) -> list[dict]:
    seen, cands = set(), []
    for q, gl, hl in _candidate_queries(series, world):
        try:
            results = image_search(q, num=10, lang=hl)
        except Exception:
            continue
        for im in results:
            url, w, h = im["imageUrl"], im["width"], im["height"]
            if url in seen:
                continue
            # want landscape-ish, decent resolution (banner, not a portrait/icon)
            if w < 600 or h < 300 or w < h:
                continue
            seen.add(url)
            cands.append(im)
    return cands[:want]


def _download(url: str) -> tuple[bytes, str] | None:
    try:
        r = requests.get(url, headers=_UA, timeout=15)
    except Exception:
        return None
    if not r.ok or len(r.content) < 3000:
        return None
    ctype = (r.headers.get("Content-Type") or "").split(";")[0].strip()
    ext = _EXT_BY_TYPE.get(ctype)
    if not ext:
        ext = url.rsplit(".", 1)[-1].split("?")[0].lower()
        ext = ext if ext in _EXT_BY_TYPE.values() else "jpg"
    return r.content, ext


def _pick(series: str, downloaded: list[tuple[dict, bytes, str]]) -> int:
    """Ask the vision model which candidate is the best work cover. Returns the
    index; falls back to 0 on any parse/logic failure."""
    content = [{"type": "text", "text":
        f"这些是《{series}》的候选封面图，用于「作品设定」页顶部的横版封面。"
        f"请选出最适合的一张：能代表作品的世界观/氛围、画面干净、"
        f"无明显文字水印或商品包装、构图完整。按顺序编号 0..{len(downloaded)-1}，"
        f"只返回 JSON：{{\"best\": <编号>, \"reason\": \"...\"}}"}]
    for i, (_, data, _ext) in enumerate(downloaded):
        b64, mt = vision.encode_image(data)
        content.append({"type": "text", "text": f"图 {i}："})
        content.append({"type": "image", "source": {"type": "base64", "media_type": mt, "data": b64}})
    try:
        out = vision.call([{"role": "user", "content": content}],
                          system="你是资深视觉编辑，负责挑选作品封面。只输出 JSON。")
        j = json.loads(out[out.find("{"):out.rfind("}") + 1])
        idx = int(j.get("best", 0))
        return idx if 0 <= idx < len(downloaded) else 0
    except Exception:
        return 0


def grab_cover(project_id: str) -> dict:
    """Search → download → vision-pick → save context/cover.<ext>.
    Returns { url, source, title }. Raises FileNotFoundError if the project is
    missing, RuntimeError if no usable candidate could be fetched."""
    from services import project_service
    proj = project_service.get_project(project_id)          # raises FileNotFoundError
    series = proj.get("series") or proj.get("character") or ""
    world = (proj.get("world") or {}).get("worldSetting") or {}

    downloaded: list[tuple[dict, bytes, str]] = []
    for im in _gather_candidates(series, world):
        got = _download(im["imageUrl"])
        if got:
            downloaded.append((im, got[0], got[1]))

    if not downloaded:
        raise RuntimeError("没有可用的候选封面图（搜索无结果或全部下载失败）")

    idx = _pick(series, downloaded)
    im, data, ext = downloaded[idx]

    # Remove any prior cover (extension may differ), then write the new one.
    old = cover_path(project_id)
    if old:
        old.unlink(missing_ok=True)
    dest = STORAGE_ROOT / project_id / "context" / f"cover.{ext}"
    dest.write_bytes(data)

    return {"url": cover_url(project_id), "source": im.get("source", ""), "title": im.get("title", "")}
