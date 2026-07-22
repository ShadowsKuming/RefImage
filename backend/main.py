"""
main.py — FastAPI application entry point

Routers:
  /new-project/*   Step 1 (image analysis) + Step 2 (profile chat)
  /projects/*      Project persistence and retrieval
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import auth, home, new_project, project, shot

app = FastAPI(title="RefPlan API", version="0.4.0")

_origins_env = os.getenv("ALLOWED_ORIGINS", "http://localhost:3333,http://localhost:3000")
_origins = [o.strip() for o in _origins_env.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,        prefix="/auth",        tags=["auth"])
app.include_router(home.router,        prefix="/home",        tags=["home"])
app.include_router(new_project.router, prefix="/new-project", tags=["new-project"])
app.include_router(project.router,     prefix="/projects",    tags=["projects"])
app.include_router(shot.router,        prefix="/projects",    tags=["shots"])


@app.get("/health")
def health():
    return {"status": "ok"}
