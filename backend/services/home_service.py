"""
services/home_service.py — Home page data: list all projects as lightweight summaries

Only reads meta.json and counts shots/ subdirectories per project.
Does not load full project context (world, character, visual_spec) — that's project_service's job.
"""
import json
from pathlib import Path

STORAGE_ROOT = Path(__file__).parent.parent / "storage" / "projects"


def list_projects() -> list[dict]:
    """
    Return a summary card for every project on disk, sorted newest first.

    Each item: { project_id, character, series, created_at, shot_count, ref_thumb }
    ref_thumb is the URL path to the first reference image, or None if none exist.
    """
    if not STORAGE_ROOT.exists():
        return []

    results = []
    for project_dir in STORAGE_ROOT.iterdir():
        if not project_dir.is_dir():
            continue
        meta_file = project_dir / "meta.json"
        if not meta_file.exists():
            continue

        meta = json.loads(meta_file.read_text())
        project_id = meta.get("project_id", project_dir.name)

        shots_dir = project_dir / "shots"
        shot_count = sum(1 for d in shots_dir.iterdir() if d.is_dir()) if shots_dir.exists() else 0

        refs_dir = project_dir / "context" / "refs"
        ref_thumb = None
        if refs_dir.exists():
            first = next((f for f in sorted(refs_dir.iterdir()) if f.is_file()), None)
            if first:
                ref_thumb = f"/projects/{project_id}/refs/{first.name}"

        results.append({
            "project_id":  project_id,
            "character":   meta.get("character", ""),
            "series":      meta.get("series", ""),
            "created_at":  meta.get("created_at", ""),
            "shot_count":  shot_count,
            "ref_thumb":   ref_thumb,
        })

    results.sort(key=lambda p: p["created_at"], reverse=True)
    return results
