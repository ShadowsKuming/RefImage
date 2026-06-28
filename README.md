# RefImage — Cosplay Shooting Planner

**[English](README.md) | [中文](README.zh.md)**

Upload an anime character reference image → AI extracts the visual spec → generate reference shots → export actionable shooting guides.

---

## Quick Start (Docker)

```bash
cp .env.example .env
# Fill in OPENAI_API_KEY and ANTHROPIC_API_KEY

docker compose up --build
```

Open `http://localhost:3001`

---

## Local Development

**Backend**
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**Frontend**
```bash
cd frontend
npm install
npm run dev   # http://localhost:3333
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in:

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | ✓ | Image generation, vision analysis, guide generation |
| `ANTHROPIC_API_KEY` | ✓ | Character chat, planning assistant |
| `LLM_PROVIDER` | | `openai` (default) or `claude` |
| `VISION_PROVIDER` | | `openai` (default) or `claude` |
| `IMAGE_PROVIDER` | | `openai` (default) or `fal` |
| `SKETCH_MODEL` | | Default `gpt-image-2` |
| `FAST_LLM_MODEL` | | Default `claude-haiku-4-5-20251001` |

---

## User Flow

```
1. Upload character reference image
        ↓ AI extracts visual spec (hair / costume / color palette …)
2. Confirm character profile
        ↓ AI searches background, generates character profile
3. Enter project page
        ↓ Chat with AI planning assistant, build shooting brief
4. Create shots, design composition, generate reference images
        ↓ View shooting guides: Action / Expression / Camera / Background
```

---

## Project Structure

```
reference_image_system/
├── backend/
│   ├── agents/         AI logic (chat agents, guide generators)
│   │   └── guides/     Action / Expression / Camera / Background guides
│   ├── tools/          Infrastructure (LLM, vision, image gen, search)
│   ├── services/       Business logic layer
│   ├── api/            HTTP routing layer
│   ├── config.py       Unified model/provider configuration
│   └── storage/        Generated images and project data (gitignored)
├── frontend/
│   └── app/
│       ├── pages/      Route pages
│       ├── components/ UI components (guide panels)
│       └── composables/ API client
├── docker-compose.yml
└── .env.example
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Nuxt 3 / Vue 3 |
| Backend | FastAPI / Python 3.11 |
| Image generation | gpt-image-2 images.edit (multi-reference input) |
| Vision analysis | GPT-4o / Claude Sonnet (switchable) |
| LLM | GPT-4.1 / Claude Haiku (switchable) |
| Search | DuckDuckGo (ddgs) |
| Storage | Local filesystem |
| Deployment | Docker Compose |
