"""
Unit tests for moments_service granular add/remove (名场面 data layer).

Deterministic, offline — the LLM generate() path is NOT tested here (it's an eval).
STORAGE_ROOT points at a tmp dir so no real project data is touched.
"""
import pytest
from services import moments_service as ms


@pytest.fixture(autouse=True)
def _tmp_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(ms, "STORAGE_ROOT", tmp_path)
    (tmp_path / "p1" / "context").mkdir(parents=True)
    return tmp_path


def test_empty_returns_shape():
    assert ms.load_moments("p1", "c1") == {"moments": []}


def test_add_moment_assigns_id_and_trims():
    m = ms.add_moment("p1", "c1", "  蓝白碗事件 ", source="第一季", description="d")
    assert m["id"].startswith("mo_") and m["title"] == "蓝白碗事件"
    assert m["source"] == "第一季" and m["description"] == "d"
    assert len(ms.load_moments("p1", "c1")["moments"]) == 1


def test_add_moment_blank_rejected():
    with pytest.raises(ValueError):
        ms.add_moment("p1", "c1", "   ")


def test_remove_moment_by_id_and_unknown():
    a = ms.add_moment("p1", "c1", "A")
    b = ms.add_moment("p1", "c1", "B")
    assert ms.remove_moment("p1", "c1", "nope") is None
    assert ms.remove_moment("p1", "c1", a["id"])["title"] == "A"
    left = ms.load_moments("p1", "c1")["moments"]
    assert len(left) == 1 and left[0]["id"] == b["id"]


def test_moments_are_per_character():
    ms.add_moment("p1", "c1", "只属于 c1")
    assert len(ms.load_moments("p1", "c1")["moments"]) == 1
    assert ms.load_moments("p1", "c2")["moments"] == []
