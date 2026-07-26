"""
Unit tests for wardrobe_service — the costume/props data layer (plan/wardrobe.json).

Deterministic, offline. Pins the shape/id/save behavior the frontend coarse-save
relies on. STORAGE_ROOT points at a tmp dir so no real project data is touched.
"""
import pytest
from services import wardrobe_service as ws


@pytest.fixture(autouse=True)
def _tmp_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(ws, "STORAGE_ROOT", tmp_path)
    (tmp_path / "p1" / "plan").mkdir(parents=True)
    return tmp_path


def test_empty_returns_default_shape():
    d = ws.load_wardrobe("p1")
    assert set(d) == {"costume", "props"}
    assert d["costume"] == [] and d["props"] == []


def test_save_assigns_prefixed_ids_and_drops_unknown_keys():
    saved = ws.save_wardrobe("p1", {
        "costume": [{"name": "假发", "category": "wig"}],
        "props": [{"name": "贝斯"}],
        "bogus": "drop me",
    })
    assert saved["costume"][0]["id"].startswith("cs_")
    assert saved["props"][0]["id"].startswith("pr_")
    assert "bogus" not in saved


def test_ids_stable_across_loads():
    ws.save_wardrobe("p1", {"costume": [{"name": "假发"}]})
    a = ws.load_wardrobe("p1")["costume"][0]["id"]
    b = ws.load_wardrobe("p1")["costume"][0]["id"]
    assert a == b


def test_add_costume_prop_and_remove():
    c = ws.add_costume("p1", "  黑长直假发 ", category="wig", note="n", essential=False)
    assert c["id"].startswith("cs_") and c["name"] == "黑长直假发"
    assert c["category"] == "wig" and c["essential"] is False
    p = ws.add_prop("p1", "贝斯")
    assert p["id"].startswith("pr_") and p["essential"] is True
    d = ws.load_wardrobe("p1")
    assert len(d["costume"]) == 1 and len(d["props"]) == 1
    assert ws.remove_item("p1", "nope") is None
    assert ws.remove_item("p1", c["id"])["name"] == "黑长直假发"
    assert len(ws.load_wardrobe("p1")["costume"]) == 0


def test_add_costume_bad_category_falls_back_and_blank_rejected():
    c = ws.add_costume("p1", "东西", category="bogus")
    assert c["category"] == "misc"
    with pytest.raises(ValueError):
        ws.add_costume("p1", "   ")
    with pytest.raises(ValueError):
        ws.add_prop("p1", "")


def test_granular_add_does_not_persist_derived_image():
    import json
    ws.add_prop("p1", "贝斯")
    raw = json.loads((ws.STORAGE_ROOT / "p1" / "plan" / "wardrobe.json").read_text())
    assert all("image" not in i for i in raw["props"])
