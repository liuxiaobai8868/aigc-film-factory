#!/usr/bin/env python3
"""色表与黑白明暗检查（docs/21 第五节；Eian：配色单独设计，转黑白看人和背景分不分得开）。

  python3 tools/color_check.py projects/<项目>      （要 Pillow，不加 -I）

读 交付/参考图定版/ 里的场景图和人物、巨物设定图（定版图不全时读 交付/资产图/），写：
  logs/色表.md        每张图的主色（约 60 / 30 / 10 三档）、明暗反差、和类型卡色彩的对照
  logs/黑白对照.jpg    上排原图、下排黑白，一眼看出明暗层次
只提醒，不拦：反差太低（整张灰成一片）。主色只列出来和类型卡对照，不自动判（同一色系的深浅会被分成几档）。

  python3 tools/color_check.py --ref <剧照文件夹> [--out 文件.md]      参考片取色（4.0 alpha.9，crew/16）

读文件夹里的参考剧照（jpg / png / webp）：裁掉上下左右的黑边，每张量化成 16 色，相近色按 ΔE（CIE76）< 12 合并，
留占比最高的 8 色；最后把全部剧照合起来再出一份 8 色。默认写到 <剧照文件夹>/../../logs/参考片取色.md（项目的 logs）。
色值只写进研究书和风格配方的说明，不写进视频提示词。
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


def crop_black(img, thr=18):
    """裁掉黑边（宽银幕的上下黑条、左右黑条）：逐行逐列看平均亮度。"""
    g = img.convert("L")
    w, h = g.size
    small = g.resize((max(1, w // 4), max(1, h // 4)))
    sw, sh = small.size
    px = small.load()
    rows = [sum(px[x, y] for x in range(sw)) / sw for y in range(sh)]
    cols = [sum(px[x, y] for y in range(sh)) / sh for x in range(sw)]
    top = next((i for i, v in enumerate(rows) if v > thr), 0)
    bot = sh - next((i for i, v in enumerate(reversed(rows)) if v > thr), 0)
    lef = next((i for i, v in enumerate(cols) if v > thr), 0)
    rig = sw - next((i for i, v in enumerate(reversed(cols)) if v > thr), 0)
    if bot - top < sh * 0.3 or rig - lef < sw * 0.3:
        return img  # 整张都很暗（夜戏），不裁
    return img.crop((lef * 4, top * 4, rig * 4, bot * 4))


def _lab(rgb):
    def f(c):
        c /= 255
        return ((c + 0.055) / 1.055) ** 2.4 if c > 0.04045 else c / 12.92
    r, g, b = (f(float(x)) for x in rgb)
    x, y, z = (r * 0.4124 + g * 0.3576 + b * 0.1805) / 0.95047, r * 0.2126 + g * 0.7152 + b * 0.0722, (r * 0.0193 + g * 0.1192 + b * 0.9505) / 1.08883
    t = [v ** (1 / 3) if v > 0.008856 else 7.787 * v + 16 / 116 for v in (x, y, z)]
    return 116 * t[1] - 16, 500 * (t[0] - t[1]), 200 * (t[1] - t[2])


def palette_de(img, k=8, n=16, de=12.0):
    """量化成 n 色，按 ΔE 合并相近色（占比加到主色上），留 k 色。"""
    q = img.convert("RGB").resize((240, 135)).quantize(colors=n, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()
    tot = 240 * 135
    cs = sorted(((c / tot, tuple(pal[i * 3:i * 3 + 3])) for c, i in q.getcolors()), reverse=True)
    keep = []
    for share, rgb in cs:
        lab = _lab(rgb)
        for kk in keep:
            if sum((a - b) ** 2 for a, b in zip(lab, kk[2])) ** 0.5 < de:
                kk[0] += share
                break
        else:
            keep.append([share, rgb, lab])
    keep.sort(key=lambda x: -x[0])
    return [("#%02x%02x%02x" % kk[1], kk[0]) for kk in keep[:k]]


def ref_main(args):
    d = os.path.abspath(args[0])
    out = args[args.index("--out") + 1] if "--out" in args else os.path.join(os.path.dirname(os.path.dirname(d)), "logs", "参考片取色.md")
    files = sorted(f for f in os.listdir(d) if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp")))
    if not files:
        sys.exit(f"{d} 里没有剧照（jpg / png / webp）")
    L = ["# 参考片取色（只给研究书用，色值不写进视频提示词）", "", f"剧照：`{d}`，共 {len(files)} 张；裁黑边，ΔE < 12 的相近色合并。", "",
         "| 剧照 | 8 个主色（占比） | 明暗反差 |", "|---|---|---|"]
    allpx = []
    for f in files:
        im = crop_black(Image.open(os.path.join(d, f)).convert("RGB"))
        allpx.append(im.resize((160, 90)))
        sd, _ = contrast(im)
        L.append(f"| {f} | {'、'.join(f'{h} {s:.0%}' for h, s in palette_de(im))} | {sd:.2f} |")
    sheet = Image.new("RGB", (160, 90 * len(allpx)))
    for i, im in enumerate(allpx):
        sheet.paste(im, (0, 90 * i))
    L += ["", "**全部剧照合起来**：" + "、".join(f"{h} {s:.0%}" for h, s in palette_de(sheet)), "",
          "用法：按占比排出 60 / 30 / 10（最大的一两色是主调，中间是辅调，最后一个高饱和的小色块常常就是点缀色），写进研究书视听层的色彩一行；"
          "同一部片取不同场景的剧照，别只取海报和宣传照（海报的颜色是调过的）。"]
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "--ref":
        return ref_main(sys.argv[2:])
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
