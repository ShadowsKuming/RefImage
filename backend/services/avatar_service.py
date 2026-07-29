"""
services/avatar_service.py — Per-character avatar (upload + crop)

Flow: user uploads a source image → picks a square crop frame → we crop it into a
256px avatar. Both the source and the crop rect are kept so the crop can be
re-adjusted later without re-uploading. An optional vision-model face-box gives a
smart initial crop.

Storage (namespaced by character id, ready for multiple characters):
  context/avatars/{cid}_src.<ext>   uploaded source
  context/avatars/{cid}.png         cropped 256px avatar
  context/avatars/{cid}.json        { src_ext, x, y, size }  (normalized 0-1)

LLM/vision is only touched by auto_crop_guess(), so this module isn't part of the
offline unit-test suite.
"""
import json
from pathlib import Path

from PIL import Image

STORAGE_ROOT = Path(__file__).parent.parent / "storage" / "projects"
_EXT_BY_TYPE = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
AVATAR_SIZE = 256


def _dir(project_id: str) -> Path:
    return STORAGE_ROOT / project_id / "context" / "avatars"


def _meta_path(project_id: str, cid: str) -> Path:
    return _dir(project_id) / f"{cid}.json"


def _read_meta(project_id: str, cid: str) -> dict | None:
    p = _meta_path(project_id, cid)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            return None
    return None


def source_path(project_id: str, cid: str) -> Path | None:
    meta = _read_meta(project_id, cid)
    if meta and meta.get("src_ext"):
        p = _dir(project_id) / f"{cid}_src.{meta['src_ext']}"
        if p.exists():
            return p
    # No dedicated avatar source (older/edge projects) → materialize one by copying
    # the character's reference image into the avatar source slot, ONCE. From then on
    # it's a real {cid}_src file that display / crop / auto-recognize all share — no
    # read-time fallback that can diverge between callers.
    return _materialize_source_from_ref(project_id, cid)


def _materialize_source_from_ref(project_id: str, cid: str) -> Path | None:
    refs_dir = STORAGE_ROOT / project_id / "context" / "refs"
    if not refs_dir.exists():
        return None
    refs = sorted(f for f in refs_dir.iterdir() if f.is_file())
    if not refs:
        return None
    ref = refs[0]
    ext = ref.suffix.lstrip(".").lower()
    ext = ext if ext in _EXT_BY_TYPE.values() else "jpg"
    d = _dir(project_id)
    d.mkdir(parents=True, exist_ok=True)
    dest = d / f"{cid}_src.{ext}"
    if not dest.exists():
        dest.write_bytes(ref.read_bytes())          # copy the ref into the avatar source slot
        meta = _read_meta(project_id, cid) or {}
        meta["src_ext"] = ext
        _meta_path(project_id, cid).write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    return dest


def avatar_path(project_id: str, cid: str) -> Path | None:
    p = _dir(project_id) / f"{cid}.png"
    return p if p.exists() else None


def avatar_url(project_id: str, cid: str) -> str | None:
    p = avatar_path(project_id, cid)
    if not p:
        return None
    return f"/projects/{project_id}/characters/{cid}/avatar?v={int(p.stat().st_mtime)}"


def source_url(project_id: str, cid: str) -> str | None:
    p = source_path(project_id, cid)
    if not p:
        return None
    return f"/projects/{project_id}/characters/{cid}/avatar/source?v={int(p.stat().st_mtime)}"


def crop_rect(project_id: str, cid: str) -> dict | None:
    meta = _read_meta(project_id, cid)
    if meta and all(k in meta for k in ("x", "y", "size")):
        return {"x": meta["x"], "y": meta["y"], "size": meta["size"]}
    return None


def save_source(project_id: str, cid: str, data: bytes, filename: str, content_type: str = "") -> str:
    """Store the uploaded source image. Returns its serving URL."""
    ext = _EXT_BY_TYPE.get(content_type.split(";")[0].strip())
    if not ext:
        tail = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
        ext = tail if tail in _EXT_BY_TYPE.values() else "jpg"
    d = _dir(project_id)
    d.mkdir(parents=True, exist_ok=True)
    # drop any prior source with a different extension
    for old in d.glob(f"{cid}_src.*"):
        old.unlink(missing_ok=True)
    (d / f"{cid}_src.{ext}").write_bytes(data)
    meta = _read_meta(project_id, cid) or {}
    meta["src_ext"] = ext
    _meta_path(project_id, cid).write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    return source_url(project_id, cid) or ""


def apply_crop(project_id: str, cid: str, x: float, y: float, size: float) -> str:
    """Crop the stored source by a normalized square rect (0-1 on the source) into
    a {cid}.png avatar. Returns the avatar URL. Clamps the rect into bounds."""
    src = source_path(project_id, cid)
    if not src:
        raise FileNotFoundError("No avatar source uploaded")
    im = Image.open(src).convert("RGB")
    W, H = im.size
    # normalized → pixels; keep it square in pixels using the smaller axis scale
    px, py = x * W, y * H
    ps = size * min(W, H) if size <= 1 else size
    # clamp square fully inside the image
    ps = max(16.0, min(ps, float(min(W, H))))
    px = max(0.0, min(px, W - ps))
    py = max(0.0, min(py, H - ps))
    box = (round(px), round(py), round(px + ps), round(py + ps))
    crop = im.crop(box).resize((AVATAR_SIZE, AVATAR_SIZE), Image.LANCZOS)
    crop.save(_dir(project_id) / f"{cid}.png")
    meta = _read_meta(project_id, cid) or {}
    meta.update({"x": x, "y": y, "size": size})
    _meta_path(project_id, cid).write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    return avatar_url(project_id, cid) or ""


def auto_crop_guess(project_id: str, cid: str) -> dict:
    """Ask the vision model for a square face box on the source, returned as a
    normalized rect { x, y, size } (size relative to min(W,H)). Falls back to a
    top-centered square if vision fails."""
    src = source_path(project_id, cid)
    if not src:
        raise FileNotFoundError("No avatar source uploaded")
    from tools import vision
    im = Image.open(src).convert("RGB")
    W, H = im.size
    b64, mt = vision.encode_image(src.read_bytes())
    prompt = (
        f"Anime character reference, image is {W}x{H} pixels. Give the center of the "
        "character's face and a good SQUARE avatar crop size in PIXELS, framing head+hair "
        '(top of hair to just below chin). Return ONLY JSON: {"cx": int, "cy": int, "size": int}.'
    )
    content = [{"type": "text", "text": prompt},
               {"type": "image", "source": {"type": "base64", "media_type": mt, "data": b64}}]
    try:
        out = vision.call([{"role": "user", "content": content}],
                          system="Precise vision annotator. Output only JSON.")
        j = json.loads(out[out.find("{"):out.rfind("}") + 1])
        cx, cy, s = float(j["cx"]), float(j["cy"]), float(j["size"])
        s = max(16.0, min(s, float(min(W, H))))
        x = max(0.0, min(cx - s / 2, W - s)) / W
        y = max(0.0, min(cy - s / 2, H - s)) / H
        size = s / min(W, H)
        return {"x": x, "y": y, "size": size}
    except Exception:
        s = min(W, H) * 0.6
        return {"x": (W - s) / 2 / W, "y": 0.03, "size": s / min(W, H)}
