"""在 Blender 里按镜头规格 JSON 搭白模预演并渲染帧序列。由 render_previs.py 调用：

    <Blender> -b --factory-startup -P build_from_spec.py -- <spec.json> <帧输出目录> [--stills]

坐标：米制，Z 向上。人物 face=0 时正面朝 -Y，face 为绕 Z 轴的角度（度，逆时针为正）。
规格字段见 tools/previs/README.md。
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa: E402,F401  (bpy, reset, box, person, key, camera, linear_all)

argv = sys.argv[sys.argv.index("--") + 1:]
SPEC = json.load(open(argv[0], encoding="utf-8"))
OUT = argv[1]
STILLS = "--stills" in argv
NO_RENDER = "--no-render" in argv  # 只搭场景不渲染（geometry_check.py 用）

dur = float(SPEC["duration"])
sc = reset(dur)
res = SPEC.get("resolution", [1280, 720])
sc.render.resolution_x, sc.render.resolution_y = res
if "world_color" in SPEC:
    sc.world.color = SPEC["world_color"]


def keyed_times(keys):
    return sorted(keys, key=lambda k: k["t"])


# 静态与可动方块：min/max 是初始包围盒；keys 里的 offset 是相对初始位置的位移，scale 是缩放倍数
for b in SPEC.get("boxes", []):
    o = box(b["name"], b["min"][0], b["max"][0], b["min"][1], b["max"][1], b["min"][2], b["max"][2],
            tuple(b.get("color", (0.4, 0.4, 0.4))))
    base_loc, base_scale = tuple(o.location), tuple(o.scale)
    for k in keyed_times(b.get("keys", [])):
        off = k.get("offset", (0, 0, 0))
        sc_mul = k.get("scale", (1, 1, 1))
        key(o, k["t"], loc=tuple(base_loc[i] + off[i] for i in range(3)),
            scale=tuple(base_scale[i] * sc_mul[i] for i in range(3)))

# 人物：圆柱 + 球头代理，keys 给出位置与朝向；lean 为前倾角
aims = {}
for p in SPEC.get("people", []):
    h = p.get("height", 1.70)
    root = person(p["name"], tuple(p.get("color", (0.85, 0.25, 0.10))), h)
    aim = bpy.data.objects.new(p["name"] + "_aim", None)
    bpy.context.collection.objects.link(aim)
    aims[p["name"]] = aim
    for k in keyed_times(p["keys"]):
        x, y, z = k["pos"]
        key(root, k["t"], loc=(x, y, z), rot=(-k.get("lean", 0), 0, k.get("face", 0)))
        key(aim, k["t"], loc=(x, y, z + 0.8 * h))


def wobble(t, amp):
    return (amp * math.sin(t * 7.1), amp * math.sin(t * 5.3 + 1), amp * math.sin(t * 6.2 + 2))


# 镜头：每个 shot 从 start 开始，到下一个 shot 的 start 结束；时间轴标记绑定相机实现硬切
shots = sorted(SPEC["shots"], key=lambda s: s["start"])
cams = []
for i, s in enumerate(shots):
    c = camera(s.get("lens", 35))
    c.name = s.get("name", f"C{i + 1}")
    end = shots[i + 1]["start"] if i + 1 < len(shots) else dur
    target = s.get("look_at")
    if target is not None:
        aim = aims.get(target) if isinstance(target, str) else None
        if aim is None:
            aim = bpy.data.objects.new(c.name + "_target", None)
            bpy.context.collection.objects.link(aim)
            aim.location = target
        con = c.constraints.new("TRACK_TO")
        con.target = aim
        con.track_axis = "TRACK_NEGATIVE_Z"
        con.up_axis = "UP_Y"
    ks = keyed_times(s["keys"])
    amp = s.get("handheld", 0.0)
    times = sorted({k["t"] for k in ks} | ({round(s["start"] + j * 0.25, 2) for j in range(int((end - s["start"]) / 0.25) + 1)} if amp else set()))
    for t in times:
        # 在相邻关键帧之间线性插值，再叠加手持晃动
        prev = max((k for k in ks if k["t"] <= t), key=lambda k: k["t"], default=ks[0])
        nxt = min((k for k in ks if k["t"] >= t), key=lambda k: k["t"], default=ks[-1])
        u = 0 if nxt["t"] == prev["t"] else (t - prev["t"]) / (nxt["t"] - prev["t"])
        pos = [prev["pos"][j] + (nxt["pos"][j] - prev["pos"][j]) * u for j in range(3)]
        w = wobble(t, amp)
        pos = tuple(pos[j] + w[j] for j in range(3))
        rot = None
        if target is None:
            r0, r1 = prev.get("rot", (90, 0, 0)), nxt.get("rot", (90, 0, 0))
            rot = tuple(r0[j] + (r1[j] - r0[j]) * u for j in range(3))
        key(c, t, loc=pos, rot=rot if rot else (90, 0, 0))
    if ks[-1]["t"] < end:
        key(c, end, loc=tuple(ks[-1]["pos"]), rot=ks[-1].get("rot", (90, 0, 0)) if target is None else (90, 0, 0))
    cams.append((s["start"], c))
    m = sc.timeline_markers.new(c.name, frame=int(1 + s["start"] * FPS))
    m.camera = c
sc.camera = cams[0][1]

linear_all()
os.makedirs(OUT, exist_ok=True)
if NO_RENDER:
    pass
elif STILLS:
    # 每个镜头取中点一帧
    for i, (t0, c) in enumerate(cams):
        t1 = cams[i + 1][0] if i + 1 < len(cams) else dur
        f = int(1 + (t0 + t1) / 2 * FPS)
        sc.camera = c
        sc.frame_set(f)
        sc.render.filepath = f"{OUT}/still_{i + 1:02d}.png"
        bpy.ops.render.render(write_still=True)
else:
    render(OUT)
