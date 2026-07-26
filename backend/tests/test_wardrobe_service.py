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
