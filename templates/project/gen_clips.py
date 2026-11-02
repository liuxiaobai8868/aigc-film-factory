#!/usr/bin/env python3
"""《{{片名}}》镜头数据：一处定义，同时导出白模规格（预演规格/第N条.json）和镜头规格单（交付/规格单/第N条.json）。

单位：米。识别色：黄 = 主角，蓝 = 第二主角，灰 = 其他人。
写法规则（docs/14、docs/18 第三节）：
- 每镜 body 以"画面里：……。"开头，写清画面里有谁；台词放在 {花括号} 里，说话人要在画里，或写明画外 / 背对镜头 / 过肩。
- 画面写到路人，就把本世界的群像加进 tags，并按群演编号点名（docs/17）。
- 对白镜头最多一个小动作，写在第几秒；手部特写写清是谁的手、袖口什么样。
- 过肩用 ots()，瘦小的前景人物用 back≈0.9、lat≈0.28。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "..", "..", "tools"))
import build_assets as A  # noqa: E402
from projectkit import add, b, bo, person, head, cam  # noqa: E402,F401
import projectkit as K  # noqa: E402

YEL, GRY = [0.95, 0.8, 0.15], [0.6, 0.6, 0.6]
WOOD, WHITE, FLOOR = [0.35, 0.25, 0.18], [0.92, 0.92, 0.9], [0.5, 0.5, 0.52]
H = {"阿青": 1.62}

THREE = "世界锁：只有一个世界，深夜的便利店，安静、冷暖对冲。"
STYLE = "质感：近真人实拍的电影写实（风格配方 R05、R04，docs/16）：暖黄台灯照在人身上，背景冷白灯管；暗部过渡平滑，画面干净。"
MUSIC = "配乐：没有配乐，只有冰柜的嗡嗡声和门外的雨声。"
VOICE = {"阿青": "阿青：声音轻，有点哑，语速慢。"}
LIP = "对白：普通话，自然口语。所有角色只说花括号里的台词；只有说话的人动嘴；画面全程是纯影像，没有字幕。"
ANCHOR = "人物都是正常的人体结构：两只手各五根手指。"


def world():
    return [b("Floor", [-5, -5, -0.1], [5, 5, 0], FLOOR), b("Counter", [-3, 1, 0], [-1.5, 2.2, 1.0], WOOD),
            b("Lamp", [-2.6, 1.4, 1.0], [-2.4, 1.6, 1.4], [1.0, 0.8, 0.4])] + \
           [b(f"Shelf{k}", [0.5, -2 + k * 1.6, 0], [3.5, -1.6 + k * 1.6, 1.8], WHITE) for k in range(3)]


AQ = (-2.25, 0.4, 0)  # 阿青站在收银台后


def clip1():
    people = [person("阿青", YEL, H["阿青"], [(0, AQ, 0, 0), (8, AQ, 0, 0)])]
    shots = [
        dict(t0=0, t1=4, name="空店", lens=35, cam=cam(0, 35, (2.5, -4.5, 1.6), head(AQ, H["阿青"])),
             body="画面里：深夜空荡的便利店、站在收银台后的阿青。63°，固定；冷白灯管下的货架，收银台上一盏暖黄台灯照着她；<冰柜嗡嗡声，门外的雨声>。"),
        dict(t0=4, t1=8, name="看表", lens=50, cam=cam(4, 50, (-2.25, -1.4, 1.5), head(AQ, H["阿青"])),
             body="画面里：阿青。47°，固定近景；第 1 秒她抬起左手看了一眼旧电子表，轻声说：{又是三点。}"),
    ]
    return dict(n="1", dur=8, title="三点", summary="深夜便利店，阿青看表", model="Seedance 2.5 + 白模",
                tags=["@阿青", "@loc_便利店"], count="画面中始终只有 1 个人：阿青。", context="阿青在便利店值夜班。",
                extra_chars=[], voices=["阿青"], sfx="<冰柜嗡嗡声> <门外的雨声>",
                constraint="店里只有阿青一个人；收银台在门的左手边。", axis=None, people=people, shots=shots,
                fail="店里出现第二个人；阿青的电子表戴到右手。", risk="—", splice="出口：阿青放下手。")


CLIPS = [clip1]


def export():
    texts = dict(THREE=THREE, STYLE=STYLE, MUSIC=MUSIC, VOICE=VOICE, LIP=LIP, ANCHOR=ANCHOR)
    K.export(ROOT, "{{片名}}", "{{短名}}", A.ITEMS, world(), [f() for f in CLIPS], texts, "黄色圆柱=阿青，灰白方块=货架和收银台")


if __name__ == "__main__":
    export()
