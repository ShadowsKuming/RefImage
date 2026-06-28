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
from agents.character_extractor import FIELDS, extract_features, verify_same_character
from agents.character_chat import chat as _character_chat
from tools.translate import translate_visual_spec

# In-memory session store: { session_id: { history, extracted, gender, done, visual_spec } }
_sessions: dict[str, dict] = {}

_EMPTY_EXTRACTED = {f: None for f in FIELDS}  # English only during accumulation

_NULL_STRINGS = {"null", "none", "unknown", "n/a", "not visible", "cannot determine", "undetermined"}

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
}


def _is_null(v) -> bool:
    if v is None:
        return True
    if isinstance(v, str) and v.strip().lower() in _NULL_STRINGS:
        return True
    return False


def _missing(extracted: dict) -> list[str]:
    """Return field names that still have no English value."""
    return [f for f, v in extracted.items() if _is_null(v)]


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

def profile_chat(
    message: str,
    history: list[dict],
    visual_spec: str | None = None,
    current_profile: dict | None = None,
) -> dict:
    """
    Multi-turn agent chat for Step 2 profile building.
    Returns: { reply: str, profile: dict | None }
      - reply is always present (the agent's conversational response)
      - profile is non-null only when the agent updated the profile this turn
    """
    return _character_chat(message, history, visual_spec, current_profile)


# ── Step 1: image analysis ────────────────────────────────────────────────────

def verify_character(image_bytes: bytes, session_id: str) -> dict:
    """
    Check whether a new image shows the same character as an existing session.
    Returns: { same: bool, reason: str }
    """
    session = _sessions.get(session_id)
    if not session or not any(v for v in session["extracted"].values() if v):
        return {"same": True, "reason": ""}
    result = verify_same_character(image_bytes, session["extracted"])
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
      { session_id, done, gender, message, visual_spec, extracted, missing_fields }
      done=True means all fields are filled and visual_spec is ready.
    """
    if session_id is None or session_id not in _sessions:
        session_id = str(uuid.uuid4())
        _sessions[session_id] = {
            "history":     [],
            "extracted":   dict(_EMPTY_EXTRACTED),  # flat English fields
            "gender":      "female",
            "done":        False,
            "visual_spec": None,
        }

    session = _sessions[session_id]

    if session["done"]:
        return {
            "session_id":    session_id,
            "done":          True,
            "message":       "角色信息已完整。",
            "visual_spec":   session["visual_spec"],
            "extracted":     session["extracted"],
            "missing_fields": [],
        }

    missing = _missing(session["extracted"])
    result  = extract_features(image_bytes, session["history"], missing)

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
        # Translate English fields to zh + ja, then compile labelled text per language
        multilang_fields      = translate_visual_spec(session["extracted"])
        session["visual_spec"] = _compile_visual_spec(multilang_fields)

    print(f"[analyze] session={session_id} done={done} missing={missing_after}")

    return {
        "session_id":    session_id,
        "done":          done,
        "gender":        session["gender"],
        "message":       result["message"],
        "visual_spec":   session["visual_spec"],
        "extracted":     session["extracted"],
        "missing_fields": missing_after,
    }
