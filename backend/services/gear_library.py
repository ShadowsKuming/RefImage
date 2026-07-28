"""
services/gear_library.py — Cosplay shoot gear knowledge base

This is the AI's REFERENCE dictionary, not a checklist shown wholesale to the
user. When extracting a shot's plan, the AI picks only a FEW clearly-triggered
items per shot (minimal principle — don't overwhelm; the user can always add
their own). Curated from real cosplay-photography practice, so the AI maps shot
features → items instead of hallucinating gear.

Structure:
  PER_SHOT   — suggested per shot, gated by `when` triggers. AI picks a few.
  BASELINE   — standing kit brought to ANY shoot; belongs at the PROJECT level
               (checked once), never itemized per shot.
  HARDWARE   — shared grip/rigging referenced by several PER_SHOT categories.
  RESTRICTED — permit / fire / safety-sensitive; never suggested by default,
               only surfaced with an explicit caution.
"""

# Shared grip & rigging — hang / brace / weigh-down. Referenced by dynamics,
# pose_support, environment. Heavy suspension needs pro rigging + safety check.
HARDWARE = [
    "沙袋 / 配重袋", "C-stand / 魔术腿 / 夹臂", "晾衣杆 / 伸缩杆 / 旗杆",
    "透明亚克力杆 / 支架", "弹力线 / 细钢丝（比钓鱼线承重大）",
]

# Per-shot categories — AI suggests a few items only when the trigger matches.
PER_SHOT = {
    "dynamics": {
        "label": "动态与悬浮",
        "when": "裙摆 / 披风 / 头发飘动、跳跃、旋转等动态效果",
        "items": [
            "透明线 / 钓鱼线", "风扇 / 鼓风机", "手持吹气吹尘器（近距离精确）",
            "威亚（需专业固定 + 安全检查）", "落叶 / 纸片 / 花瓣机", "转盘 / 旋转台",
        ],
    },
    "pose_support": {
        "label": "姿势与身体支撑",
        "when": "难维持的姿势：悬空 / 半蹲 / 后仰 / 单脚 / 跪趴 / 补身高",
        "items": [
            "苹果箱 / 摄影箱", "脚踏 / 踏台 / 木板（补高）",
            "折叠凳 / 隐藏坐箱 / 透明亚克力椅", "软垫 / 瑜伽垫 / 护膝",
            "靠垫 / 腰垫 / 楔形垫", "把杆 / 隐藏扶手", "医疗胶带 / 肌贴", "防滑垫 / 防滑胶带",
        ],
    },
    "environment": {
        "label": "环境效果",
        "when": "雨 / 雪 / 雾 / 花瓣 / 地面倒影 / 特定光影纹理",
        "items": [
            "喷壶 / 细雾瓶", "雨机 / 打孔水管", "水雾机 / 雾化器（比浓烟柔）",
            "泡泡机", "雪花机 / 安全人造雪", "反光水盘 / 黑亚克力板（倒影）",
            "棱镜 / CD / 反光膜（折射炫光）", "黑旗 / 黑白布 / 银色保温毯（控光遮挡）",
            "窗框 / 纱帘 / 百叶（光影纹理）", "投影仪 / 图案灯片（投窗影 / 水波 / 树林）",
            "布景：旧报纸 / 碎石 / 泡沫砖 / 假植物", "雨后：刮水器 / 吸水拖布 / 防水布",
        ],
    },
    "lens_fx": {
        "label": "镜头前效果",
        "when": "柔焦 / 朦胧 / 前景遮挡 / 多重人物 / 面部局部光",
        "items": [
            "柔焦 / 黑柔滤镜", "星光 / 棱镜 / 分像镜", "塑料膜 / 彩色薄膜",
            "丝袜 / 薄纱（柔化）", "镜头前水滴板", "小镜 / 碎镜面替代（局部反射 / 多重）",
            "铜管 / 透明管 / 金属环（隧道感）", "树叶 / 花束（前景遮挡）",
            "手机屏 / 小显示器（面部局部色光）",
        ],
    },
}

# Project-level standing kit — brought to any shoot, checked once, NOT per shot.
BASELINE = {
    "styling": {
        "label": "造型维护包",
        "items": [
            "时装胶 / 身体胶", "安全裤 / 打底 / 胸贴", "隐形肩带 / 透明松紧带",
            "磁扣 / 魔术贴 / 暗扣（快拆）", "扎带 / 铁丝 / 铝丝（塑形）", "泡棉 / 填充棉",
            "别针 / 夹子 / 双面胶", "静电喷雾 / 除皱喷雾 / 挂烫机", "粘毛滚 / 除尘刷",
            "针线包 / 热熔胶 / 强力胶（注意材质与皮肤安全）",
            "假发：定型喷雾 / 发网 / U形夹 / 假发支架 / 备用发片", "鞋：防磨贴 / 后跟贴 / 鞋底胶",
        ],
    },
    "safety": {
        "label": "现场保障",
        "items": [
            "急救包", "灭火毯 / 合规灭火器", "防水布 / 设备雨罩", "警示胶带 / 反光锥",
            "延长线保护槽 / 理线胶带", "工作手套 / 护膝护腕", "暖宝宝 / 保温毯",
            "饮水 / 纸巾 / 吸油纸", "备用电池 / 充电宝", "对讲机", "垃圾袋 / 清洁",
            "防晒防虫", "临时更衣帐篷 / 遮挡布",
        ],
    },
}

# Permit / fire / safety-sensitive — never default; surface only with a caution.
RESTRICTED = [
    "烟饼 / 明火 / 爆闪粉尘（涉场地许可、消防、呼吸安全）",
    "真碎玻璃（一律用亚克力 / 安全替代）",
    "大量颗粒物 / 人造雪超量使用（清理与呼吸安全）",
]
