"""
Unit test for the planning agent's same-turn dedup guard (make_dedup).

The agent occasionally emits the identical mutation call several times in one
turn; without dedup that creates duplicate items. This pins that an identical
(tool, args) call runs at most once, while distinct args and distinct tools
still run.
"""
from agents.planning_chat import make_dedup


def test_identical_call_runs_once():
    seen = set()
    dedup = make_dedup(seen)
    calls = []
    fn = dedup("add_moment", lambda inp: (calls.append(inp), "ok")[1])
    inp = {"title": "天台", "source": "S1"}
    assert fn(inp) == "ok"
    r2 = fn(dict(inp))          # same args (new dict) → skipped
    assert "已经处理过" in r2
    assert len(calls) == 1


def test_distinct_args_both_run():
    dedup = make_dedup(set())
    calls = []
    fn = dedup("add_costume", lambda inp: (calls.append(inp["name"]), "ok")[1])
    fn({"name": "假发"})
    fn({"name": "校服"})
    assert calls == ["假发", "校服"]


def test_key_ignores_arg_order():
    dedup = make_dedup(set())
    calls = []
    fn = dedup("add_prop", lambda inp: (calls.append(1), "ok")[1])
    fn({"name": "贝斯", "note": "n"})
    fn({"note": "n", "name": "贝斯"})   # same content, different key order → skipped
    assert len(calls) == 1


def test_shared_seen_isolates_by_tool_name():
    seen = set()
    dedup = make_dedup(seen)
    a_calls, b_calls = [], []
    add = dedup("add_moment", lambda inp: (a_calls.append(1), "ok")[1])
    rem = dedup("remove_moment", lambda inp: (b_calls.append(1), "ok")[1])
    add({"id": "x"})
    rem({"id": "x"})   # same args but different tool → runs
    assert len(a_calls) == 1 and len(b_calls) == 1
