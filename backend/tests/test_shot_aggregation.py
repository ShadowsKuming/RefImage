"""
Unit tests for the shot→project aggregation + handbook assembly layer.

No LLM here — these pin the deterministic derived views the workspace panels and
the handbook PDF both rely on: locations/equipment/schedule roll-ups, the
Overleaf-style compile snapshot, the 已完成 gate, and handbook assembly. Every
test points STORAGE_ROOT (both modules) at a tmp dir so nothing touches real data.

Robustness is the point: empty projects, shots with no plan, corrupted plan.json,
missing location/equipment/duration must never raise — they're just skipped.
"""
import json

import pytest
from services import project_service, shot_plan_service


@pytest.fixture(autouse=True)
def _tmp_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(project_service, "STORAGE_ROOT", tmp_path)
    monkeypatch.setattr(shot_plan_service, "STORAGE_ROOT", tmp_path)
    return tmp_path


def _mkshot(root, pid, sid, *, plan=None, shot=None, sheet=None, raw_plan=None):
    d = root / pid / "shots" / sid
    d.mkdir(parents=True, exist_ok=True)
    base_shot = {"shot_id": sid, "title": sid.upper(), "status": "refined"}
    if shot:
        base_shot.update(shot)
    (d / "shot.json").write_text(json.dumps(base_shot, ensure_ascii=False))
    if raw_plan is not None:
        (d / "plan.json").write_text(raw_plan)
    elif plan is not None:
        (d / "plan.json").write_text(json.dumps(plan, ensure_ascii=False))
    if sheet is not None:
        (d / "sheet.json").write_text(json.dumps(sheet, ensure_ascii=False))
    return d


def _plan(*, location="", indoor="室内", equipment=None, duration="", props=None,
          maincolor="", backup="", risks=None, tags=None):
    return {
        "overview": {"tags": tags or [], "priority": "mid"},
        "logistics": {
            "scene": {"location": location, "indoor_outdoor": indoor},
            "timing": {"duration": duration},
            "props": {"character": props or []},
            "equipment": equipment or [],
        },
        "technique": {"params": {"maincolor": maincolor}, "backup": backup, "risks": risks or []},
    }


# ── aggregate_shot_logistics ──────────────────────────────────────────────────

def test_logistics_empty_project(tmp_path):
    (tmp_path / "p1").mkdir()
    out = project_service.aggregate_shot_logistics("p1")
    assert out == {"locations": [], "equipment": []}


def test_logistics_missing_shots_dir_no_raise():
    # project dir absent entirely
    out = project_service.aggregate_shot_logistics("ghost")
    assert out == {"locations": [], "equipment": []}


def test_logistics_dedups_locations_and_links_shots(tmp_path):
    _mkshot(tmp_path, "p1", "s01", plan=_plan(location="音乐教室"))
    _mkshot(tmp_path, "p1", "s02", plan=_plan(location="音乐教室"))
    _mkshot(tmp_path, "p1", "s03", plan=_plan(location="走廊"))
    locs = project_service.aggregate_shot_logistics("p1")["locations"]
    assert [l["name"] for l in locs] == ["音乐教室", "走廊"]
    assert [s["shot_id"] for s in locs[0]["shots"]] == ["s01", "s02"]


def test_logistics_dedups_equipment_merges_purposes(tmp_path):
    _mkshot(tmp_path, "p1", "s01", plan=_plan(equipment=[{"name": "反光板", "purpose": "补光"}]))
    _mkshot(tmp_path, "p1", "s02", plan=_plan(equipment=[{"name": "反光板", "purpose": "压暗面"}, {"name": "三脚架"}]))
    eq = {e["name"]: e for e in project_service.aggregate_shot_logistics("p1")["equipment"]}
    assert set(eq) == {"反光板", "三脚架"}
    assert eq["反光板"]["purposes"] == ["补光", "压暗面"]
    assert len(eq["反光板"]["shots"]) == 2


def test_logistics_equipment_string_form(tmp_path):
    _mkshot(tmp_path, "p1", "s01", plan=_plan(equipment=["三脚架"]))
    eq = project_service.aggregate_shot_logistics("p1")["equipment"]
    assert eq[0]["name"] == "三脚架" and eq[0]["purposes"] == []


def test_logistics_skips_missing_plan_and_blank_location(tmp_path):
    _mkshot(tmp_path, "p1", "s01", shot={"title": "no plan"})          # no plan.json
    _mkshot(tmp_path, "p1", "s02", plan=_plan(location=""))             # blank location
    _mkshot(tmp_path, "p1", "s03", plan=_plan(location="教室"))
    locs = project_service.aggregate_shot_logistics("p1")["locations"]
    assert [l["name"] for l in locs] == ["教室"]


def test_logistics_corrupted_plan_json_skipped(tmp_path):
    _mkshot(tmp_path, "p1", "s01", raw_plan="{ this is not json ")
    _mkshot(tmp_path, "p1", "s02", plan=_plan(location="教室", equipment=[{"name": "灯"}]))
    out = project_service.aggregate_shot_logistics("p1")
    assert [l["name"] for l in out["locations"]] == ["教室"]
    assert [e["name"] for e in out["equipment"]] == ["灯"]


# ── aggregate_schedule ────────────────────────────────────────────────────────

def test_schedule_groups_by_location_sums_duration(tmp_path):
    _mkshot(tmp_path, "p1", "s01", plan=_plan(location="音乐教室", duration="20 分钟"))
    _mkshot(tmp_path, "p1", "s02", plan=_plan(location="音乐教室", duration="15分钟"))
    _mkshot(tmp_path, "p1", "s03", plan=_plan(location="走廊", duration="30 分钟"))
    rows = project_service.aggregate_schedule("p1")
    assert [r["scene"] for r in rows] == ["音乐教室", "走廊"]
    assert rows[0]["shots"] == "S01–S02" and rows[0]["duration_minutes"] == 35
    assert rows[1]["shots"] == "S03" and rows[1]["duration_minutes"] == 30
    assert rows[0]["shot_ids"] == ["s01", "s02"]


def test_schedule_labels_track_all_shots_not_just_located(tmp_path):
    # s01 has no location → still consumes label S01, so s02 is S02
    _mkshot(tmp_path, "p1", "s01", plan=_plan(location=""))
    _mkshot(tmp_path, "p1", "s02", plan=_plan(location="教室", duration="10 分钟"))
    rows = project_service.aggregate_schedule("p1")
    assert rows[0]["shots"] == "S02"


def test_schedule_empty_and_no_durations(tmp_path):
    (tmp_path / "p1").mkdir()
    assert project_service.aggregate_schedule("p1") == []
    _mkshot(tmp_path, "p2", "s01", plan=_plan(location="教室"))  # no duration
    rows = project_service.aggregate_schedule("p2")
    assert rows[0]["duration_minutes"] == 0


def test_parse_minutes_variants():
    assert project_service._parse_minutes("10-15 分钟") == 10
    assert project_service._parse_minutes("约 20 分钟") == 20
    assert project_service._parse_minutes("") == 0
    assert project_service._parse_minutes("无") == 0


def test_clock_from_variants():
    cf = project_service._clock_from
    assert cf("15:00") == 15 * 60
    assert cf("3点") == 3 * 60
    assert cf("下午3点") == 15 * 60
    assert cf("下午三点") == 15 * 60
    assert cf("晚上八点") == 20 * 60
    assert cf("上午10点") == 10 * 60
    assert cf("九点半") == 9 * 60 + 30
    assert cf("傍晚") is None          # too vague to place on a clock
    assert cf("待定") is None
    assert cf("") is None


def test_schedule_time_concrete_start_lays_out_sequential(tmp_path, monkeypatch):
    import services.plan_service as plan_service
    monkeypatch.setattr(plan_service, "STORAGE_ROOT", tmp_path)
    _mkshot(tmp_path, "p1", "s01", plan=_plan(location="卧室", duration="60 分钟"))
    _mkshot(tmp_path, "p1", "s02", plan=_plan(location="客厅", duration="30 分钟"))
    plan_service.update_overview("p1", shoot_time="下午3点")
    rows = project_service.aggregate_schedule("p1")
    assert rows[0]["time"] == "15:00"   # first segment starts at the given time
    assert rows[1]["time"] == "16:00"   # + 60 min of the first segment


def test_schedule_time_vague_labels_only_first_row(tmp_path, monkeypatch):
    import services.plan_service as plan_service
    monkeypatch.setattr(plan_service, "STORAGE_ROOT", tmp_path)
    _mkshot(tmp_path, "p1", "s01", plan=_plan(location="卧室", duration="60 分钟"))
    _mkshot(tmp_path, "p1", "s02", plan=_plan(location="客厅", duration="30 分钟"))
    plan_service.update_overview("p1", shoot_time="傍晚")
    rows = project_service.aggregate_schedule("p1")
    assert rows[0]["time"] == "傍晚" and rows[1]["time"] == ""


# ── compile / load sheet ──────────────────────────────────────────────────────

def test_compile_snapshots_current_plan(tmp_path):
    _mkshot(tmp_path, "p1", "s01", plan=_plan(location="教室", backup="改走廊"))
    sheet = shot_plan_service.compile_sheet("p1", "s01")
    assert sheet["plan"]["logistics"]["scene"]["location"] == "教室"
    assert "compiled_at" in sheet
    assert shot_plan_service.load_sheet("p1", "s01")["plan"] == sheet["plan"]


def test_compile_is_a_frozen_snapshot(tmp_path):
    _mkshot(tmp_path, "p1", "s01", plan=_plan(location="教室"))
    shot_plan_service.compile_sheet("p1", "s01")
    # edit the plan afterwards → sheet must NOT change until recompiled
    shot_plan_service.update_field("p1", "s01", "logistics.scene.place", "新场景")
    assert shot_plan_service.load_sheet("p1", "s01")["plan"]["logistics"]["scene"].get("place", "") == ""


def test_compile_without_plan_raises(tmp_path):
    _mkshot(tmp_path, "p1", "s01", shot={"title": "x"})  # no plan
    with pytest.raises(FileNotFoundError):
        shot_plan_service.compile_sheet("p1", "s01")


def test_load_sheet_absent_returns_none(tmp_path):
    _mkshot(tmp_path, "p1", "s01", plan=_plan())
    assert shot_plan_service.load_sheet("p1", "s01") is None


# ── set_shot_completed ────────────────────────────────────────────────────────

def test_set_completed_persists(tmp_path):
    _mkshot(tmp_path, "p1", "s01", plan=_plan())
    project_service.set_shot_completed("p1", "s01", True)
    shot = json.loads((tmp_path / "p1" / "shots" / "s01" / "shot.json").read_text())
    assert shot["completed"] is True
    project_service.set_shot_completed("p1", "s01", False)
    shot = json.loads((tmp_path / "p1" / "shots" / "s01" / "shot.json").read_text())
    assert shot["completed"] is False


def test_set_completed_unknown_shot_raises(tmp_path):
    (tmp_path / "p1" / "shots").mkdir(parents=True)
    with pytest.raises(FileNotFoundError):
        project_service.set_shot_completed("p1", "nope", True)


# ── get_handbook assembly ─────────────────────────────────────────────────────

def _stub_project(monkeypatch, shots, wardrobe=None, plan_data=None):
    def fake_get_project(pid):
        return {
            "shots": shots,
            "logistics_rollup": project_service.aggregate_shot_logistics(pid),
            "wardrobe": wardrobe or {},
            "characters": [{"name": "秋山澪", "series": "轻音少女", "avatar": "/a.png"}],
            "plan": {"data": plan_data or {"theme": "校园轻音"}},
            "cover": "/cover.png",
            "character": "秋山澪",
        }
    monkeypatch.setattr(project_service, "get_project", fake_get_project)


def test_handbook_only_includes_compiled_pages(tmp_path, monkeypatch):
    _mkshot(tmp_path, "p1", "s01", plan=_plan(location="教室"),
            sheet={"compiled_at": "t", "plan": _plan(location="教室")})
    _mkshot(tmp_path, "p1", "s02", plan=_plan(location="走廊"))  # not compiled
    _stub_project(monkeypatch, [
        {"shot_id": "s01", "title": "贝斯练习", "image_url": "/i1", "completed": True},
        {"shot_id": "s02", "title": "走廊", "image_url": "/i2", "completed": False},
    ])
    hb = project_service.get_handbook("p1")
    assert [p["shot_id"] for p in hb["pages"]] == ["s01"]
    assert hb["pages"][0]["index"] == 1


def test_handbook_aggregates_sections(tmp_path, monkeypatch):
    _mkshot(tmp_path, "p1", "s01",
            plan=_plan(location="音乐教室", equipment=[{"name": "反光板"}], duration="20 分钟",
                       props=["贝斯"], maincolor="蓝", backup="改走廊", risks=["注意表情"],
                       tags=["校园", "治愈"]))
    _stub_project(monkeypatch,
                  [{"shot_id": "s01", "title": "贝斯练习", "image_url": "/i1", "completed": False}],
                  wardrobe={"costumes": [{"name": "校服"}]})
    hb = project_service.get_handbook("p1")
    assert hb["summary"]["shot_count"] == 1
    assert hb["summary"]["scene_count"] == 1
    assert hb["summary"]["duration_minutes"] == 20
    assert hb["summary"]["costume_count"] == 1
    assert set(hb["summary"]["tags"]) == {"校园", "治愈"}
    assert "#7fb3e0" in hb["palette"]                      # 蓝 → hex
    assert hb["prep"]["equipment"] == ["反光板"] and hb["prep"]["props"] == ["贝斯"]
    assert hb["prep"]["costumes"] == ["校服"] and hb["prep"]["locations"] == ["音乐教室"]
    assert hb["backups"][0]["backup"] == "改走廊" and hb["backups"][0]["risks"] == ["注意表情"]
    assert hb["schedule"][0]["scene"] == "音乐教室"


def test_handbook_default_palette_when_no_colors(tmp_path, monkeypatch):
    _mkshot(tmp_path, "p1", "s01", plan=_plan(location="教室"))
    _stub_project(monkeypatch, [{"shot_id": "s01", "title": "x", "image_url": "", "completed": False}])
    hb = project_service.get_handbook("p1")
    assert len(hb["palette"]) >= 3          # falls back to default palette
    assert hb["pages"] == []                # nothing compiled


def test_handbook_empty_project(tmp_path, monkeypatch):
    (tmp_path / "p1").mkdir()
    _stub_project(monkeypatch, [])
    hb = project_service.get_handbook("p1")
    assert hb["pages"] == [] and hb["summary"]["shot_count"] == 0
    assert hb["schedule"] == [] and hb["backups"] == []
