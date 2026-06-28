"""
tools/llm.py — Provider-agnostic LLM client

Wraps Claude, OpenAI, and Gemini behind a single interface so the rest of the
codebase never imports provider SDKs directly.  Switch providers by setting the
LLM_PROVIDER env var; models can be overridden per-provider with LLM_MODEL_*.

Tool definitions always use Anthropic's format as the canonical schema.
OpenAI format is derived internally via _anthropic_tool_to_openai().

Public API:
  call()            — plain text, no tools
  call_with_tools() — single-turn with optional tools
  call_agent()      — multi-turn agentic loop (search → … → passthrough tool)
"""
import json
import os
from config import LLM_PROVIDER as PROVIDER, LLM_MODEL as TEXT_MODEL


# ── Public interface ──────────────────────────────────────────────────────────

def call(messages: list[dict], system: str, max_tokens: int = 1500) -> str:
    """Plain text call, no tools. Returns the reply string."""
    result = call_with_tools(messages, system, tools=[], max_tokens=max_tokens)
    return result["text"]


def call_with_tools(
    messages: list[dict],
    system: str,
    tools: list[dict],  # Anthropic tool format as canonical
    max_tokens: int = 1500,
) -> dict:
    """
    Single-turn call with optional tools.
    Returns: { text: str, tool_calls: [{ name: str, input: dict }] }
    """
    fn = {"claude": _call_claude, "openai": _call_openai, "gemini": _call_gemini}.get(PROVIDER)
    if not fn:
        raise ValueError(f"Unknown LLM_PROVIDER: '{PROVIDER}'. Choose from: claude, openai, gemini")
    return fn(messages, system, tools, max_tokens)


def call_agent(
    messages: list[dict],
    system: str,
    tools: list[dict],
    tool_executor: dict,  # { tool_name: callable(input: dict) -> str }
    max_turns: int = 5,
    max_tokens: int = 1500,
) -> dict:
    """
    Multi-turn agentic loop.

    On each turn the LLM may call tools.  Tools are split into two categories:
      - executor tools  (in tool_executor): called immediately, result fed back
      - passthrough tools (not in tool_executor): collected and returned to caller

    The loop stops when a turn produces no executor tool calls (either the model
    returned plain text, or it only called passthrough tools like update_profile).

    Returns: { text: str, tool_calls: [{ name, input }] }
      text       — last text reply from the model
      tool_calls — all passthrough tool calls collected across turns
    """
    fn = {"claude": _agent_claude, "openai": _agent_openai}.get(PROVIDER)
    if not fn:
        raise ValueError(f"call_agent not supported for provider: '{PROVIDER}'")
    return fn(messages, system, tools, tool_executor, max_turns, max_tokens)


# ── Claude ────────────────────────────────────────────────────────────────────

def _call_claude(messages, system, tools, max_tokens):
    import anthropic
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    kwargs = dict(
        model=TEXT_MODEL["claude"],
        max_tokens=max_tokens,
        system=system,
        messages=messages,
    )
    if tools:
        kwargs["tools"] = tools
    response = client.messages.create(**kwargs)

    text = ""
    tool_calls = []
    for block in response.content:
        if block.type == "text":
            text = block.text
        elif block.type == "tool_use":
            tool_calls.append({"name": block.name, "input": block.input})
    return {"text": text, "tool_calls": tool_calls}


def _agent_claude(messages, system, tools, tool_executor, max_turns, max_tokens):
    import anthropic
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    msgs = list(messages)
    final_text = ""
    final_tool_calls = []

    for _ in range(max_turns):
        response = client.messages.create(
            model=TEXT_MODEL["claude"], max_tokens=max_tokens,
            system=system, tools=tools, messages=msgs,
        )
        text = ""
        exec_calls = []
        passthrough_calls = []
        for block in response.content:
            if block.type == "text":
                text = block.text
            elif block.type == "tool_use":
                if block.name in tool_executor:
                    exec_calls.append(block)
                else:
                    passthrough_calls.append({"name": block.name, "input": block.input})

        final_text = text
        final_tool_calls.extend(passthrough_calls)

        if not exec_calls:
            break

        msgs.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in exec_calls:
            result = tool_executor[block.name](block.input)
            tool_results.append({
                "type": "tool_result", "tool_use_id": block.id, "content": result,
            })
        msgs.append({"role": "user", "content": tool_results})

    return {"text": final_text, "tool_calls": final_tool_calls}


# ── OpenAI ────────────────────────────────────────────────────────────────────

def _anthropic_tool_to_openai(tool: dict) -> dict:
    """Convert Anthropic tool schema to OpenAI function-calling format."""
    return {
        "type": "function",
        "function": {
            "name":        tool["name"],
            "description": tool.get("description", ""),
            "parameters":  tool.get("input_schema", {}),
        },
    }


def _call_openai(messages, system, tools, max_tokens):
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    full_messages = [{"role": "system", "content": system}] + messages
    kwargs = dict(model=TEXT_MODEL["openai"], max_completion_tokens=max_tokens, messages=full_messages)
    if tools:
        kwargs["tools"] = [_anthropic_tool_to_openai(t) for t in tools]
    response = client.chat.completions.create(**kwargs)

    msg = response.choices[0].message
    text = msg.content or ""
    tool_calls = []
    for tc in (msg.tool_calls or []):
        tool_calls.append({"name": tc.function.name, "input": json.loads(tc.function.arguments)})
    return {"text": text, "tool_calls": tool_calls}


def _agent_openai(messages, system, tools, tool_executor, max_turns, max_tokens):
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    openai_tools = [_anthropic_tool_to_openai(t) for t in tools]
    msgs = [{"role": "system", "content": system}] + list(messages)
    final_text = ""
    final_tool_calls = []

    for turn in range(max_turns):
        # Turn 0: "auto" so pure chat messages don't force a tool call.
        # Turns 1+: "required" to keep the search loop going once started.
        # Last turn: back to "auto" to allow a plain-text wrap-up reply.
        if turn == 0 or turn == max_turns - 1:
            tool_choice = "auto"
        else:
            tool_choice = "required"

        response = client.chat.completions.create(
            model=TEXT_MODEL["openai"], max_completion_tokens=max_tokens,
            messages=msgs, tools=openai_tools if openai_tools else None,
            tool_choice=tool_choice if openai_tools else "none",
        )
        msg = response.choices[0].message
        final_text = msg.content or ""
        exec_calls = []
        for tc in (msg.tool_calls or []):
            name       = tc.function.name
            tool_input = json.loads(tc.function.arguments)
            if name in tool_executor:
                exec_calls.append(tc)
            else:
                # Passthrough tool (e.g. update_profile): collect and stop looping
                final_tool_calls.append({"name": name, "input": tool_input})

        if not exec_calls:
            break

        msgs.append(msg)
        for tc in exec_calls:
            result = tool_executor[tc.function.name](json.loads(tc.function.arguments))
            msgs.append({"role": "tool", "tool_call_id": tc.id, "content": result})

    return {"text": final_text, "tool_calls": final_tool_calls}


# ── Gemini ────────────────────────────────────────────────────────────────────

def _call_gemini(messages, system, tools, max_tokens):
    raise NotImplementedError("Gemini provider not yet implemented")
