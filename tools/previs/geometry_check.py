#!/usr/bin/env python3
"""零抽卡闸门 · 白模几何检查：在 Blender 里搭出白模场景，按镜头规格单逐镜检查构图（docs/14 第四节）。

用法（不用开 Blender 界面）：
  python3 tools/previs/geometry_check.py <白模规格.json> <镜头规格单.json> [--out 报告.md]

每镜在 25%、50%、75% 三个时刻取样，检查：
  入画   "画面里"写到的主体（白模里同名的人物）头部在不在画面里
  大小   主体从头到脚占画高多少；< 6% 判"太小，模型会画成小点"
  遮挡   从镜头到主体头部的视线被什么挡住；写了"虚化 / 背影 / 肩膀"的前景人物是有意遮挡，只记录
  头后   主体头部正后方有没有塔、针、柱子这类竖直物体（会和人融成一体，第一版的老问题）
  穿墙   镜头位置是不是落在墙、道具的方块里面
  轴线   规格单写了 "axis": {"a": 人物, "b": 人物} 时，记录每镜机位在轴线哪一侧，两侧都出现就提醒越轴
退出码 0 = 无 FAIL。
"""
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

if "bpy" not in sys.modules and not os.environ.get("_GEOMETRY_IN_BLENDER"):
    sys.path.insert(0, HERE)
    from render_previs import blender_bin  # noqa: E402
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("previs")
    ap.add_argument("shotspec")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    out = a.out or os.path.splitext(a.shotspec)[0] + "_几何检查.md"
    env = dict(os.environ, _GEOMETRY_IN_BLENDER="1")
    r = subprocess.run([blender_bin(), "-b", "--factory-startup", "-P", os.path.abspath(__file__), "--",
                        os.path.abspath(a.previs), os.path.abspath(a.shotspec), os.path.abspath(out)], env=env,
                       capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(out):
        sys.exit("Blender 运行失败：\n" + (r.stderr[-2000:] or r.stdout[-2000:]))
    txt = open(out, encoding="utf-8").read()
    print(txt)
    sys.exit(1 if "| FAIL" in txt else 0)

# ---------------- 以下在 Blender 里运行 ----------------
import runpy  # noqa: E402

import bpy  # noqa: E402
from bpy_extras.object_utils import world_to_camera_view  # noqa: E402
from mathutils import Vector  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:]
PREVIS, SHOTSPEC, OUT = argv[0], argv[1], argv[2]
tmp = os.path.join(os.path.dirname(OUT), "_geo_tmp")
sys.argv = [sys.argv[0], "--", PREVIS, tmp, "--no-render"]
runpy.run_path(os.path.join(HERE, "build_from_spec.py"), run_name="__main__")
shutil.rmtree(tmp, ignore_errors=True)

sc = bpy.context.scene
FPS = sc.render.fps
spec = json.load(open(SHOTSPEC, encoding="utf-8"))
markers = sorted(((m.frame - 1) / FPS, m.camera) for m in sc.timeline_markers)
people = {o.name for o in bpy.data.objects if o.type == "EMPTY" and bpy.data.objects.get(o.name + "_head")}
boxes = [o for o in bpy.data.objects if o.type == "MESH" and not any(o.name.startswith(p + "_") for p in people)]
TALL = [o for o in boxes if o.dimensions.z > 6 * max(o.dimensions.x, o.dimensions.y, 1e-6) and o.dimensions.z > 3]


def cam_at(t):
    cur = None
    for t0, c in markers:
        if t0 <= t + 1e-6:
            cur = c
    return cur


def inside(o, p):
    mn = Vector(min(v[i] for v in (o.matrix_world @ Vector(c) for c in o.bound_box)) for i in range(3))
    mx = Vector(max(v[i] for v in (o.matrix_world @ Vector(c) for c in o.bound_box)) for i in range(3))
    return all(mn[i] + 1e-4 < p[i] < mx[i] - 1e-4 for i in range(3))


def owner(obj):
    for p in people:
        if obj.name == p or obj.name.startswith(p + "_"):
            return p
    return obj.name


def subjects(body):
    """从"画面里：……。"取主体。镜子里、画像里的人不算；只露手脚的特写不查头；虚化、背影、背对镜头的算前景。"""
    m = re.search(r"画面里：([^。]*)。", body)
    if not m:
        return [], [], []
    main, fg, partial = [], [], []
    for item in re.split(r"[、，]", m.group(1)):
        if re.search(r"镜子里|画像里|铜镜里", item):
            continue
        for p in people:
            if p in item:
                if re.search(r"的手|的双手|的脚|光着的脚|的鼓面", item):
                    partial.append(p)
                elif re.search(r"虚化|背影|肩膀|后脑|背对", item):
                    fg.append(p)
                else:
                    main.append(p)
    return main, fg, partial


rows, axis_sides, comp = [], {}, []  # comp：构图统计（不拦，docs/21 第五节）
dg = bpy.context.evaluated_depsgraph_get()
for sh in spec["shots"]:
    L = sh["t1"] - sh["t0"]
    main, fg, partial = subjects(sh["body"])
    ok_occ = set(sh.get("allow_occlude", []))
    notes = []
    level = "PASS"
    for frac in (0.25, 0.5, 0.75):
        t = sh["t0"] + frac * L
        sc.frame_set(int(round(1 + t * FPS)))
        dg = bpy.context.evaluated_depsgraph_get()
        cam = cam_at(t)
        if cam is None:
            continue
        sc.camera = cam
        cp = cam.matrix_world.translation
        for o in boxes:
            if inside(o, cp):
                notes.append(f"{t:.1f}s 镜头在「{o.name}」里面")
                level = "FAIL"
        if frac == 0.5 and main and sh.get("struct", {}).get("type") in ("single", "ots", "track"):
            hd0 = bpy.data.objects[main[0] + "_head"].matrix_world.translation
            v0 = world_to_camera_view(sc, cam, hd0)
            if v0.z > 0:
                eye = abs(cp.z - hd0.z) < 0.35
                mid = 0.43 <= v0.x <= 0.57
                comp.append((sh, main[0], v0.x, eye, mid))
        for p in main:
            head = bpy.data.objects[p + "_head"].matrix_world.translation
            body = bpy.data.objects[p + "_body"]
            v = world_to_camera_view(sc, cam, head)
            if not (0 <= v.x <= 1 and 0 <= v.y <= 1 and v.z > 0):
                notes.append(f"{t:.1f}s「{p}」的头不在画面里")
                level = "FAIL"
                continue
            top = body.matrix_world @ Vector((0, 0, body.dimensions.z / 2))
            feet = body.matrix_world @ Vector((0, 0, -body.dimensions.z / 2))
            hgt = abs(world_to_camera_view(sc, cam, head).y - world_to_camera_view(sc, cam, feet).y)
            if hgt < 0.06 and p not in sh.get("allow_small", []):
                notes.append(f"{t:.1f}s「{p}」只占画高 {hgt:.0%}，太小")
                level = "FAIL" if level == "FAIL" else "WARN"
            d = head - cp
            hit, loc, _n, _i, obj, _m = sc.ray_cast(dg, cp, d.normalized(), distance=d.length)
            if hit and owner(obj) != p and owner(obj) not in ok_occ and (loc - cp).length < d.length - 0.05:
                who = owner(obj)
                if who in fg:
                    notes.append(f"{t:.1f}s「{p}」被前景「{who}」挡住（规格写了前景虚化，属有意遮挡；确认嘴没被挡）")
                else:
                    notes.append(f"{t:.1f}s「{p}」被「{who}」挡住")
                    level = "FAIL" if level == "FAIL" else "WARN"
            for o in [x for x in boxes if x.name not in ok_occ and max(x.dimensions.x, x.dimensions.y) > 0.15
                      and x.dimensions.z > 6 * max(x.dimensions.x, x.dimensions.y) and x.dimensions.z > 3]:
                c = o.matrix_world.translation
                ov = world_to_camera_view(sc, cam, c)
                xs = [world_to_camera_view(sc, cam, o.matrix_world @ Vector(cc)).x for cc in o.bound_box]
                # 只看离主体不远的竖直物体：远处的人类尺度家具在微距焦外，不会和主体融在一起
                if min(xs) - 0.01 <= v.x <= max(xs) + 0.01 and v.z < ov.z < v.z * 6:
                    notes.append(f"{t:.1f}s「{p}」头后是竖直物体「{o.name}」，会融在一起")
                    level = "FAIL" if level == "FAIL" else "WARN"
        for p in fg:  # 过肩的前景人物至少要有肩膀在画里，否则过肩就成了单人镜头（《天劫外包》第 6 条、样例第 1 条教训）
            hd = bpy.data.objects[p + "_head"].matrix_world.translation
            sh_pt = hd - Vector((0, 0, 0.3))
            vs = [world_to_camera_view(sc, cam, x) for x in (hd, sh_pt)]
            if not any(-0.05 <= w.x <= 1.05 and -0.1 <= w.y <= 1.05 and w.z > 0 for w in vs):
                notes.append(f"{t:.1f}s 前景「{p}」不在画里，过肩没过上")
                level = "FAIL"
        ax = spec.get("axis")
        both = ax and all(n in main + fg for n in (ax.get("a"), ax.get("b")))
        if both and ax.get("a") in people and ax.get("b") in people and frac == 0.5:
            pa = bpy.data.objects[ax["a"]].matrix_world.translation
            pb = bpy.data.objects[ax["b"]].matrix_world.translation
            cross = (pb.x - pa.x) * (cp.y - pa.y) - (pb.y - pa.y) * (cp.x - pa.x)
            off = abs(cross) / max((pb - pa).xy.length, 1e-6)
            # 机位离轴线很近（正打、正反打的正面）不算哪一侧
            if "人类视角" not in sh["name"] and not sh.get("new_axis") and off > 1.5:
                axis_sides[sh["id"]] = "左" if cross > 0 else "右"
    rows.append((sh, level, sorted(set(notes), key=notes.index)))

if len(set(axis_sides.values())) > 1:
    rows.append(({"id": "-", "name": "轴线", "t0": 0, "t1": spec["duration"]}, "WARN",
                 [f"机位在轴线两侧都出现：{axis_sides}（除非是有意换轴，并在规格里给该镜写 new_axis: true）"]))

lines = [f"# 白模几何检查：第 {spec['clip']} 条 {spec['title']}", "",
         "| 镜头 | 时间 | 结果 | 说明 |", "|---|---|---|---|"]
for sh, level, notes in rows:
    lines.append(f"| {sh['id']} {sh['name']} | {sh['t0']:g}–{sh['t1']:g} 秒 | {level} | {'；'.join(notes) or '主体入画、大小合适、没有被挡、头后干净'} |")
if comp:
    lines += ["", "## 构图（只统计，不拦）", "", "| 镜头 | 主体 | 头部水平位置 | 判断 |", "|---|---|---|---|"]
    for sh, p, x, eye, mid in comp:
        tag = "居中平视" if (eye and mid) else ("居中" if mid else ("黄金分割附近" if 0.32 <= x <= 0.44 or 0.56 <= x <= 0.68 else "偏边"))
        lines.append(f"| {sh['id']} {sh['name']} | {p} | {x:.0%} | {tag} |")
open(OUT, "w", encoding="utf-8").write("\n".join(lines) + "\n")
