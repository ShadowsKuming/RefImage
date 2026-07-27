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
    parent_version_ids: list[str] | None = None,
    selected_ref_ids: list[str] | None = None,
) -> dict:
    """
    Run one turn of the per-shot AI assistant.

    Returns:
        { reply, generating, options, stage, camera }
        generating is True when the AI decided to generate an image this turn.
        options are the quick-reply chips for the user's next turn (may be empty).
        stage == "camera" → frontend shows the direct-control camera panel instead
        of chips; camera = { shot, aspect, angle } suggested defaults for it.

    Raises:
        FileNotFoundError if project or shot not found.
    """
    project = project_service.get_project(project_id)
    shot    = next((s for s in project.get("shots", []) if s["shot_id"] == shot_id), None)
    if shot is None:
        raise FileNotFoundError(f"Shot {shot_id!r} not found")

    shot_refs = project_service.list_shot_refs(project_id, shot_id)

    history = project_service.get_shot_history(project_id, shot_id)
    llm_history = [
        {"role": "user" if t["role"] == "user" else "assistant", "content": t["text"]}
        for t in history if t.get("role") in ("user", "agent")
    ]

    result = _shot_chat(
        message, llm_history, project, shot,
        shot_refs=shot_refs,
        selected_ref_ids=selected_ref_ids or [],
    )

    project_service.append_shot_messages(project_id, shot_id, [
        {"role": "user",  "text": message},
        {"role": "agent", "text": result["reply"]},
    ])

    # If agent classified a ref, kick off background processing
    if result.get("classify_ref"):
        cr = result["classify_ref"]
        background_tasks.add_task(
            project_service.set_shot_ref_type,
            project_id, shot_id, cr["ref_id"], cr["ref_type"],
        )

    if result["generating"] and result["prompt_parts"]:
        background_tasks.add_task(
            generate_service.generate_shot_image,
            project_id, shot_id, result["prompt_parts"],
            parent_version_ids or [],
            result.get("params") or {},
        )

    return {"reply": result["reply"], "generating": result["generating"],
            "options": result.get("options", []),
            "stage": result.get("stage", "chat"), "camera": result.get("camera")}


def refine_version(
    project_id: str,
    shot_id: str,
    parent_version_id: str,
    params: dict,
    background_tasks: BackgroundTasks,
) -> dict:
    """Regenerate from the refine panel: same content as the parent version, new
    visual params. Schedules generation as a background task (frontend polls),
    branching a new version off parent_version_id."""
    prompt_parts = generate_service.build_refine_parts(project_id, shot_id, parent_version_id, params)
    background_tasks.add_task(
        generate_service.generate_shot_image,
        project_id, shot_id, prompt_parts,
        [parent_version_id], params,
    )
    return {"generating": True}
