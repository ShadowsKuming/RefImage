"""
The camera panel's explicit 景别/画幅/机位 must win over whatever framing the LLM
writes into generate_image. We mock the agent loop so it emits a generate_image
call carrying the *wrong* (LLM-recommended) framing, pass the user's real picks as
`framing`, and assert the forced override lands in prompt_parts + params.
"""
from agents import shot_chat


def _fake_call_agent_factory(tool_input):
    def _fake(messages, system, tools, tool_executor, max_turns, max_tokens):
        tool_executor["generate_image"](tool_input)
        return {"text": "正在生成，请稍等片刻~"}
    return _fake


def test_panel_framing_overrides_llm(monkeypatch):
    monkeypatch.setattr(shot_chat, "_build_system", lambda *a, **k: "sys")
    # LLM proposes portrait / medium shot / eye level (its own recommendation)
    llm_input = {
        "atmosphere": "warm", "scene": "bedroom", "pose": "hugging guitar",
        "composition": "Medium shot, eye level, character from the waist up",
        "orientation": "portrait",
        "params": {"shot": "半身", "aspect": "竖图", "angle": "平视"},
    }
    monkeypatch.setattr(shot_chat, "call_agent", _fake_call_agent_factory(llm_input))

    # User actually chose 特写 / 横图 / 俯视 in the panel
    res = shot_chat.chat("就按这个生成：特写、横图、俯视", [], {}, {},
                         framing={"shot": "特写", "aspect": "横图", "angle": "俯视"})

    assert res["generating"] is True
    pp = res["prompt_parts"]
    assert pp["orientation"] == "landscape"          # 横图, not the LLM's portrait
    assert "close-up" in pp["composition"].lower()   # 特写 framing forced
    assert "above" in pp["composition"].lower() or "high" in pp["composition"].lower()  # 俯视
    assert res["params"]["shot"] == "特写"
    assert res["params"]["aspect"] == "横图"
    assert res["params"]["angle"] == "俯视"


def test_no_framing_keeps_llm_output(monkeypatch):
    monkeypatch.setattr(shot_chat, "_build_system", lambda *a, **k: "sys")
    llm_input = {
        "atmosphere": "warm", "scene": "bedroom", "pose": "hugging guitar",
        "composition": "Medium shot, eye level", "orientation": "portrait",
        "params": {"shot": "半身", "aspect": "竖图", "angle": "平视"},
    }
    monkeypatch.setattr(shot_chat, "call_agent", _fake_call_agent_factory(llm_input))

    res = shot_chat.chat("就这样生成", [], {}, {}, framing=None)
    # nothing forced → the LLM's own framing is preserved
    assert res["prompt_parts"]["orientation"] == "portrait"
    assert res["params"]["shot"] == "半身"
