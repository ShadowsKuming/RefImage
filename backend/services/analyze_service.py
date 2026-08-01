"""
services/analyze_service.py — Step 1 & 2 analysis logic

Owns all in-memory session state for the image analysis pipeline (Step 1) and
delegates character profile chat (Step 2) to tools/character_chat.py.

Step 1 — image analysis sessions:
  Each upload session is identified by a UUID.  Multiple images can be added to
  the same session; extracted fields accumulate across images until all eight
  visual fields are filled.  Session state lives in _sessions (in-memory only —
  restarting the server clears sessions, which is fine for the new-project flow).

Step 2 — profile chat:
  Stateless from the service's perspective; all state (history, current profile)
  is passed in per request from the frontend.
"""
import uuid
from agents.character_extractor import (
    FIELDS, extract_features, verify_same_character, is_null_value, VisionParseError,
)
from agents.character_chat import chat as _character_chat
from tools.translate import translate_visual_spec

# In-memory session store: { session_id: { history, extracted, gender, done, visual_spec } }
_sessions: dict[str, dict] = {}

_EMPTY_EXTRACTED = {f: None for f in FIELDS}  # English only during accumulation

# Human-readable labels per language, used when compiling the display text
_LABELS: dict[str, dict[str, str]] = {
    "zh": {
        "hairstyle": "发型", "face_makeup": "妆容", "upper_body": "上身",
        "lower_body": "下身", "shoes": "鞋履", "proportions": "体型",
        "distinctive": "特征", "color_palette": "配色",
    },
    "en": {
        "hairstyle": "Hairstyle", "face_makeup": "Face and makeup", "upper_body": "Upper body",
        "lower_body": "Lower body", "shoes": "Shoes", "proportions": "Body proportions",
        "distinctive": "Distinctive features", "color_palette": "Color palette",
    },
    "ja": {
        "hairstyle": "ヘアスタイル", "face_makeup": "顔・メイク", "upper_body": "上半身",
        "lower_body": "下半身", "shoes": "シューズ", "proportions": "体型",
        "distinctive": "特徴", "color_palette": "配色",
    },
    "pt": {
        "hairstyle": "Penteado", "face_makeup": "Rosto e maquiagem", "upper_body": "Parte superior",
        "lower_body": "Parte inferior", "shoes": "Sapatos", "proportions": "Proporções corporais",
        "distinctive": "Características distintivas", "color_palette": "Paleta de cores",
    },
}


def _is_null(v) -> bool:
    return is_null_value(v)


def _missing(extracted: dict) -> list[str]:
    """Return field names that still have no English value. All 8 fields are
    required — the user must supply images that show every field before the
    session is marked done."""
    return [f for f, v in extracted.items() if _is_null(v)]


def _progress_message(extracted: dict, missing: list[str]) -> str:
    """Build a deterministic Chinese status message from the actual extraction
    state — never trust the vision LLM's own free-form completeness claim,
    since it can say '已提取完整' while required fields are still null."""
    labels = _LABELS["zh"]
    if not missing:
        return "角色外貌信息已提取完整。"
    done_labels = [labels[f] for f, v in extracted.items() if not _is_null(v)]
    missing_labels = [labels[f] for f in missing]
    parts = []
    if done_labels:
        parts.append(f"已提取到：{'、'.join(done_labels)}。")
    parts.append(f"还缺少：{'、'.join(missing_labels)}，请上传能看清这些部位的参考图。")
    return "".join(parts)


def _build_visual_spec(extracted_en: dict) -> tuple[dict, dict]:
    """Translate extracted English fields (one LLM call, separate from
    extraction) and compile visual spec. Falls back to English-only if the
    translation LLM call fails.
    Returns (visual_spec_by_lang, multilang_fields) — multilang_fields is the
    full { zh: {field: val}, en: {...}, ja: {...}, pt: {...} } structure, persisted
    as-is to context/extracted.json so every saved project has all system languages
    per field, and used live for CharacterFigure tooltips during the wizard."""
    try:
        multilang = translate_visual_spec(extracted_en)
    except Exception:
        multilang = {"zh": dict(extracted_en), "en": dict(extracted_en), "ja": dict(extracted_en), "pt": dict(extracted_en)}
    return _compile_visual_spec(multilang), multilang


def _compile_visual_spec(multilang_fields: dict) -> dict:
    """
    Build per-language plain-text spec from a {zh, en, ja} fields dict.
    Each language gets its own labeled text block.
    """
    result = {}
    for lang, labels in _LABELS.items():
        fields = multilang_fields.get(lang, {})
        lines = [
            f"{labels[k]}: {fields[k]}"
            for k in FIELDS
            if not _is_null(fields.get(k))
        ]
        result[lang] = "\n".join(lines)
    return result


# ── Step 2: profile chat ──────────────────────────────────────────────────────

def get_session(session_id: str) -> dict | None:
    """Return the raw session dict, or None if it doesn't exist."""
    return _sessions.get(session_id)


def profile_chat(
    message: str,
    history: list[dict],
    visual_spec: str | None = None,
    current_profile: dict | None = None,
    session_id: str | None = None,
    reply_lang: str = "zh",
) -> dict:
    """
    Multi-turn agent chat for Step 2 profile building.
    Returns: { reply: str, profile: dict | None }
      - reply is always present (the agent's conversational response)
      - profile is non-null only when the agent updated the profile this turn
    """
    return _character_chat(message, history, visual_spec, current_profile, session_id, reply_lang)


# ── Step 1: image analysis ────────────────────────────────────────────────────

def verify_character(image_bytes: bytes, session_id: str, reply_lang: str = "zh") -> dict:
    """
    Check whether a new image shows the same character as an existing session.
    Returns: { same: bool, reason: str }
    """
    session = _sessions.get(session_id)
    if not session or not any(v for v in session["extracted"].values() if v):
        return {"same": True, "reason": ""}
    result = verify_same_character(image_bytes, session["extracted"], reply_lang)
    return {
        "same":   result.get("same", True),
        "reason": result.get("reason", ""),
    }


def start_or_continue(image_bytes: bytes, session_id: str | None) -> dict:
    """
    Analyze a character reference image, accumulating extracted fields across
    multiple images in the same session.

    Pass session_id=None to start a new session; pass the returned session_id
    on subsequent calls to continue the same session with additional images.

    Extraction merges incrementally: a field is only updated if it was previously
    null, so earlier images take precedence over later ones for each field.

    Returns:
      { session_id, done, gender, message, visual_spec, extracted, extracted_i18n, missing_fields }
      done=True means all fields are filled and visual_spec is ready.
      extracted_i18n ({zh, en, ja} per field) is null until done — translation
      runs once, as its own LLM call, right after extraction completes.
    """
    if session_id is None or session_id not in _sessions:
        session_id = str(uuid.uuid4())
        _sessions[session_id] = {
            "history":     [],
            "extracted":   dict(_EMPTY_EXTRACTED),  # flat English fields
            "gender":      "female",
            "done":        False,
            "visual_spec": None,
            "extracted_i18n": None,  # { zh, en, ja } per-field, filled once done
            "first_image": None,   # bytes of the first uploaded image
            "char_hint":   None,   # cached vision identification result
        }

    session = _sessions[session_id]

    # Keep the first uploaded image for Step 2 vision identification
    if session["first_image"] is None:
        session["first_image"] = image_bytes

    if session["done"]:
        # Retry translation if it failed on a previous call
        if session["visual_spec"] is None:
            session["visual_spec"], session["extracted_i18n"] = _build_visual_spec(session["extracted"])
        return {
            "session_id":    session_id,
            "done":          True,
            "gender":        session["gender"],
            "message":       "角色信息已完整。",
            "visual_spec":   session["visual_spec"],
            "extracted":     session["extracted"],
            "extracted_i18n": session["extracted_i18n"],
            "missing_fields": [],
        }

    missing = _missing(session["extracted"])
    try:
        result = extract_features(image_bytes, session["history"], missing)
    except VisionParseError:
        # Model refused / returned non-JSON (moderation, or not an anime character).
        # Don't 500 — tell the user plainly and let them upload a clearer image.
        return {
            "session_id":     session_id,
            "done":           False,
            "gender":         session["gender"],
            "message":        "没能从这张图识别出角色特征——可能图片不够清晰，或不是动漫角色。"
                              "换一张更清晰的动漫角色参考图再试试。",
            "visual_spec":    None,
            "extracted":      session["extracted"],
            "extracted_i18n": None,
            "missing_fields": missing,
            "unrecognized":   True,
        }

    # Merge: only fill previously-null English fields
    for field, value in result["updates"].items():
        if _is_null(session["extracted"].get(field)):
            session["extracted"][field] = None if _is_null(value) else value

    session["history"] = result["updated_history"]
    session["gender"]  = result.get("gender", session["gender"])

    missing_after = _missing(session["extracted"])
    done = len(missing_after) == 0

    if done:
        session["done"] = True
        session["visual_spec"], session["extracted_i18n"] = _build_visual_spec(session["extracted"])

    print(f"[analyze] session={session_id} done={done} missing={missing_after}")

    return {
        "session_id":    session_id,
        "done":          done,
        "gender":        session["gender"],
        "message":       _progress_message(session["extracted"], missing_after),
        "visual_spec":   session["visual_spec"],
        "extracted":     session["extracted"],
        "extracted_i18n": session["extracted_i18n"],
        "missing_fields": missing_after,
    }
