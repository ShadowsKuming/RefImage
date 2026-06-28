# RefImage — 系统架构 & AI Pipeline

---

## 整体架构

```
frontend (Nuxt 3)
    │  HTTP / REST
    ▼
backend (FastAPI)
    ├── api/          路由层
    ├── services/     业务编排
    └── tools/        AI 原子能力
            ├── llm.py              Claude / OpenAI / Gemini（可切换）
            ├── vision.py           视觉 LLM（Claude / GPT-4o）
            ├── image_gen.py        gpt-image-2 图像生成
            ├── search.py           Serper Google 搜索
            ├── character_extractor.py   外貌特征提取
            ├── character_chat.py        角色档案对话 agent
            ├── shot_chat.py             拍摄策划对话 agent
            └── planning_chat.py         全局拍摄规划 agent
```

---

## 数据流

### Step 1 — 图像分析（新建项目）

```
用户上传参考图（可多张）
    ↓ character_extractor.extract_features()
      Vision LLM 提取 8 个外貌字段：
      发型 / 妆容 / 上身 / 下身 / 鞋子 / 体型 / 特征 / 配色
    ↓ analyze_service（session 管理，多图累积填充 missing_fields）
    ↓ translate.py 将英文字段翻译为中文 + 日文
    → 存入 context/visual_spec.json（含 zh / en / ja / prompt）
```

### Step 2 — 角色档案（新建项目）

```
用户与 AI 对话确认角色名、作品名
    ↓ character_chat agent（tools: web_search + update_profile）
      Serper 搜索角色背景、世界观、经典场景
    → 存入 context/character.json、context/world.json
```

### Step 3 — Shot 策划（项目内）

```
用户创建 shot，与 AI 对话设计拍摄方案
    ↓ shot_chat agent（tools: web_search + generate_image）
      系统提示注入：角色性格 / 标志性瞬间 / 经典场景 / 外貌特征
      对话风格：创意导演，主动提案，用户确认后才生成
    ↓ 用户确认 → AI 调用 generate_image 工具
    ↓ generate_service（BackgroundTask）
      拼装 prompt：style + character + atmosphere + scene + pose + composition
      调用 gpt-image-2 images.edit（传入所有参考图）
    → 存入 shots/{shot_id}/generated.png
```

### Step 4 — 拍摄指南（Shot 内）

```
用户点击图上标注点（发型 / 表情 / 动作 / 布光 / 背景）
    ↓ guide_service.get_or_generate()
    ↓ planning_chat agent（tools: web_search + update_brief）
      针对具体部位生成可操作拍摄建议
    → 存入 shots/{shot_id}/guides/{guide_type}.json
```

---

## 存储结构

```
storage/projects/{project_id}/
    meta.json                   项目基本信息
    context/
        refs/                   原始参考图
        extra_refs/             补充参考图（用户后续上传）
        visual_spec.json        外貌规格 { zh, en, ja, prompt }
        world.json              世界观设定
        character.json          角色档案
    plan/
        brief.json              全局拍摄简报
        chat_history.json       AI 规划助手对话历史
    shots/{shot_id}/
        shot.json               标题、氛围、状态、image_url
        chat_history.json       该 shot 的对话历史
        generated.png           生成的参考例图
        guides/
            hair.json
            expression.json
            action.json
            lighting.json
            background.json
```

---

## Shot 状态流转

```
pending → generating → done → refined
                    ↘ error
```

- `pending`   — 刚创建，未生成图
- `generating` — 后台任务运行中（BackgroundTask）
- `done`      — 图已生成，可继续对话
- `refined`   — 用户手动标记完善，聊天锁定
- `error`     — 生成失败（moderation / 网络等），AI 自动分析原因追加到对话历史

---

## 图像生成参数

gpt-image-2 `images.edit`，支持多参考图输入：

| orientation | 尺寸 | 用途 |
|---|---|---|
| square | 1024×1024 | 通用 |
| portrait | 1024×1536 | 全身 / 角色特写 |
| landscape | 1536×1024 | 场景横图 |
| landscape_wide | 1536×864 | 电影宽画面 |

> 注：864×1536（9:16 竖图）在动漫角色+短裙组合下稳定触发安全审核，已排除。
