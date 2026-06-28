# RefImage — Cosplay 拍摄策划系统

上传角色参考图，AI 自动提取外貌设定、生成拍摄参考例图、输出可操作的拍摄指南。

---

## 快速启动（Docker）

```bash
cp .env.example .env
# 填入 OPENAI_API_KEY 和 ANTHROPIC_API_KEY
docker compose up --build
```

打开 `http://localhost:3000`

---

## 本地开发

**后端**
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**前端**
```bash
cd frontend
npm install
npm run dev   # http://localhost:3333
```

---

## 环境变量

复制 `.env.example` 为 `.env` 并填写：

| 变量 | 必填 | 说明 |
|------|------|------|
| `OPENAI_API_KEY` | ✓ | 图像生成、视觉分析、guide 生成 |
| `ANTHROPIC_API_KEY` | ✓ | 角色对话、规划助手 |
| `LLM_PROVIDER` | | `openai`（默认）或 `claude` |
| `VISION_PROVIDER` | | `openai`（默认）或 `claude` |
| `IMAGE_PROVIDER` | | `openai`（默认）或 `fal` |
| `SKETCH_MODEL` | | 默认 `gpt-image-2` |
| `FAST_LLM_MODEL` | | 默认 `claude-haiku-4-5-20251001` |

---

## 项目结构

```
reference_image_system/
├── backend/
│   ├── agents/         AI 逻辑（对话 agents、guide 生成器）
│   │   └── guides/     动作/表情/构图/背景 guide
│   ├── tools/          基础设施（LLM、视觉、图像生成、搜索）
│   ├── services/       业务逻辑层
│   ├── api/            HTTP 路由层
│   ├── config.py       模型/provider 统一配置
│   └── storage/        生成图片和项目数据（gitignored）
├── frontend/
│   └── app/
│       ├── pages/      路由页面
│       ├── components/ UI 组件（含各类 guide 面板）
│       └── composables/ API client
├── docker-compose.yml
└── .env.example
```

---

## 用户流程

```
1. 上传角色参考图
        ↓ AI 提取外貌特征（发型/服装/配色等 8 个字段）
2. 确认角色设定
        ↓ AI 搜索角色背景、世界观，生成人设档案
3. 进入项目页
        ↓ 与 AI 规划助手讨论拍摄计划，生成拍摄总结
4. 创建单个 shot，与 AI 对话设计构图，生成参考例图
        ↓ 查看拍摄指南：动作 / 表情 / 构图 / 背景
5. 标记完善，导出计划
```

---

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Nuxt 3 / Vue 3 |
| 后端 | FastAPI / Python 3.11 |
| 图像生成 | gpt-image-2 images.edit（多参考图输入）|
| 视觉分析 | GPT-4o / Claude Sonnet（可切换）|
| LLM | GPT-4.1 / Claude Haiku（可切换）|
| 搜索 | DuckDuckGo（ddgs）|
| 存储 | 本地文件系统 |
