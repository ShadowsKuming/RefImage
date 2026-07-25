"""
Unit tests for _identify_from_image's response parsing.

The vision LLM is prompted to return {"confidence", "text"} JSON, and the
frontend uses `confidence` to decide whether to show a yes/no confirm chip
(only for a single-candidate guess). The parsing must survive the model not
following the format perfectly — fenced code blocks, extra prose, malformed
JSON, or a bogus confidence value — and always fall back to a safe
confidence="none" (ask-the-user) rather than crashing or lying.

The vision call itself is mocked; these tests pin the parsing/fallback logic,
not model behavior.
"""
import pytest
from agents import character_chat


@pytest.fixture(autouse=True)
def _stub_encode(monkeypatch):
    # _identify_from_image encodes the image before calling the LLM; stub it so
    # tests can pass dummy bytes.
    monkeypatch.setattr(character_chat.vision, "encode_image",
                        lambda b: ("ZmFrZQ==", "image/png"))


def _run(monkeypatch, raw: str) -> dict:
    monkeypatch.setattr(character_chat.vision, "call", lambda *a, **k: raw)
    return character_chat._identify_from_image(b"fake-bytes")


def test_clean_json_single(monkeypatch):
    out = _run(monkeypatch, '{"confidence": "single", "text": "秋山澪，轻音少女"}')
    assert out == {"confidence": "single", "text": "秋山澪，轻音少女"}


def test_multiple_and_none_confidence_pass_through(monkeypatch):
    assert _run(monkeypatch, '{"confidence": "multiple", "text": "A 或 B"}')["confidence"] == "multiple"
    assert _run(monkeypatch, '{"confidence": "none", "text": "黑长直"}')["confidence"] == "none"


def test_json_wrapped_in_markdown_fence_is_still_parsed(monkeypatch):
    # Model ignored "don't wrap in code block" — the {...} extraction still works.
    raw = '```json\n{"confidence": "single", "text": "凉宫春日"}\n```'
    assert _run(monkeypatch, raw) == {"confidence": "single", "text": "凉宫春日"}


def test_json_with_surrounding_prose_is_still_parsed(monkeypatch):
    raw = '好的，结果是：{"confidence": "single", "text": "初音未来"} 希望有帮助'
    assert _run(monkeypatch, raw)["text"] == "初音未来"


def test_malformed_json_falls_back_to_none_and_raw_text(monkeypatch):
    raw = '{"confidence": "single", "text": '  # truncated / invalid
    out = _run(monkeypatch, raw)
    assert out["confidence"] == "none"
    assert out["text"] == raw


def test_plain_text_with_no_json_falls_back_to_none(monkeypatch):
    raw = "这看起来像是黑长直发、穿校服的角色，但我无法确定是谁。"
    out = _run(monkeypatch, raw)
    assert out["confidence"] == "none"
    assert out["text"] == raw


def test_bogus_confidence_value_is_rejected_but_text_kept(monkeypatch):
    # An out-of-enum confidence must not leak through — default to "none" so the
    # frontend doesn't show a confirm chip it can't back up. Text is still used.
    out = _run(monkeypatch, '{"confidence": "maybe", "text": "候选：A、B"}')
    assert out["confidence"] == "none"
    assert out["text"] == "候选：A、B"


def test_missing_text_field_falls_back_to_raw(monkeypatch):
    raw = '{"confidence": "single"}'
    out = _run(monkeypatch, raw)
    assert out["confidence"] == "single"
    assert out["text"] == raw
