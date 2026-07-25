"""
Unit tests for the field-completeness logic in analyze_service.

This is the gate that decides whether Step 1 is "done" (all 8 visual fields
filled) — the frontend lights up the figure dots and unlocks the flow off it.
It must treat the vision LLM's various ways of saying "I couldn't see this"
(null / none / N/A / "not visible" …) as missing, not as a real value.
"""
from services.analyze_service import _is_null, _missing


class TestIsNull:
    def test_none_is_null(self):
        assert _is_null(None) is True

    def test_real_value_is_not_null(self):
        assert _is_null("black knee-high boots") is False

    def test_null_sentinel_strings_are_null(self):
        # The vision LLM says "I can't see this" in many ways — all must count
        # as missing, or a hallucinated-but-empty field would mark Step 1 done.
        for s in ["null", "none", "unknown", "n/a", "not visible",
                  "cannot determine", "undetermined"]:
            assert _is_null(s) is True, s

    def test_null_sentinels_are_case_and_space_insensitive(self):
        for s in ["NULL", "None", "  N/A  ", "Not Visible", "UNKNOWN"]:
            assert _is_null(s) is True, s

    def test_empty_string_is_not_a_sentinel(self):
        # "" isn't in the sentinel set; document the current behavior so a
        # future change to treat it as missing is a deliberate decision.
        assert _is_null("") is False


class TestMissing:
    def test_all_present_returns_empty(self):
        extracted = {f"field{i}": f"value{i}" for i in range(8)}
        assert _missing(extracted) == []

    def test_returns_only_the_null_fields_in_order(self):
        extracted = {
            "hairstyle": "long black",
            "shoes": None,
            "proportions": "not visible",
            "color_palette": "black and white",
        }
        assert _missing(extracted) == ["shoes", "proportions"]

    def test_all_missing(self):
        extracted = {"a": None, "b": "unknown", "c": "N/A"}
        assert _missing(extracted) == ["a", "b", "c"]
