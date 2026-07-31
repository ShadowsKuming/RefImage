"""
Unit tests for the handbook-finalize gather flow in agents/planning_flow.

No real LLM or disk: the say/menu/parse helpers and the storage services are
monkeypatched, so these pin only the deterministic state-machine logic —
  · __handbook → readiness gate ONLY when something's still undetermined
  · __gather   → walks exactly the pending slots (date/crew), skipping filled ones
  · the gather queue ends at plan_wrap (not the normal plan_wig next)
"""
import pytest
from agents import planning_flow as pf


@pytest.fixture
def env(monkeypatch):
    state = {}
    plan_data = {"shoot_date": "", "shoot_time": "", "crew": {}}
    recorded = []

    project = {
        "character_data": {"character": "后藤独"},
        "visual_spec": {"zh": "女性角色", "en": ""},
        "shots": [{"shot_id": "s1", "title": "卧室发呆", "completed": True}],
        "plan": {"chat_history": [], "data": plan_data},
    }

    monkeypatch.setattr(pf.project_service, "get_project", lambda pid: project)
    monkeypatch.setattr(pf.project_service, "save_chat_history", lambda pid, h: None)
    monkeypatch.setattr(pf.agent_state_service, "load_state", lambda pid: state.get(pid, {}))
    monkeypatch.setattr(pf.agent_state_service, "save_state",
                        lambda pid, st: state.__setitem__(pid, st))

    def _upd(pid, theme=None, shoot_date=None, crew=None, shoot_time=None):
        if shoot_date is not None:
            plan_data["shoot_date"] = shoot_date
        if shoot_time is not None:
            plan_data["shoot_time"] = shoot_time
        if crew is not None:
            plan_data["crew"] = crew
        recorded.append(("overview", shoot_date, crew, shoot_time))
    monkeypatch.setattr(pf.plan_service, "update_overview", _upd)
    monkeypatch.setattr(pf.plan_service, "add_note", lambda *a, **k: recorded.append(("note",)))
    monkeypatch.setattr(pf.plan_service, "load_plan_data", lambda pid: plan_data)

    # LLM helpers → deterministic stand-ins
    monkeypatch.setattr(pf, "_menu_reply", lambda *a, **k: "（萌妹说的话）")
    monkeypatch.setattr(pf, "_say", lambda *a, **k: ("（问一句）", ["选项"]))
    monkeypatch.setattr(pf, "_parse_value", lambda msg, intent: msg)

    return project, plan_data, state, recorded


def test_handbook_gate_when_pending(env):
    project, plan_data, state, recorded = env
    res = pf.run_step("p1", "__handbook")
    assert res["state"] == "finalize"
    actions = [o["action"] for o in res["options"]]
    assert actions == ["finalize_go", "finalize_later"]
    assert res["options"][0]["value"] == "__gather"
    assert res["options"][1]["value"] == "__resume"


def test_handbook_no_nag_when_ready(env):
    project, plan_data, state, recorded = env
    plan_data["shoot_date"] = "2026年8月"
    plan_data["crew"] = {"photographers": 1}
    res = pf.run_step("p1", "__handbook")
    assert res["reply"] == ""           # nothing to lock in → stay quiet
    assert res["state"] != "finalize"


def test_gather_sweeps_full_checklist_then_wraps(env):
    project, plan_data, state, recorded = env
    # enter the gate, then say "ready"
    pf.run_step("p1", "__handbook")
    r1 = pf.run_step("p1", "__gather")
    assert r1["state"] == "plan_date"          # first pending slot
    assert state["p1"]["gather"] is True
    assert state["p1"]["queue"] == ["plan_time", "plan_crew", "plan_wig", "plan_clothes"]

    r2 = pf.run_step("p1", "下个月")            # answer date
    assert plan_data["shoot_date"] == "下个月"
    assert r2["state"] == "plan_time"          # rough start time comes right after date

    r3 = pf.run_step("p1", "傍晚")             # answer time → stored separately for the schedule
    assert plan_data["shoot_time"] == "傍晚"
    assert plan_data["shoot_date"] == "下个月"
    assert r3["state"] == "plan_crew"

    r4 = pf.run_step("p1", "found")            # answer crew
    assert plan_data["crew"].get("photographers")
    assert r4["state"] == "plan_wig"           # wig & clothes always swept

    r5 = pf.run_step("p1", "ready")            # answer wig
    assert r5["state"] == "plan_clothes"

    r6 = pf.run_step("p1", "ready")            # answer clothes → wrap
    assert r6["state"] == "plan_wrap"
    assert state["p1"]["gather"] is False


def test_gather_skips_concrete_date_but_still_asks_time(env):
    project, plan_data, state, recorded = env
    plan_data["shoot_date"] = "2026年8月"       # concrete (has year) → date skipped
    pf.run_step("p1", "__handbook")
    r1 = pf.run_step("p1", "__gather")
    assert r1["state"] == "plan_time"          # date skipped, time still confirmed
    assert state["p1"]["queue"] == ["plan_crew", "plan_wig", "plan_clothes"]


def test_wrap_menu_offers_next_shot_not_first(env):
    project, plan_data, state, recorded = env
    # walk to the wrap
    pf.run_step("p1", "__handbook")
    pf.run_step("p1", "__gather")
    pf.run_step("p1", "下个月")     # date
    pf.run_step("p1", "傍晚")      # time
    pf.run_step("p1", "found")     # crew
    pf.run_step("p1", "ready")     # wig
    r = pf.run_step("p1", "ready") # clothes → plan_wrap
    assert r["state"] == "plan_wrap"
    actions = [o.get("action") for o in r["options"]]
    assert "new_shot" in actions and "go_shot" not in actions  # shots exist → "next", not "first"
