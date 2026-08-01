"""
Regression test for the `__resume` clobbering bug (found reviewing real EC2
chat history): the frontend fires `__resume` on every project-page mount. If
the last agent turn offered an un-clicked "propose_shot" invitation (a
`make_shot` chip), `__resume` must NOT overwrite it with a mid-stage
congratulations message — the user hasn't decided yet, and a same-instant
reload shouldn't erase their pending choice.
"""
import pytest
from agents import planning_flow as pf


@pytest.fixture
def env(monkeypatch):
    state = {}
    saved_history = []

    project = {
        "character_data": {"character": "后藤独"},
        "visual_spec": {"zh": "女性角色", "en": ""},
        "shots": [{"shot_id": "s1", "title": "卧室发呆", "completed": True}],
        "plan": {"chat_history": [], "data": {}},
    }

    monkeypatch.setattr(pf.project_service, "get_project", lambda pid: project)
    monkeypatch.setattr(pf.project_service, "save_chat_history",
                        lambda pid, h: saved_history.append(list(h)))
    monkeypatch.setattr(pf.agent_state_service, "load_state", lambda pid: state.get(pid, {}))
    monkeypatch.setattr(pf.agent_state_service, "save_state",
                        lambda pid, st: state.__setitem__(pid, st))
    monkeypatch.setattr(pf, "_menu_reply", lambda *a, **k: "（萌妹说的话）")

    return project, state, saved_history


def test_resume_does_not_clobber_pending_shot_invite(env):
    project, state, saved_history = env
    invite_msg = {
        "role": "agent", "text": "要不要试试这个？",
        "options": [{"label": "🎬 去构思「温柔社恐」", "value": "温柔社恐", "action": "make_shot"},
                    {"label": "再聊聊", "value": "再聊聊"}],
    }
    project["plan"]["chat_history"] = [invite_msg]
    state["p1"] = {"state": "open", "last_options": invite_msg["options"]}

    res = pf.run_step("p1", "__resume")

    assert res["reply"] == ""                      # no-op: nothing new said
    assert res["options"] == invite_msg["options"]  # invite preserved verbatim
    assert res["state"] == "open"
    assert saved_history == []                      # history untouched, no overwrite persisted


def test_resume_still_congratulates_when_no_pending_invite(env):
    project, state, saved_history = env
    project["plan"]["chat_history"] = [
        {"role": "agent", "text": "上次聊到这儿", "options": [{"label": "继续", "value": "继续"}]},
    ]
    state["p1"] = {"state": "open"}

    res = pf.run_step("p1", "__resume")

    assert res["reply"] != ""          # normal mid-stage check-in still fires
    assert res["state"] == "midstage"


def test_resume_ignores_invite_chip_if_user_already_clicked_past_it(env):
    project, state, saved_history = env
    # the invite was clicked → a newer agent turn (no make_shot chip) is now last
    project["plan"]["chat_history"] = [
        {"role": "agent", "text": "邀请", "options": [{"action": "make_shot", "value": "x"}]},
        {"role": "user", "text": "温柔社恐"},
        {"role": "agent", "text": "好嘞，那我们开始吧", "options": [{"label": "继续", "value": "继续"}]},
    ]
    state["p1"] = {"state": "open"}

    res = pf.run_step("p1", "__resume")

    assert res["state"] == "midstage"   # the stale invite check only looks at the LAST turn
