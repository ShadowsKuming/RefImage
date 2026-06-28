# Pose Sketch Generation — Prompting Guide

> 用于 Action Guide 功能：将生成的 cos 例图转换为 mannequin 姿势素描，供 coser 参考摆姿势。

---

## 核心思路

**不是"重新画一张图"，是"提取 Pose Information"。**

输入：cos 角色参考图（有服装、背景、颜色）
输出：白底 mannequin 素描，只保留姿势信息

两个关键转变：
1. 用途从"插画"变成"cosplay 姿势指导"——告诉模型目的，会改变它的生成先验
2. 不说"去掉什么"，而说"替换成什么"——积极指令比否定指令稳定

---

## 最终 Prompt（实测稳定，三次输出一致）

```
Task:
Convert the reference illustration into a cosplay pose guide.
The output should function as a human pose reference for a cosplayer, not as an illustration.
The sketch should clearly communicate balance, center of gravity, limb orientation, and weight distribution.

Subject:
Replace the human body with a neutral artist mannequin.
Represent the body using simple cylinders, spheres, and joint markers. No muscles, no anatomy, no clothing folds.
Blank mannequin head. No hair, no facial features.
Match the original pose as precisely as possible.

Constraints:
- Preserve camera viewpoint and perspective exactly
- Keep the original framing. If legs or feet are cropped, expand the canvas downward only — do not recompose or change camera position or distance
- Full body from head to feet must be visible
- White background only
- Black outlines only
- No background elements
- No text, no watermarks
```

---

## API 调用方式

```python
result = client.images.edit(
    model="gpt-image-2",
    image=[("input.png", img_bytes, "image/png")],  # RGBA PNG
    prompt=PROMPT,
    size="1024x1024",
    quality="low",
)
```

输入图必须是 **RGBA PNG**，用 Pillow 转换：
```python
img = Image.open(path).convert("RGBA")
buf = io.BytesIO()
img.save(buf, format="PNG")
img_bytes = buf.getvalue()
```

---

## 各段设计原则

| 段 | 目的 | 关键决策 |
|---|---|---|
| Task | 改变模型的生成先验 | 明确说"pose reference for cosplayer"而不是"sketch" |
| Subject — Body | 指定几何形式 | "cylinders, spheres, joint markers"，具体几何比"mannequin"更稳定 |
| Subject — Hair | 保留角色辨识度 | 只保留轮廓，明确说"silhouette cue"让模型知道用途 |
| Subject — Head | 防止画出面部 | "Blank mannequin head"比"no face details"更彻底 |
| Subject — Pose | 积极指令 | "Match the original pose as precisely as possible"而不是"do not change" |
| Constraints | 视角和全身 | 相机视角和构图必须显式保留，否则模型会自由重构 |

---

## 踩坑记录

### ❌ 不能直接用 images.edit() 做"线稿转换"
```
# 这样会被审核拦截（moderation_stage: output, sexual）
prompt = "Convert this into a sketch. Black lines, white background."
```
原因：输入图有敏感服装 → 模型还原全身时触发输出审核。

### ✅ 用 mannequin 替换 + 目的声明可以绕过
mannequin 几何体 + "pose reference not illustration" 的组合让模型生成非敏感内容，通过审核。

---

### ❌ "Preserve pose" ≠ 保留相机视角
```
# 模型可能换个角度重画"同一个姿势"
Preserve exactly: body pose, stance, limb angles
```
同一个姿势可以从正面/侧面/45°画——必须显式锁定视角。

### ✅ 单独声明相机视角
```
Constraints:
- Preserve camera viewpoint and perspective exactly
```

---

### ❌ "全身" + "保持构图" 写在一起会冲突
```
# 模型理解成"重新构图以容纳全身"
Redraw as full-body... Extend the frame downward if needed
```

### ✅ 把"扩展画布"和"不改构图"分开说
```
Keep the original framing. If legs or feet are cropped,
expand the canvas downward only —
do not recompose or change camera position or distance.
```

---

### ❌ 否定指令容易失效
```
Do not show body curves.   # AI 还是会画
No face details.           # 还是会画眼睛
```

### ✅ 说替换成什么，而不是禁止什么
```
Replace the human body with a neutral artist mannequin.
Blank mannequin head.
```

---

## 输出稳定性

实测同 prompt 连续生成 3 次：
- 姿势一致 ✓
- 视角一致 ✓  
- 全身可见 ✓
- 审核通过 ✓
- 风格一致（mannequin + 头发轮廓）✓

`quality="low"` 足够，速度快，cos 参考用途不需要高质量。
