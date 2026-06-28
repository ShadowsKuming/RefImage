"""
config.py — Global model and provider configuration

All switchable AI interfaces are declared here.
To swap a provider or model, change this file or set the corresponding env var.

API keys stay in .env (sensitive).
Provider/model choices are defaulted here (non-sensitive, version-controlled).
"""
import os
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../.env"))

# ── Text LLM ──────────────────────────────────────────────────────────────────
# Used by: planning chat, shot chat, character chat, translate
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
LLM_MODEL = {
    "openai": os.getenv("LLM_MODEL_OPENAI", "gpt-4.1"),
    "claude": os.getenv("LLM_MODEL_CLAUDE", "claude-haiku-4-5-20251001"),
    "gemini": os.getenv("LLM_MODEL_GEMINI", "gemini-2.0-flash"),
}

# ── Vision LLM ────────────────────────────────────────────────────────────────
# Used by: character extractor, action/background/expression/camera guides
VISION_PROVIDER = os.getenv("VISION_PROVIDER", "openai")
VISION_MODEL = {
    "openai": os.getenv("VISION_MODEL_OPENAI", "gpt-4o"),
    "claude": os.getenv("VISION_MODEL_CLAUDE", "claude-sonnet-4-6"),
}

# ── Image Generation ──────────────────────────────────────────────────────────
# Used by: shot reference image generation
IMAGE_GEN_PROVIDER = os.getenv("IMAGE_PROVIDER", "openai")
IMAGE_GEN_MODEL = {
    "openai": os.getenv("IMAGE_GEN_MODEL_OPENAI", "gpt-image-2"),
    "fal":    os.getenv("IMAGE_GEN_MODEL_FAL",    "fal-ai/flux/dev"),
}

# ── Sketch Generation ─────────────────────────────────────────────────────────
# Used by: action guide pose sketch (images.edit)
# Replace with a fine-tuned sketch model when available
SKETCH_MODEL = os.getenv("SKETCH_MODEL", "gpt-image-2")

# ── Lightweight LLM ───────────────────────────────────────────────────────────
# Used by: fast/cheap tasks (project metadata generation, simple completions)
FAST_LLM_MODEL = os.getenv("FAST_LLM_MODEL", "claude-haiku-4-5-20251001")
