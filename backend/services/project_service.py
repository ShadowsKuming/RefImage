"""
services/project_service.py — Project persistence (read + write)

On-disk layout per project:
  storage/projects/{uuid}/
    meta.json              — project_id, character, series, created_at
    context/               — character/world context (read-only after creation)
      refs/                — original reference images used for visual spec extraction
      extra_refs/          — supplementary reference images added later
      extracted.json       — raw per-field extraction output from Step 1
      visual_spec.json     — multilingual appearance spec { zh, en, ja, prompt }
      world.json           — { series, worldSetting }
      character.json       — { character, series, characterBackground }
    plan/                  — global shooting plan (written by AI planning assistant)
      brief.json           — structured plan: locations, equipment, timeline, style
      chat_history.json    — AI planning assistant conversation history
    shots/                 — individual photoshoot sessions
      {shot_id}/
        shot.json          — title, mood, description, status, created_at
        generated.png      — AI-generated example image (added later)
        guides/            — guide cards per body part (added later)

context/ is the immutable source of truth for the character.
plan/ and shots/ are writable by the AI planning assistant and the user.
"""
import json
import os
import uuid
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../../.env"))

STORAGE_ROOT = Path(__file__).parent.parent / "storage" / "projects"


def _extract_english_name(char_name: str) -> str:
    """Extract the English-only name from a multilingual name string.
    e.g. '樱野玖璃梦（桜野くりむ/Kurimu Sakurano）' → 'Kurimu Sakurano'
    Falls back to the original string if no English portion is found.
    """
    import re
    # Match last segment after '/' inside （）, or any Latin word sequence
    m = re.search(r'/([A-Za-z][^/）)]+)）?$', char_name)
    if m:
        return m.group(1).strip()
    # Fallback: return as-is if already English
    return char_name


def _build_image_prompt(char_name: str, en_spec: str) -> str:
    """Generate a concise image-prompt string from the English visual spec.
    Only includes hair, eyes, face — outfit is locked via reference image at generation time.
    """
    import anthropic
    from config import FAST_LLM_MODEL
    en_name = _extract_english_name(char_name)
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    resp = client.messages.create(
        model=FAST_LLM_MODEL,
        max_tokens=150,
        messages=[{
            "role": "user",
            "content": (
                f"Convert this character appearance description into a concise image prompt string.\n\n"
                f"Character name (English only): {en_name}\n\n"
                f"Rules:\n"
                f"- Single flowing sentence, no labels or headers\n"
                f"- Must start with \"{en_name}.\"\n"
                f"- Include ONLY: hair color, hair style, hair accessories, eye color, face shape, skin tone\n"
                f"- Do NOT include: outfit, clothing, shoes, body proportions, hex codes\n"
                f"- End with: \"Preserve her exact outfit, colors, and accessories exactly as shown in the reference image. Do not redesign or reinterpret the costume.\"\n"
                f"- Output only the prompt string, nothing else\n\n"
                f"Source:\n{en_spec}"
            ),
        }],
    )
    return resp.content[0].text.strip()


def assert_owner(project_id: str, user_id: str) -> None:
    """Raise FileNotFoundError if project missing, PermissionError if wrong user."""
    meta_file = STORAGE_ROOT / project_id / "meta.json"
    if not meta_file.exists():
        raise FileNotFoundError(f"Project {project_id!r} not found")
    meta = json.loads(meta_file.read_text())
    owner = meta.get("owner_id") or os.getenv("DEFAULT_OWNER_ID", "default")
    if owner != user_id:
        raise PermissionError("Access denied")


def set_project_owner(project_id: str, owner_id: str) -> None:
    """Set owner_id on an existing project (used after import)."""
    meta_file = STORAGE_ROOT / project_id / "meta.json"
    if not meta_file.exists():
        raise FileNotFoundError(f"Project {project_id!r} not found")
    meta = json.loads(meta_file.read_text())
    meta["owner_id"] = owner_id
    meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2))


def create_project(
    images: list[bytes],
    image_names: list[str],
    extracted: dict,
    visual_spec: dict,  # { zh: str, en: str, ja: str }
    world: dict,        # { series, worldSetting }
    character: dict,    # { character, series, characterBackground }
    owner_id: str = "",
) -> dict:
    """
    Persist a new project to disk and return its metadata.
    Initialises the full directory structure: context/, plan/, shots/.

    Returns: { project_id, character, series, created_at }
    """
    project_id = str(uuid.uuid4())
    base = STORAGE_ROOT / project_id

    # ── context/ ──────────────────────────────────────────────
    refs_dir = base / "context" / "refs"
    refs_dir.mkdir(parents=True, exist_ok=True)

    for i, (img_bytes, name) in enumerate(zip(images, image_names)):
        ext = Path(name).suffix or ".jpg"
        (refs_dir / f"{i+1:03d}{ext}").write_bytes(img_bytes)

    ctx = base / "context"
    (ctx / "extracted.json").write_text(json.dumps(extracted,    ensure_ascii=False, indent=2))
    visual_spec["prompt"] = _build_image_prompt(character["character"], visual_spec["en"])
    (ctx / "visual_spec.json").write_text(json.dumps(visual_spec, ensure_ascii=False, indent=2))
    (ctx / "world.json").write_text(json.dumps(world,            ensure_ascii=False, indent=2))
    (ctx / "character.json").write_text(json.dumps(character,    ensure_ascii=False, indent=2))

    # ── plan/ ─────────────────────────────────────────────────
    plan_dir = base / "plan"
    plan_dir.mkdir(exist_ok=True)
    (plan_dir / "brief.json").write_text(json.dumps({}, ensure_ascii=False))
    (plan_dir / "chat_history.json").write_text(json.dumps([], ensure_ascii=False))

    # ── shots/ ────────────────────────────────────────────────
    (base / "shots").mkdir(exist_ok=True)

    # ── meta.json ─────────────────────────────────────────────
    meta = {
        "project_id": project_id,
        "character":  character.get("character", ""),
        "series":     world.get("series", ""),
        "created_at": datetime.utcnow().isoformat() + "Z",
        "owner_id":   owner_id,
    }
    (base / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))

    return meta


def get_project(project_id: str) -> dict:
    """
    Load a project from disk and return a merged payload for the frontend.

    Returns:
      {
        project_id, character, series, created_at,
        world, character_data, visual_spec,
        refs, extra_refs,
        plan:  { brief: dict, chat_history: list },
        shots: [ { shot_id, title, mood, description, status, created_at } ]
      }
    Raises FileNotFoundError if the project doesn't exist.
    """
    base = STORAGE_ROOT / project_id
    if not base.exists():
        raise FileNotFoundError(f"Project {project_id!r} not found")

    ctx = base / "context"

    meta           = json.loads((base / "meta.json").read_text())
    world          = json.loads((ctx / "world.json").read_text())
    character_data = json.loads((ctx / "character.json").read_text())

    vs_json = ctx / "visual_spec.json"
    vs_txt  = ctx / "visual_spec.txt"
    if vs_json.exists():
        visual_spec = json.loads(vs_json.read_text())
    else:
        text = vs_txt.read_text() if vs_txt.exists() else ""
        visual_spec = {"zh": text, "en": text, "ja": text}

    refs = sorted(
        f"/projects/{project_id}/refs/{f.name}"
        for f in (ctx / "refs").iterdir()
        if f.is_file()
    )

    extra_refs_dir = ctx / "extra_refs"
    extra_refs = sorted(
        f"/projects/{project_id}/extra-refs/{f.name}"
        for f in extra_refs_dir.iterdir()
        if f.is_file()
    ) if extra_refs_dir.exists() else []

    # ── plan/ (graceful fallback for projects created before this version) ──
    plan_dir = base / "plan"
    brief         = json.loads((plan_dir / "brief.json").read_text())        if (plan_dir / "brief.json").exists()        else {}
    chat_history  = json.loads((plan_dir / "chat_history.json").read_text()) if (plan_dir / "chat_history.json").exists() else []

    # ── shots/ ────────────────────────────────────────────────────────────────
    shots_dir = base / "shots"
    shots = []
    if shots_dir.exists():
        for shot_dir in sorted(shots_dir.iterdir()):
            shot_file = shot_dir / "shot.json"
            if shot_dir.is_dir() and shot_file.exists():
                shots.append(json.loads(shot_file.read_text()))

    return {
        **meta,
        "world":          world,
        "character_data": character_data,
        "visual_spec":    visual_spec,
        "refs":           refs,
        "extra_refs":     extra_refs,
        "plan": {
            "brief":        brief,
            "chat_history": chat_history,
        },
        "shots": shots,
    }


# ── Shots ──────────────────────────────────────────────────────────────────────

def get_shot_history(project_id: str, shot_id: str) -> list[dict]:
    """Load chat history for a shot (empty list if none yet)."""
    path = STORAGE_ROOT / project_id / "shots" / shot_id / "chat_history.json"
    return json.loads(path.read_text()) if path.exists() else []


def append_shot_messages(project_id: str, shot_id: str, messages: list[dict]) -> None:
    """Append one or more chat messages to a shot's history."""
    path = STORAGE_ROOT / project_id / "shots" / shot_id / "chat_history.json"
    history = json.loads(path.read_text()) if path.exists() else []
    history.extend(messages)
    path.write_text(json.dumps(history, ensure_ascii=False, indent=2))


def create_shot(project_id: str, title: str, mood: str, description: str = "") -> dict:
    """
    Create a new shot under shots/{shot_id}/ and return its data.
    """
    base = STORAGE_ROOT / project_id
    if not base.exists():
        raise FileNotFoundError(f"Project {project_id!r} not found")

    shot_id  = str(uuid.uuid4())
    shot_dir = base / "shots" / shot_id
    shot_dir.mkdir(parents=True, exist_ok=True)
    (shot_dir / "guides").mkdir(exist_ok=True)

    shot = {
        "shot_id":     shot_id,
        "project_id":  project_id,
        "title":       title,
        "mood":        mood,
        "description": description,
        "status":      "pending",
        "created_at":  datetime.utcnow().isoformat() + "Z",
    }
    (shot_dir / "shot.json").write_text(json.dumps(shot, ensure_ascii=False, indent=2))

    # Seed chat history with welcome message
    (shot_dir / "chat_history.json").write_text(json.dumps([
        {"role": "agent", "text": f"为「{title}」规划中。描述想要的效果，我来生成参考例图。"},
    ], ensure_ascii=False, indent=2))

    return shot


def rename_shot(project_id: str, shot_id: str, title: str) -> None:
    """Update the title of an existing shot."""
    shot_file = STORAGE_ROOT / project_id / "shots" / shot_id / "shot.json"
    if not shot_file.exists():
        raise FileNotFoundError(f"Shot {shot_id!r} not found")
    shot = json.loads(shot_file.read_text())
    shot["title"] = title
    shot_file.write_text(json.dumps(shot, ensure_ascii=False, indent=2))


def delete_shot(project_id: str, shot_id: str) -> None:
    """Remove a shot directory entirely."""
    import shutil
    shot_dir = STORAGE_ROOT / project_id / "shots" / shot_id
    if not shot_dir.exists():
        raise FileNotFoundError(f"Shot {shot_id!r} not found")
    shutil.rmtree(shot_dir)


def update_shot_status(
    project_id: str,
    shot_id: str,
    status: str,
    image_url: str | None = None,
    error_type: str | None = None,
) -> None:
    """Update shot.json status (and optionally image_url or error_type)."""
    shot_file = STORAGE_ROOT / project_id / "shots" / shot_id / "shot.json"
    if not shot_file.exists():
        raise FileNotFoundError(f"Shot {shot_id!r} not found")
    shot = json.loads(shot_file.read_text())
    shot["status"] = status
    if image_url is not None:
        shot["image_url"] = image_url
    if error_type is not None:
        shot["error_type"] = error_type
    elif status != "error":
        shot.pop("error_type", None)
    shot_file.write_text(json.dumps(shot, ensure_ascii=False, indent=2))


def get_shot(project_id: str, shot_id: str) -> dict:
    """Load a shot with its chat history."""
    shot_file = STORAGE_ROOT / project_id / "shots" / shot_id / "shot.json"
    if not shot_file.exists():
        raise FileNotFoundError(f"Shot {shot_id!r} not found")
    shot = json.loads(shot_file.read_text())
    shot["chat_history"] = get_shot_history(project_id, shot_id)
    return shot


# ── Version tree ───────────────────────────────────────────────────────────────

def _clear_guide_cache(shot_dir: Path) -> None:
    for f in (shot_dir / "guides").glob("*.json"):
        f.unlink(missing_ok=True)


def list_versions(project_id: str, shot_id: str) -> list[dict]:
    """Return all version nodes with image_url filled in."""
    shot_file = STORAGE_ROOT / project_id / "shots" / shot_id / "shot.json"
    if not shot_file.exists():
        raise FileNotFoundError(f"Shot {shot_id!r} not found")
    shot = json.loads(shot_file.read_text())
    versions = shot.get("versions", [])
    result = []
    for v in versions:
        entry = dict(v)
        img = STORAGE_ROOT / project_id / "shots" / shot_id / "versions" / f"{v['id']}.png"
        entry["image_url"] = (
            f"/projects/{project_id}/shots/{shot_id}/versions/{v['id']}"
            if img.exists() else None
        )
        result.append(entry)
    return result


def add_version(
    project_id: str,
    shot_id: str,
    version_id: str,
    parent_ids: list[str],
    prompt: str,
    image_bytes: bytes,
) -> dict:
    """Persist a new version image and update shot.json. Auto-activates the new version."""
    shot_dir = STORAGE_ROOT / project_id / "shots" / shot_id
    if not shot_dir.exists():
        raise FileNotFoundError(f"Shot {shot_id!r} not found")

    versions_dir = shot_dir / "versions"
    versions_dir.mkdir(exist_ok=True)
    (versions_dir / f"{version_id}.png").write_bytes(image_bytes)

    shot_file = shot_dir / "shot.json"
    shot = json.loads(shot_file.read_text())
    entry = {
        "id":         version_id,
        "parent_ids": parent_ids,
        "prompt":     prompt,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    shot.setdefault("versions", []).append(entry)
    shot["active_version_id"] = version_id
    shot_file.write_text(json.dumps(shot, ensure_ascii=False, indent=2))

    # Keep generated.png in sync so guide generation stays backward-compatible
    (shot_dir / "generated.png").write_bytes(image_bytes)
    _clear_guide_cache(shot_dir)

    return entry


def delete_version(project_id: str, shot_id: str, version_id: str) -> None:
    """Delete a version node. If it was active, auto-activate the most recent remaining version."""
    import shutil
    shot_dir = STORAGE_ROOT / project_id / "shots" / shot_id
    shot_file = shot_dir / "shot.json"
    if not shot_file.exists():
        raise FileNotFoundError(f"Shot {shot_id!r} not found")

    shot = json.loads(shot_file.read_text())
    was_active = shot.get("active_version_id") == version_id
    shot["versions"] = [v for v in shot.get("versions", []) if v["id"] != version_id]

    if was_active:
        remaining = shot["versions"]
        if remaining:
            new_active = remaining[-1]["id"]
            shot["active_version_id"] = new_active
            src = shot_dir / "versions" / f"{new_active}.png"
            if src.exists():
                shutil.copy2(src, shot_dir / "generated.png")
        else:
            shot["active_version_id"] = None
            gen = shot_dir / "generated.png"
            if gen.exists():
                gen.unlink()
        _clear_guide_cache(shot_dir)

    shot_file.write_text(json.dumps(shot, ensure_ascii=False, indent=2))
    (shot_dir / "versions" / f"{version_id}.png").unlink(missing_ok=True)


def activate_version(project_id: str, shot_id: str, version_id: str) -> None:
    """Set a version as active: copy its image to generated.png and clear guide cache."""
    shot_dir = STORAGE_ROOT / project_id / "shots" / shot_id
    shot_file = shot_dir / "shot.json"
    if not shot_file.exists():
        raise FileNotFoundError(f"Shot {shot_id!r} not found")

    shot = json.loads(shot_file.read_text())
    if not any(v["id"] == version_id for v in shot.get("versions", [])):
        raise FileNotFoundError(f"Version {version_id!r} not found")

    shot["active_version_id"] = version_id
    shot_file.write_text(json.dumps(shot, ensure_ascii=False, indent=2))

    src = shot_dir / "versions" / f"{version_id}.png"
    if src.exists():
        (shot_dir / "generated.png").write_bytes(src.read_bytes())
    _clear_guide_cache(shot_dir)


# ── Plan ───────────────────────────────────────────────────────────────────────

def save_chat_history(project_id: str, history: list[dict]) -> None:
    """Persist the full AI planning chat history to plan/chat_history.json."""
    plan_dir = STORAGE_ROOT / project_id / "plan"
    plan_dir.mkdir(exist_ok=True)
    (plan_dir / "chat_history.json").write_text(json.dumps(history, ensure_ascii=False, indent=2))


def save_brief(project_id: str, brief: dict) -> None:
    """Persist the structured shooting brief to plan/brief.json."""
    plan_dir = STORAGE_ROOT / project_id / "plan"
    plan_dir.mkdir(exist_ok=True)
    (plan_dir / "brief.json").write_text(json.dumps(brief, ensure_ascii=False, indent=2))


# ── Reference images ───────────────────────────────────────────────────────────

def add_extra_ref(project_id: str, image_bytes: bytes, image_name: str) -> str:
    """
    Save a supplementary reference image to context/extra_refs/.
    Returns the URL path the frontend can use to fetch it.
    """
    extra_dir = STORAGE_ROOT / project_id / "context" / "extra_refs"
    extra_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(image_name).suffix or ".jpg"
    existing = sorted(extra_dir.iterdir()) if extra_dir.exists() else []
    next_num = len(existing) + 1
    filename = f"{next_num:03d}{ext}"
    (extra_dir / filename).write_bytes(image_bytes)

    return f"/projects/{project_id}/extra-refs/{filename}"


def get_extra_ref_path(project_id: str, filename: str) -> Path:
    """Return the absolute path to a supplementary reference image."""
    extra_dir = STORAGE_ROOT / project_id / "context" / "extra_refs"
    path = (extra_dir / filename).resolve()
    if not path.is_relative_to(extra_dir.resolve()):
        raise FileNotFoundError("Invalid path")
    if not path.exists():
        raise FileNotFoundError(f"Extra ref {filename!r} not found in project {project_id!r}")
    return path


def get_ref_path(project_id: str, filename: str) -> Path:
    """
    Return the absolute path to an original reference image.
    Path traversal is prevented by resolving against the refs directory.
    """
    refs_dir = STORAGE_ROOT / project_id / "context" / "refs"
    path = (refs_dir / filename).resolve()
    if not path.is_relative_to(refs_dir.resolve()):
        raise FileNotFoundError("Invalid path")
    if not path.exists():
        raise FileNotFoundError(f"Ref {filename!r} not found in project {project_id!r}")
    return path


# ── Shot reference nodes (r-nodes) ─────────────────────────────────────────────
# Separate from version nodes: user-uploaded images for pose/background/weapon/
# costume/lighting/expression reference. Processed into character-neutral assets
# before being fed to image generation.

def add_shot_ref(project_id: str, shot_id: str, image_bytes: bytes) -> dict:
    """Upload a new r-node for a shot. Type must be set separately via set_shot_ref_type."""
    shot_dir = STORAGE_ROOT / project_id / "shots" / shot_id
    if not shot_dir.exists():
        raise FileNotFoundError(f"Shot {shot_id!r} not found")

    ref_id = uuid.uuid4().hex[:8]
    refs_dir = shot_dir / "refs"
    refs_dir.mkdir(exist_ok=True)
    (refs_dir / f"{ref_id}.png").write_bytes(image_bytes)

    entry = {
        "id":         ref_id,
        "type":       None,          # set by agent after asking user
        "status":     "pending_type",
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    shot_file = shot_dir / "shot.json"
    shot = json.loads(shot_file.read_text())
    shot.setdefault("shot_refs", []).append(entry)
    shot_file.write_text(json.dumps(shot, ensure_ascii=False, indent=2))
    return entry


def list_shot_refs(project_id: str, shot_id: str) -> list[dict]:
    """Return all r-nodes for a shot with image URLs."""
    shot_file = STORAGE_ROOT / project_id / "shots" / shot_id / "shot.json"
    if not shot_file.exists():
        raise FileNotFoundError(f"Shot {shot_id!r} not found")
    shot = json.loads(shot_file.read_text())
    result = []
    for r in shot.get("shot_refs", []):
        entry = dict(r)
        entry["original_url"] = f"/projects/{project_id}/shots/{shot_id}/refs/{r['id']}/original"
        proc_img = STORAGE_ROOT / project_id / "shots" / shot_id / "refs" / f"{r['id']}_proc.png"
        proc_txt = STORAGE_ROOT / project_id / "shots" / shot_id / "refs" / f"{r['id']}_proc.txt"
        if proc_img.exists():
            entry["processed_url"] = f"/projects/{project_id}/shots/{shot_id}/refs/{r['id']}/processed"
        elif proc_txt.exists():
            entry["processed_text"] = proc_txt.read_text()
        else:
            entry["processed_url"] = None
        result.append(entry)
    return result


def set_shot_ref_type(project_id: str, shot_id: str, ref_id: str, ref_type: str) -> dict:
    """
    Set the type for an r-node and trigger background processing.
    Processing is synchronous here; caller should run this in a BackgroundTask.
    """
    from tools.ref_extractor import process as _process, IMAGE_TYPES

    shot_dir = STORAGE_ROOT / project_id / "shots" / shot_id
    shot_file = shot_dir / "shot.json"
    if not shot_file.exists():
        raise FileNotFoundError(f"Shot {shot_id!r} not found")

    shot = json.loads(shot_file.read_text())
    ref_entry = next((r for r in shot.get("shot_refs", []) if r["id"] == ref_id), None)
    if ref_entry is None:
        raise FileNotFoundError(f"Ref {ref_id!r} not found")

    # Mark as processing
    ref_entry["type"]   = ref_type
    ref_entry["status"] = "processing"
    shot_file.write_text(json.dumps(shot, ensure_ascii=False, indent=2))

    # Process
    refs_dir = shot_dir / "refs"
    original = (refs_dir / f"{ref_id}.png").read_bytes()
    try:
        result = _process(original, ref_type)
        if ref_type in IMAGE_TYPES:
            (refs_dir / f"{ref_id}_proc.png").write_bytes(result)
        else:
            (refs_dir / f"{ref_id}_proc.txt").write_text(result)
        ref_entry["status"] = "ready"
    except Exception as e:
        ref_entry["status"] = "error"
        ref_entry["error"]  = str(e)

    shot = json.loads(shot_file.read_text())  # re-read (avoid race on versions)
    for i, r in enumerate(shot.get("shot_refs", [])):
        if r["id"] == ref_id:
            shot["shot_refs"][i] = ref_entry
            break
    shot_file.write_text(json.dumps(shot, ensure_ascii=False, indent=2))
    return ref_entry


def get_shot_ref_file(project_id: str, shot_id: str, ref_id: str, which: str) -> Path:
    """Return path to original or processed ref image. which='original'|'processed'"""
    refs_dir = STORAGE_ROOT / project_id / "shots" / shot_id / "refs"
    if which == "original":
        p = refs_dir / f"{ref_id}.png"
    else:
        p = refs_dir / f"{ref_id}_proc.png"
    if not p.exists():
        raise FileNotFoundError(f"Ref {ref_id!r} {which} not found")
    return p


def get_shot_ref_processed_bytes(project_id: str, shot_id: str, ref_id: str) -> "bytes | None":
    """Return processed bytes for image-type refs, or None if text/not ready."""
    p = STORAGE_ROOT / project_id / "shots" / shot_id / "refs" / f"{ref_id}_proc.png"
    return p.read_bytes() if p.exists() else None


def delete_shot_ref(project_id: str, shot_id: str, ref_id: str) -> None:
    shot_dir = STORAGE_ROOT / project_id / "shots" / shot_id
    shot_file = shot_dir / "shot.json"
    if not shot_file.exists():
        raise FileNotFoundError(f"Shot {shot_id!r} not found")
    shot = json.loads(shot_file.read_text())
    shot["shot_refs"] = [r for r in shot.get("shot_refs", []) if r["id"] != ref_id]
    shot_file.write_text(json.dumps(shot, ensure_ascii=False, indent=2))
    refs_dir = shot_dir / "refs"
    for suffix in [".png", "_proc.png", "_proc.txt"]:
        (refs_dir / f"{ref_id}{suffix}").unlink(missing_ok=True)
