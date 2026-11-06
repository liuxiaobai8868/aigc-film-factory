#!/usr/bin/env python3
"""色表与黑白明暗检查（docs/21 第五节；Eian：配色单独设计，转黑白看人和背景分不分得开）。

  python3 tools/color_check.py projects/<项目>      （要 Pillow，不加 -I）

读 交付/参考图定版/ 里的场景图和人物、巨物设定图（定版图不全时读 交付/资产图/），写：
  logs/色表.md        每张图的主色（约 60 / 30 / 10 三档）、明暗反差、和类型卡色彩的对照
  logs/黑白对照.jpg    上排原图、下排黑白，一眼看出明暗层次
只提醒，不拦：反差太低（整张灰成一片）。主色只列出来和类型卡对照，不自动判（同一色系的深浅会被分成几档）。
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont, ImageStat

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def palette(img, k=3):
    """主色：中位切分量化成 k 色，按占比排序（只用 Pillow）。"""
    q = img.convert("RGB").resize((160, 90)).quantize(colors=k, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()
    counts = sorted(q.getcolors(), reverse=True)
    n = sum(c for c, _ in counts)
    return [("#%02x%02x%02x" % tuple(pal[i * 3:i * 3 + 3]), c / n) for c, i in counts]


def contrast(img):
    g = img.convert("L").resize((192, 108))
    sd = ImageStat.Stat(g).stddev[0] / 255
    hist = g.histogram()
    tot, acc, lo, hi = sum(hist), 0, 0, 255
    for v, c in enumerate(hist):
        acc += c
        if acc >= tot * 0.05 and lo == 0:
            lo = v
        if acc >= tot * 0.95:
            hi = v
            break
    return sd, (hi - lo) / 255


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    proj = os.path.abspath(sys.argv[1])
    d = os.path.join(proj, "交付", "参考图定版")
    if not os.path.isdir(d) or not os.listdir(d):
        d = os.path.join(proj, "交付", "资产图")
    files = sorted(f for f in os.listdir(d) if f.lower().endswith((".png", ".jpg")) and (f.startswith("场景_") or "三视图" in f or "设定图" in f))
    if not files:
        sys.exit("没有找到场景图或人物图")
    look = {}
    p = os.path.join(proj, "设定.json")
    if os.path.exists(p):
        g = (json.load(open(p, encoding="utf-8")).get("look") or {}).get("genre")
        if g:
            lib = {c["id"]: c for c in json.load(open(os.path.join(ROOT, "config", "genre_library.json"), encoding="utf-8"))["类型"]}
            for gid in ([g] if isinstance(g, str) else g):
                if gid in lib:
                    look[gid] = lib[gid]["色彩"]
    L = ["# 色表与明暗（只提醒，不拦）", ""]
    if look:
        L += ["类型卡要求的色彩：" + "；".join(f"{k} {v}" for k, v in look.items()), ""]
    L += ["| 图 | 主色（占比） | 明暗反差 | 提醒 |", "|---|---|---|---|"]
    thumbs = []
    for f in files:
        im = Image.open(os.path.join(d, f))
        pal = palette(im)
        sd, rng = contrast(im)
        warn = []
        if sd < 0.12:
            warn.append("反差太低，转黑白后灰成一片，人和背景分不开")
        cells = "、".join(f"{h} {s:.0%}" for h, s in pal)
        L.append(f"| {f} | {cells} | {sd:.2f}（5–95% 跨度 {rng:.2f}） | {'；'.join(warn) or '—'} |")
        thumbs.append((f, im))
    L += ["", "明暗反差是黑白图亮度的标准差：0.12 以下偏平，0.18 以上层次清楚。人物设定图是灰底版式，主要看场景图。",
          "黑白对照图：`logs/黑白对照.jpg`（上排原图，下排黑白）。"]
    w, h = 400, 225
    sheet = Image.new("RGB", (w * len(thumbs), h * 2 + 30), (20, 20, 20))
    dr = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/STHeiti Medium.ttc", 16)
    except OSError:
        font = ImageFont.load_default()
    for i, (f, im) in enumerate(thumbs):
        t = im.convert("RGB").resize((w, h))
        sheet.paste(t, (i * w, 30))
        sheet.paste(t.convert("L").convert("RGB"), (i * w, 30 + h))
        dr.text((i * w + 6, 6), f[:24], fill=(230, 230, 230), font=font)
    os.makedirs(os.path.join(proj, "logs"), exist_ok=True)
    sheet.save(os.path.join(proj, "logs", "黑白对照.jpg"), quality=88)
    open(os.path.join(proj, "logs", "色表.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
