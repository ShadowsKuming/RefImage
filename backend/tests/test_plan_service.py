"""
Unit tests for plan_service — the deterministic plan.json data layer.

No LLM here: these pin the pure-function behavior the AI tools and the frontend
coarse-save both rely on — id assignment/stability, add/remove semantics, the
add/remove-only contract (no in-place update), and checklist cleanup on removal.

Each test points STORAGE_ROOT at a tmp dir so nothing touches real project data.
"""
import pytest
from services import plan_service


@pytest.fixture(autouse=True)
def _tmp_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(plan_service, "STORAGE_ROOT", tmp_path)
    (tmp_path / "p1" / "plan").mkdir(parents=True)
    return tmp_path


def test_empty_project_returns_default_shape():
    d = plan_service.load_plan_data("p1")
    assert set(d) == {
        "theme", "shoot_date", "crew", "equipment", "schedule",
        "notes", "location_meta", "prepared", "notes_done",
    }
    assert d["equipment"] == [] and d["theme"] == ""


def test_add_equipment_assigns_prefixed_id_and_persists():
    item = plan_service.add_equipment("p1", name="  85mm 镜头  ", category="lens")
    assert item["id"].startswith("eq_")
    assert item["name"] == "85mm 镜头"          # trimmed
    assert item["required"] is True             # default
    reloaded = plan_service.load_plan_data("p1")
    assert reloaded["equipment"][0]["id"] == item["id"]


def test_add_equipment_rejects_blank_name():
    with pytest.raises(ValueError):
        plan_service.add_equipment("p1", name="   ")


def test_remove_equipment_by_id_and_unknown_id():
    a = plan_service.add_equipment("p1", name="A")
    b = plan_service.add_equipment("p1", name="B")
    assert plan_service.remove_equipment("p1", "eq_nope") is None
    removed = plan_service.remove_equipment("p1", a["id"])
    assert removed["name"] == "A"
    names = [e["name"] for e in plan_service.load_plan_data("p1")["equipment"]]
    assert names == ["B"] and b["id"]


def test_remove_equipment_drops_name_from_prepared():
    plan_service.add_equipment("p1", name="相机机身")
    item = plan_service.add_equipment("p1", name="反光板")
    plan_service.save_plan_data("p1", {**plan_service.load_plan_data("p1"), "prepared": ["相机机身", "反光板"]})
    plan_service.remove_equipment("p1", item["id"])
    assert plan_service.load_plan_data("p1")["prepared"] == ["相机机身"]


def test_duplicate_names_removed_unambiguously_by_id():
    a = plan_service.add_equipment("p1", name="50mm 镜头")
    b = plan_service.add_equipment("p1", name="50mm 镜头")
    plan_service.remove_equipment("p1", a["id"])
    remaining = plan_service.load_plan_data("p1")["equipment"]
    assert len(remaining) == 1 and remaining[0]["id"] == b["id"]


def test_note_defaults_and_enum_coercion():
    item = plan_service.add_note("p1", title="场地申请", phase="bogus", priority="bogus")
    assert item["id"].startswith("nt_")
    assert item["phase"] == "pre" and item["priority"] == "mid"


def test_remove_note_drops_title_from_notes_done():
    keep = plan_service.add_note("p1", title="保留")
    drop = plan_service.add_note("p1", title="删除")
    plan_service.save_plan_data("p1", {**plan_service.load_plan_data("p1"), "notes_done": ["保留", "删除"]})
    plan_service.remove_note("p1", drop["id"])
    assert plan_service.load_plan_data("p1")["notes_done"] == ["保留"]


def test_schedule_segment_requires_scene():
    with pytest.raises(ValueError):
        plan_service.add_schedule_segment("p1", scene="")
    seg = plan_service.add_schedule_segment("p1", scene="音乐教室", light="自然光", priority="high")
    assert seg["id"].startswith("sg_") and seg["shot_ids"] == []


def test_update_overview_only_touches_provided_fields():
    plan_service.update_overview("p1", theme="青春", crew={"photographers": 2, "cosers": None})
    plan_service.update_overview("p1", shoot_date="2026/08/15")
    d = plan_service.load_plan_data("p1")
    assert d["theme"] == "青春"                 # preserved across the second call
    assert d["shoot_date"] == "2026/08/15"
    assert d["crew"] == {"photographers": 2}    # None values dropped


def test_save_plan_data_backfills_ids_and_drops_unknown_keys():
    saved = plan_service.save_plan_data("p1", {
        "equipment": [{"name": "无 id 设备"}],
        "bogus_key": "should be dropped",
    })
    assert saved["equipment"][0]["id"].startswith("eq_")
    assert "bogus_key" not in saved


def test_ids_are_stable_across_loads():
    plan_service.add_equipment("p1", name="A")
    first = plan_service.load_plan_data("p1")["equipment"][0]["id"]
    second = plan_service.load_plan_data("p1")["equipment"][0]["id"]
    assert first == second
