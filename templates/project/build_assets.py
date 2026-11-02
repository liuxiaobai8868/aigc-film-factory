#!/usr/bin/env python3
"""《{{片名}}》资产数据：描述锁在这里定义一次，镜头规格单逐字引用。只写数据，文档由 tools/projectkit.py 生成。

改完跑：python3 tools/pipeline.py run projects/{{片名}}
字段说明见 tools/projectkit.py 顶部和 docs/18 第三节。下面是一个最小可跑的例子，照着替换成本片内容。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "..", "..", "tools"))
import projectkit as K  # noqa: E402

# 1. 风格：每个"世界"选一个配方（docs/16，config/style_recipes.json），人物与道具单独一个
STYLE = K.recipes({"室内": "R05", "人物": "R04"})
FILM = "near-live-action cinematic short film"
STYLE_NOTE = "室内 R05 暖琥珀冷暖对冲；人物与道具 R04 冷调作者电影人像"

# 2. 描述锁（中文，逐字进规格单）
LOCK = {
    "阿青": "阿青：二十出头的年轻女人，瘦，齐肩黑发别在耳后；穿洗旧的深蓝色工装外套和黑色长裤，白色帆布鞋；左手腕戴一块旧电子表。",
}
GEO = {
    "便利店": "便利店：深夜的小便利店，收银台在门左手边，台上一盏暖黄色的小台灯；货架三排，冷白色灯管；玻璃门外是下雨的街。",
}

# 3. 出图清单（顺序就是出图顺序；deps 写要先出好的图的序号）
ITEMS = [
    dict(tag="@阿青", world="人物", file="阿青_三视图.png", type="人物三视图", rec="Image 2.5（APIMart 2K）", deps="—", use="第 1 条",
         lock=LOCK["阿青"], en=f"Create a character reference sheet for a {FILM}: a tired young night-shift clerk.",
         must="MUST BE READABLE: worn dark-blue work jacket, white canvas shoes, an old digital watch on the left wrist. "
              "Age and face: clearly an adult in her early twenties. PORTRAIT: calm, tired eyes, mouth closed.",
         check=["二十出头的成年人", "深蓝工装、白帆布鞋、左手电子表", "正面全身像的脸模糊成椭圆"],
         duty="「阿青」：脸只从右侧大头像取；体型和服装从左侧全身像取；正面全身像的模糊椭圆不是脸；不继承灰底和三视图版式。"),
    dict(tag="@loc_便利店", world="室内", file="场景_便利店.png", type="场景主图", rec="Image 2.5（APIMart 2K）", deps="—", use="第 1 条",
         lock=GEO["便利店"], en=f"A location reference image for a {FILM}, no characters: a small convenience store late at night.",
         must="The cashier counter to the left of the glass door with one small warm desk lamp; three aisles under cold white tubes; "
              "rain on the street outside the glass door. The scene is completely uninhabited. Full-frame image. No readable text or signs.",
         check=["收银台在门左边", "暖黄台灯 + 冷白灯管", "没有人、没有字"],
         duty="「便利店」：只取空间结构、收银台位置、灯光与材质；不作首帧，不继承构图。"),
]


def main():
    n = K.write_asset_doc(ROOT, "{{片名}}", ITEMS, STYLE, STYLE_NOTE, "出图顺序：人物三视图 → 道具 → 场景 → 群像。")
    print(n, "张")


if __name__ == "__main__":
    main()
