"""
Regression tests for the shared null-value definition.

Bug this guards against: `translate.py` and `analyze_service.py` each had their
own null-string set, and they drifted — "no distinctive features" was null in
translate (so it got skipped and never translated) but a real value in
analyze_service (so it lit the figure dot). Result: the tooltip fell back to the
untranslated English while every other field showed the localized value.

Both modules now share `is_null_value`, and a negative-but-real answer like
"no distinctive features" must count as PRESENT (gets translated), not absent.
"""
from agents.character_extractor import is_null_value
from services.analyze_service import _is_null as svc_is_null
from tools.translate import _is_null as translate_is_null, translate_visual_spec


class TestSharedNullDefinition:
    def test_negative_but_real_answer_is_not_null(self):
        # The character was analyzed and genuinely has none — a complete value.
        assert is_null_value("no distinctive features") is False

    def test_true_absence_sentinels_are_null(self):
        for s in ["null", "none", "unknown", "n/a", "not visible",
                  "cannot determine", "undetermined", None]:
            assert is_null_value(s) is True, s

    def test_all_three_modules_agree(self):
        # The whole point of the shared definition — no drift between the
        # completeness check and the translation-skip check.
        for v in ["no distinctive features", "none", None, "long black hair"]:
            assert svc_is_null(v) == translate_is_null(v) == is_null_value(v), v


class TestTranslateKeepsNegativeRealValues:
    def test_no_distinctive_features_gets_translated_not_nulled(self, monkeypatch):
        # Mock the translation LLM; the fix is that "distinctive" reaches it at
        # all (isn't filtered out as null), so the result carries a zh/ja value.
        def fake_call(messages, system, **kwargs):
            return (
                '{"zh": {"distinctive": "无明显标志性特征", "hairstyle": "黑长直"},'
                ' "ja": {"distinctive": "特徴的な要素なし", "hairstyle": "黒髪ロング"}}'
            )
        monkeypatch.setattr("tools.translate.call", fake_call)

        out = translate_visual_spec({
            "hairstyle": "long black hair",
            "distinctive": "no distinctive features",
            "shoes": None,  # genuinely absent → stays None, not translated
        })

        assert out["zh"]["distinctive"] == "无明显标志性特征"
        assert out["ja"]["distinctive"] == "特徴的な要素なし"
        assert out["en"]["distinctive"] == "no distinctive features"  # passthrough
        assert out["zh"]["shoes"] is None  # real absence still nulled everywhere
