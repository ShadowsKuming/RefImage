"""
Regression tests for vision-model refusal / non-JSON handling.

Prod incident (user04, 2026-07-28): uploading certain images made the vision
LLM return a plain-text refusal ("I'm sorry, I can't help with that." /
"抱歉，我无法识别图片中的人物…") instead of JSON. `_parse` raised, the analyze /
verify endpoints 500'd, and the user saw a generic error. These pin the graceful
degradation: refusal → VisionParseError → friendly message (analyze) / fail-open
(verify), never a crash. The vision layer is mocked — no real API.
"""
import pytest
from agents import character_extractor
from agents.character_extractor import VisionParseError, _parse
from services import analyze_service

REFUSALS = [
    "I'm sorry, I can’t help with that.",
    "抱歉，我无法识别图片中的人物。请上传动漫角色的图片。",
    "Sorry, but I can't assist with this request.",
]


# ── _parse ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text", REFUSALS)
def test_parse_raises_visionparseerror_on_refusal(text):
    with pytest.raises(VisionParseError) as ei:
        _parse(text)
    assert ei.value.raw == text            # carries the raw text for logging


def test_parse_raises_on_embedded_but_truncated_json():
    # a giant response cut mid-object (the "line 8500" JSONDecodeError case)
    with pytest.raises(VisionParseError):
        _parse('prefix {"same": true, "reason": "clipped' + '…' * 10)


def test_parse_ok_on_valid_and_embedded_json():
    assert _parse('{"a": 1}') == {"a": 1}
    assert _parse('here you go: {"same": true} done') == {"same": True}


# ── verify_same_character: fail open ──────────────────────────────────────────

def test_verify_fails_open_on_refusal(monkeypatch):
    monkeypatch.setattr(character_extractor.vision, "encode_image", lambda b: ("x", "image/png"))
    monkeypatch.setattr(character_extractor.vision, "call", lambda *a, **k: REFUSALS[0])
    out = character_extractor.verify_same_character(b"img", {"hairstyle": "black long"})
    assert out == {"same": True, "reason": ""}   # never blocks the user


# ── start_or_continue: graceful "unrecognized" instead of 500 ─────────────────

@pytest.fixture(autouse=True)
def _clear_sessions():
    yield
    analyze_service._sessions.clear()


def test_analyze_refusal_returns_friendly_not_500(monkeypatch):
    monkeypatch.setattr(character_extractor.vision, "encode_image", lambda b: ("x", "image/png"))
    monkeypatch.setattr(character_extractor.vision, "call", lambda *a, **k: REFUSALS[1])
    out = analyze_service.start_or_continue(b"img", None)   # first image, brand-new session
    assert out["done"] is False
    assert out["unrecognized"] is True
    assert out["message"] and "识别" in out["message"]
    assert out["visual_spec"] is None
    assert out["missing_fields"]                            # nothing got filled
    # session survives so the user can immediately retry with another image
    assert out["session_id"] in analyze_service._sessions


def test_analyze_success_path_unaffected(monkeypatch):
    good = '{"updates": {"hairstyle": "black long straight"}, "gender": "female", "message": "ok"}'
    monkeypatch.setattr(character_extractor.vision, "encode_image", lambda b: ("x", "image/png"))
    monkeypatch.setattr(character_extractor.vision, "call", lambda *a, **k: good)
    out = analyze_service.start_or_continue(b"img", None)
    assert out.get("unrecognized") is None
    assert out["extracted"]["hairstyle"] == "black long straight"
