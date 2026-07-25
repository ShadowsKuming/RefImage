"""
Unit tests for chat()'s awaiting_confirm gate and profile extraction.

`awaiting_confirm` tells the frontend whether to show the "对，没错" quick-confirm
chip. It must be true ONLY on the very first turn AND when the vision hint is a
single confident guess — otherwise (multiple/none candidates, later turns, or
once a profile has actually been built) the chip makes no sense and only the
free-text input applies.

The agent LLM (call_agent) is mocked; these tests pin the branching/extraction
logic, not model behavior.
"""
import pytest
from agents import character_chat
from services import analyze_service


def _seed_session(sid: str, confidence: str):
    # A dict char_hint short-circuits the real vision identification in chat().
    analyze_service._sessions[sid] = {
        "char_hint": {"confidence": confidence, "text": "秋山澪，轻音少女"},
        "first_image": b"fake",
    }


def _fake_agent(text="", tool_calls=None):
    return lambda *a, **k: {"text": text, "tool_calls": tool_calls or []}


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    analyze_service._sessions.clear()


def test_single_confidence_first_turn_awaits_confirm(monkeypatch):
    monkeypatch.setattr(character_chat, "call_agent", _fake_agent(text="是秋山澪，对吗？"))
    _seed_session("s1", "single")
    out = character_chat.chat("（kickoff）", [], None, None, "s1", "zh")
    assert out["awaiting_confirm"] is True
    assert out["profile"] is None
    assert out["reply"] == "是秋山澪，对吗？"


def test_none_confidence_does_not_await_confirm(monkeypatch):
    monkeypatch.setattr(character_chat, "call_agent", _fake_agent(text="没认出来，告诉我角色名？"))
    _seed_session("s2", "none")
    out = character_chat.chat("（kickoff）", [], None, None, "s2", "zh")
    assert out["awaiting_confirm"] is False


def test_multiple_confidence_does_not_await_confirm(monkeypatch):
    monkeypatch.setattr(character_chat, "call_agent", _fake_agent(text="是 A 还是 B？"))
    _seed_session("s3", "multiple")
    out = character_chat.chat("（kickoff）", [], None, None, "s3", "zh")
    assert out["awaiting_confirm"] is False


def test_later_turn_does_not_await_confirm_even_if_single(monkeypatch):
    # History is non-empty → not the identification turn → no confirm chip.
    monkeypatch.setattr(character_chat, "call_agent", _fake_agent(text="好的"))
    _seed_session("s4", "single")
    history = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hey"},
    ]
    out = character_chat.chat("是的", history, None, None, "s4", "zh")
    assert out["awaiting_confirm"] is False


def test_profile_built_forces_awaiting_confirm_false(monkeypatch):
    # Even on a single-confidence first turn, if the agent already built a
    # profile there's nothing left to confirm.
    tool_calls = [{"name": "update_profile", "input": {"character": "秋山澪", "series": "轻音少女"}}]
    monkeypatch.setattr(character_chat, "call_agent", _fake_agent(text="档案整理好了", tool_calls=tool_calls))
    _seed_session("s5", "single")
    out = character_chat.chat("（kickoff）", [], None, None, "s5", "zh")
    assert out["awaiting_confirm"] is False
    assert out["profile"] == {"character": "秋山澪", "series": "轻音少女"}


def test_profile_extraction_takes_first_update_profile_ignoring_web_search(monkeypatch):
    tool_calls = [
        {"name": "web_search", "input": {"query": "秋山澪"}},
        {"name": "update_profile", "input": {"character": "秋山澪"}},
        {"name": "update_profile", "input": {"character": "SHOULD-NOT-WIN"}},
    ]
    monkeypatch.setattr(character_chat, "call_agent", _fake_agent(text="好了", tool_calls=tool_calls))
    _seed_session("s6", "none")
    out = character_chat.chat("秋山澪", [], None, None, "s6", "zh")
    assert out["profile"] == {"character": "秋山澪"}


def test_no_session_id_never_awaits_confirm(monkeypatch):
    # No session → no vision hint → the confirm chip can't apply.
    monkeypatch.setattr(character_chat, "call_agent", _fake_agent(text="哪位角色？"))
    out = character_chat.chat("hi", [], None, None, None, "zh")
    assert out["awaiting_confirm"] is False
