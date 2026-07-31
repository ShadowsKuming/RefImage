"""
Unit tests for chat()'s awaiting_confirm gate and profile extraction.

`awaiting_confirm` tells the frontend whether to show the "对，没错" quick-confirm
chip. It must be true whenever the vision hint is a single confident guess AND
the profile hasn't been built yet this session — that covers BOTH the first-turn
ask and a later re-ask after the user corrects the guess (the system prompt's own
"纠正后...再确认一次" flow). It must be false once a profile has actually been
built (in this turn or an earlier one), or when the vision hint was never a
single confident guess.

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


def test_later_turn_still_awaits_confirm_if_not_yet_resolved(monkeypatch):
    # A user correction loops back into ANOTHER yes/no re-confirm ask on a later
    # turn — history being non-empty must NOT suppress the chip on its own; only
    # an actually-built profile should. (Regression: this used to hardcode "later
    # turn = no chip", which broke the exact "纠正后再确认一次" flow the system
    # prompt asks the model to do.)
    monkeypatch.setattr(character_chat, "call_agent", _fake_agent(text="那应该是秋山澪没错吧？"))
    _seed_session("s4", "single")
    history = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "是秋山澪吗？"},
    ]
    out = character_chat.chat("不对，好像不是", history, None, None, "s4", "zh")
    assert out["awaiting_confirm"] is True


def test_awaiting_confirm_retired_after_profile_built(monkeypatch):
    # Once the profile has actually been built (in an earlier turn), later turns
    # never bring the confirm chip back even though the vision hint was single.
    tool_calls = [{"name": "update_profile", "input": {"character": "秋山澪"}}]
    monkeypatch.setattr(character_chat, "call_agent", _fake_agent(text="档案整理好了", tool_calls=tool_calls))
    _seed_session("s7", "single")
    character_chat.chat("（kickoff）", [], None, None, "s7", "zh")  # builds the profile

    monkeypatch.setattr(character_chat, "call_agent", _fake_agent(text="好的，帮你改一下"))
    history = [
        {"role": "user", "content": "（kickoff）"},
        {"role": "assistant", "content": "档案整理好了"},
    ]
    out = character_chat.chat("帮我把头发改成蓝色", history, None, None, "s7", "zh")
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
