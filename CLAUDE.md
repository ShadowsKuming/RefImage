# RefImage — CLAUDE.md

AnimeCosplay 拍摄策划系统。上传角色参考图 → AI 提取外貌 → 生成参考例图 → 输出拍摄指南（动作/表情/构图/背景）。

## 快速启动

**本地开发**
```bash
# 后端（conda env: refimg）
cd backend && conda run -n refimg uvicorn main:app --reload --port 8000

# 前端
cd frontend && npm run dev   # http://localhost:3333
```

**Docker**
```bash
docker compose up --build   # 前端 :3001，后端 :8000
```

## 项目结构

```
backend/
  config.py          ← 全局 AI provider/model 配置（改这里切换模型）
  main.py            ← FastAPI 入口，CORS 从 ALLOWED_ORIGINS env 读
  api/               ← HTTP 路由（home, new_project, project, shot）
  services/          ← 业务逻辑层
  agents/            ← AI 逻辑
    planning_chat.py ← 项目规划助手（读所有 shot + guide 数据作 context）
    shot_chat.py     ← 单 shot 对话
    character_chat.py
    character_extractor.py
    guides/          ← 4 种 guide 生成器
      action.py      ← gpt-image-2 sketch + 动作描述
      expression.py  ← 表情 emoji + 导演 cue
      background.py  ← 取景地推荐
      camera.py      ← 构图/镜头/人物/视觉因素 JSON
  tools/             ← 基础设施（不含 AI 逻辑）
    llm.py           ← provider-agnostic 文本 LLM
    vision.py        ← provider-agnostic 视觉分析
    image_gen.py     ← 图像生成
    search.py        ← DuckDuckGo 搜索
    translate.py

frontend/app/
  pages/
    index.vue                        ← 首页项目列表
    projects/new.vue                 ← 新建项目向导
    projects/[id]/index.vue          ← 项目页（shots 网格 + 规划助手）
    projects/[id]/shots/[shotId].vue ← 单 shot 页（画布 + 4 个 hotspot + guide 面板）
  components/guides/
    ActionGuide.vue / ExpressionGuide.vue / CameraGuide.vue / BackgroundGuide.vue
  composables/
    useApi.ts   ← 所有 API 调用，BASE 从 runtimeConfig 读
    useTheme.ts ← 暗/亮主题
```

## 存储结构

```
backend/storage/projects/{project_id}/
  project.json
  character/reference.{ext}
  character/visual_spec.md      ← 视觉提取结果
  character/profile.md          ← 角色人设
  shots/{shot_id}/
    shot.json
    generated.png               ← 保存新图时同时删除 guides/camera.json（缓存失效）
    guides/
      action.json + action_sketch.png
      expression.json
      background.json
      camera.json
```

## AI Provider 规则

**不要悄悄换 provider。** 当前默认全部走 OpenAI，除非 `.env` 里显式覆盖。

- `LLM_PROVIDER=openai` → `gpt-4.1`（对话、规划）
- `VISION_PROVIDER=openai` → `gpt-4o`（视觉分析、guide 生成）
- `IMAGE_GEN_PROVIDER=openai` → `gpt-image-2`（shot 图片生成）
- `SKETCH_MODEL=gpt-image-2`（action guide 草图）
- `FAST_LLM_MODEL=claude-haiku-4-5-20251001`（轻量任务）

切换模型：改 `backend/config.py` 或在 `.env` 里设对应变量。`tools/llm.py` 和 `tools/vision.py` 均支持 `openai` / `claude`，`image_gen.py` 支持 `openai` / `fal`。

## 关键约定

- **前端 SSR 全关**：所有页面都有 `definePageMeta({ ssr: false })`
- **组件自动导入**：`nuxt.config.ts` 设了 `pathPrefix: false`，`guides/` 下的组件直接用 `<ActionGuide>` 而不是 `<GuidesActionGuide>`
- **vision.py 格式**：以 Anthropic 消息格式为 canonical，`_to_openai_messages()` 内部转换
- **Camera guide 缓存**：用户保存新的 crop 图时自动删除 `camera.json`，下次访问重新生成
- **CORS**：Docker 部署时通过 `ALLOWED_ORIGINS` env 控制，逗号分隔多个 origin

## 图像生成选型记录

`gpt-image-2 images.edit` 是目前唯一同时满足**动漫画风质量**和**角色一致性**的方案（~36s，quality=low）。FAL 的 Z-Image Turbo 动漫质量好但角色会漂移；FLUX Kontext 偏写实模糊。详见 memory/image_generation_findings.md。

Prompt 注意：避免 `low angle`、`jumping`、`dynamic pose` 等词，会触发 moderation。

## 待办

- [ ] Task #1：pose sketch 换专用模型（ControlNet / DWPose）替代 gpt-image-2 sketch
