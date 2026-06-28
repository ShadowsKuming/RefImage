# RefImage — Cosplay Shooting Planner / 角色扮演拍摄策划系统

> Upload an anime character reference image → AI extracts the visual spec → generate reference shots → export actionable shooting guides.
>
> 上传动漫角色参考图，AI 自动提取外貌设定、生成拍摄参考例图、输出可操作的拍摄指南。

---

## Quick Start (Docker) / 快速启动（Docker）

```bash
cp .env.example .env
# Fill in OPENAI_API_KEY and ANTHROPIC_API_KEY
# 填入 OPENAI_API_KEY 和 ANTHROPIC_API_KEY

docker compose up --build
```

Open / 打开 `http://localhost:3001`

---

## Local Development / 本地开发

**Backend / 后端**
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**Frontend / 前端**
```bash
cd frontend
npm install
npm run dev   # http://localhost:3333
```

---

## Environment Variables / 环境变量

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

## User Flow / 用户流程

```
1. Upload character reference image
   上传角色参考图
        ↓ AI extracts visual spec (hair / costume / color palette …)
          AI 提取外貌特征（发型/服装/配色等）
2. Confirm character profile
   确认角色设定
        ↓ AI searches background, generates character profile
          AI 搜索角色背景，生成人设档案
3. Enter project page
   进入项目页
        ↓ Chat with AI planning assistant, build shooting brief
          与 AI 规划助手讨论，生成拍摄总结
4. Create shots, chat to design composition, generate reference images
   创建单个 shot，对话设计构图，生成参考例图
        ↓ View shooting guides: Action / Expression / Camera / Background
          查看拍摄指南：动作 / 表情 / 构图 / 背景
```

---

## Project Structure / 项目结构

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

## Tech Stack / 技术栈

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
