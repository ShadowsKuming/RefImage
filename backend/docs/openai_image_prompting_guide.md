# OpenAI gpt-image-2 Prompting Guide
> 来源：https://developers.openai.com/cookbook/examples/multimodal/image-gen-models-prompting-guide
> 摘录与我们项目相关的部分

---

## 核心原则

1. **结构化顺序**：`background/scene → subject → key details → constraints`
2. **分段写**：用换行 / labeled segments，不要一整段
3. **明确意图**：说明用途（ad / illustration / storyboard）让模型选对 mode
4. **约束要显式**：用 "do not change X"、"preserve Y"、"change only Z"
5. **每次重复不变量**：防止多轮 drift，每次 prompt 都要重申角色固定特征
6. **小步迭代**：不要一次塞太多，先生成干净的基础图，再小改

---

## 角色一致性（Character Consistency）

官方模板——**6.4a 建立角色锚点（Anchor）**：
```
Create a children's book illustration introducing a main character.

Character:
A young, storybook-style hero inspired by a little forest outlaw,
wearing a simple green hooded tunic, soft brown boots, and a small belt
pouch. The character has a kind expression, gentle eyes, and a brave but
warm demeanor. Carries a small wooden bow used only for helping, never
harming.

Theme:
The character protects and rescues small forest animals like squirrels,
birds, and rabbits.

Style:
Children's book illustration, hand-painted watercolor look,
soft outlines, warm earthy colors, whimsical and friendly.
Proportions suitable for picture books (slightly oversized head, expressive
face).

Constraints:
- Original character (no copyrighted characters)
- No text
- No watermarks
- Plain forest background to clearly showcase the character
```

官方模板——**6.4b 故事续集（同角色新场景）**：
```
Continue the children's book story using the same character.

Scene:
The same young forest hero is gently helping a frightened squirrel
out of a fallen tree after a winter storm.
The character kneels beside the squirrel, offering reassurance.

Character Consistency:
- Same green hooded tunic
- Same facial features, proportions, and color palette
- Same gentle, heroic personality

Style:
Children's book watercolor illustration,
soft lighting, snowy forest environment,
warm and comforting mood.

Constraints:
- Do not redesign the character
- No text
- No watermarks
```

---

## 人物编辑（身份保留）

官方示例——**虚拟试衣（换衣不换人）**：
```
Edit the image to dress the woman using the provided clothing images.
Do not change her face, facial features, skin tone, body shape, pose,
or identity in any way.
Preserve her exact likeness, expression, hairstyle, and proportions.
Replace only the clothing, fitting the garments naturally to her existing
pose and body geometry with realistic fabric behavior.
Match lighting, shadows, and color temperature to the original photo so
the outfit integrates photorealistically, without looking pasted on.
Do not change the background, camera angle, framing, or image quality,
and do not add accessories, text, logos, or watermarks.
```

---

## 光线 / 天气编辑

```
Make it look like a winter evening with snowfall.
```
→ 极短也可以，关键是只说"变什么"，其他不提。

---

## 质量参数建议

| quality | 适用场景 |
|---|---|
| `low` | 快速出图、草稿、storyboard 参考图 ✅ 我们现在用这个 |
| `medium` | 人像、有文字的图 |
| `high` | 密集文字、高分辨率输出、身份敏感编辑 |

---

## 关键 Prompt 写法规则

- **保留列表每次都要重复**："Same green hooded tunic, same facial features, proportions, and color palette"
- **排除要显式**："Do not redesign the character"
- **只说变化点**："change only X, keep everything else the same"
- **引用上下文**："same style as before"、"the subject"
- **文字内容加引号或大写**：避免模型自由发挥

---

## 对我们项目的启示

### 当前 generate prompt 的问题
- `shot_chat.py` 工具描述说"不要描述角色外貌"——**与官方指南矛盾**
- 官方明确：每次 prompt 都要重复角色不变特征，否则会 drift

### 最终 prompt 结构（适配 cosplay storyboard）

经过实测验证的七段结构。各段正交——只负责一个维度，互不干涉，不会自相矛盾。

```
[Style]
Anime illustration, [作品画风/渲染介质].

[Character] — do not change
[角色名]. [发色发型发饰]. [眼睛颜色、脸型、肤色]. [上身服装]. [下身服装]. [鞋履]. [配饰/特征].
Do not redesign the character. Preserve her exact hair color, eye color, outfit, and proportions.

[Atmosphere]
Color tone: [色调方向：warm golden / cool blue-grey / high contrast / desaturated].
Mood: [情绪基调：healing / melancholic / tense / romantic / energetic].
Genre feel: [题材感：school life / action / drama / fantasy / slice-of-life].

[Scene]
[地点 + 时间]. [人物与环境的物理关系：站在哪、脚踩什么]. [背景环境元素].

[Pose / Expression]
[身体动作：手臂/腿/头部姿势]. [表情与情绪].

[Composition]
[相机高度]. [镜头类型：close-up / medium shot / full body]. [相机角度]. [画面可见范围].

[Constraints]
- No text, no watermarks
- [其他排除项]
```

### 各段职责划分

| 段 | 控制什么 | 来源 | 变化频率 |
|---|---|---|---|
| Style | 画风/渲染介质 | world.json | Project 级别固定 |
| Character | 角色外貌 | visual_spec.json | 永远不变 |
| Atmosphere | 色调 + 情绪 + 题材感 | 用户/LLM | Shot 级别 |
| Scene | 物理空间和环境 | 用户/LLM | Shot 级别 |
| Pose | 身体动作和表情 | 用户/LLM | Shot 级别 |
| Composition | 相机位置和取景 | LLM | Shot 级别 |
| Constraints | 排除项 | 固定模板 | 永远不变 |

### Atmosphere 三子维度（实测验证）

同一 Scene + Pose + Composition，只换 Atmosphere，色调和题材感完全独立响应：

| 变体 | Atmosphere | 结果 |
|---|---|---|
| A | warm golden · healing · school life | ✅ 暖金夕阳，柔光治愈 |
| B | cool blue-grey · melancholic · drama | ✅ 冷灰天空，去饱和，压抑感 |
| C | high contrast · tense · action | ✅ 深红戏剧天空，高对比紧绷感 |

### Composition 三锚点规则（避免透视矛盾）

每次写 Composition 段必须同时说清楚：

| 锚点 | 说明 | 示例 |
|---|---|---|
| ① 相机高度 | 相机相对角色的垂直位置 | `Camera at eye level with her face` |
| ② 人物站位 | 角色的脚/身体接触什么 | `feet planted on the rooftop floor` |
| ③ 道具高度关系 | 关键道具在角色身体的哪个位置 | `railing at waist height` |

只写其中一两个会让模型自由发挥，产生不合理透视。

### Character 段写法原则（重要）

`images.edit` 已经传入了参考图，文字和图片两个信号会**互相竞争**。服装描述越详细，模型越容易按文字重新诠释，反而偏离参考图。

**正确做法：只描述最容易 drift 的特征（发色、眼睛、配饰），服装用一句锁定语交给参考图**

```
Character — do not change:
[角色名]. [发色+发型+发饰]. [眼睛颜色、脸型、肤色].
Preserve her exact outfit, colors, and accessories exactly as shown in the reference image.
Do not redesign or reinterpret the costume.
```

| 方式 | 效果 |
|---|---|
| ❌ 详细描述服装文字 | 模型按文字重新画，偏离参考图 |
| ✅ 只描述发色/眼睛 + 锁定语 | 模型直接从参考图取服装，高度还原 |

### 踩坑记录

- ❌ `slightly low angle` + `leaning against railing`（Pose/Composition 混写）→ 透视矛盾
- ❌ Style 段混入 Atmosphere 信息 → 色调控制不稳定
- ❌ Character 段详细描述服装 → 文字与参考图竞争，服装反而跑偏
- ✅ 七段各司其职，服装锁定参考图 → 角色高度还原

### LLM 应该输出什么

- `[Style]` `[Character]` `[Constraints]`：自动填充，LLM 不碰
- `[Atmosphere]` `[Scene]` `[Pose]` `[Composition]`：LLM 根据对话生成，其中 Composition 必须遵守三锚点规则
