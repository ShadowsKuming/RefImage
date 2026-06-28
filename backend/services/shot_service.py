"""
services/shot_service.py — Shot-level business logic

Handles per-shot AI conversation (which decides when to generate the reference image).
Image generation is kicked off as a FastAPI BackgroundTask so the chat response
returns immediately while generation runs in the background.
"""
from fastapi import BackgroundTasks
from agents.shot_chat import chat as _shot_chat
from services import project_service, generate_service


def shot_chat(
    project_id: str,
    shot_id: str,
    message: str,
    background_tasks: BackgroundTasks,
) -> dict:
    """
    Run one turn of the per-shot AI assistant.

    Returns:
        { reply: str, generating: bool }
        generating is True when the AI decided to generate an image this turn.

    Raises:
        FileNotFoundError if project or shot not found.
    """
    project = project_service.get_project(project_id)
    shot    = next((s for s in project.get("shots", []) if s["shot_id"] == shot_id), None)
    if shot is None:
        raise FileNotFoundError(f"Shot {shot_id!r} not found")

    history = project_service.get_shot_history(project_id, shot_id)
    llm_history = [
        {"role": "user" if t["role"] == "user" else "assistant", "content": t["text"]}
        for t in history if t.get("role") in ("user", "agent")
    ]

    result = _shot_chat(message, llm_history, project, shot)

    project_service.append_shot_messages(project_id, shot_id, [
        {"role": "user",  "text": message},
        {"role": "agent", "text": result["reply"]},
    ])

    if result["generating"] and result["prompt_parts"]:
        background_tasks.add_task(
            generate_service.generate_shot_image,
            project_id, shot_id, result["prompt_parts"],
        )

    return {"reply": result["reply"], "generating": result["generating"]}
