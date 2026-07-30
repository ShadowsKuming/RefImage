"""
services/guide_service.py — Planning assistant & guide generation logic

Wraps tools/planning_chat.py and exposes a clean service interface so the API
layer stays thin (HTTP boundary only, no business logic).
"""
from agents.planning_chat import chat as _planning_chat
from services import project_service


def planning_chat(project_id: str, message: str, history: list[dict], reply_lang: str = "zh") -> dict:
    """
    Run one turn of the AI planning assistant for a project.

    Args:
        project_id: The project UUID.
        message:    The user's latest message.
        history:    Prior turns in frontend format [{ role: 'user'|'agent', text: str }].

    Returns:
        { reply: str, brief: dict | None }
        brief is non-None when the AI called update_brief this turn.

    Raises:
        FileNotFoundError: if the project doesn't exist.
    """
    project = project_service.get_project(project_id)

    # Convert frontend { role, text } → LLM { role, content }
    llm_history = [
        {
            "role":    "user" if turn["role"] == "user" else "assistant",
            "content": turn["text"],
        }
        for turn in history
        if turn.get("role") in ("user", "agent")
    ]

    result = _planning_chat(message, llm_history, project, project_id, reply_lang)
    reply = result["reply"]
    brief = result["brief"]
    options = result.get("options") or []

    # Persist updated chat history. Options ride on the agent turn so quick-reply
    # chips survive a reload (the frontend restores them from the last agent msg).
    updated_history = list(history) + [
        {"role": "user",  "text": message},
        {"role": "agent", "text": reply, "options": options},
    ]
    project_service.save_chat_history(project_id, updated_history)

    # Persist brief if the AI committed a plan
    if brief:
        project_service.save_brief(project_id, brief)

    # result["plan"/"wardrobe"/"moments"] are the fresh values when the AI mutated
    # them this turn (already persisted by the services), else None.
    return {
        "reply": reply, "brief": brief,
        "options": result.get("options", []),
        "plan": result.get("plan"),
        "wardrobe": result.get("wardrobe"),
        "moments": result.get("moments"),
    }
