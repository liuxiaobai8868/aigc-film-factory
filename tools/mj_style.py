#!/usr/bin/env python3
"""风格库查询：风格配方（Image 2.5 / Banana / Seedance 通用英文描述）和 493 张样图条目；可把选中的样图拼成对比图。

  python3 -I tools/mj_style.py --recipes             # 列出全部风格配方
  python3 -I tools/mj_style.py --recipe R03 R04      # 打印配方英文全文（直接套进 STYLE 段 / 质感后缀）

  python3 -I tools/mj_style.py c254 s218            # 按编号看详情
  python3 -I tools/mj_style.py --find 雷 写实       # 关键词（标题/小类/色调/介质/原提示词，全部命中才算）
  python3 -I tools/mj_style.py --cats               # 列出全部小类和条数
  python3 -I tools/mj_style.py c254 s218 --sheet out.jpg   # 拼对比图（需要原 zip，见库里"来源"）

配方：config/style_recipes.json；样图：config/mj_style_library.json；拼图：docs/assets/mj风格库/；用法：docs/16-风格库.md
样图里的 MJ 风格码和参数只作档案，出图时不用。
"""
import argparse
import json
import os
import sys
import zipfile
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(ROOT, "config", "mj_style_library.json")
RECIPES = os.path.join(ROOT, "config", "style_recipes.json")
ZIP = "/Users/wangpeng/精品资料/7(1).最强角色-场景-巨兽资产生成/MJ码图对照_完整版.zip"


def load():
    return json.load(open(LIB, encoding="utf-8"))["条目"]


def show(e, full=False):
    print(f"[{e['id']}] {e['大类']} / {e['小类']} / {e['标题']}（{e['码型']}）")
    print(f"  色调：{e['色调']}")
    if e["整组效果"]:
        print(f"  整组效果：{e['整组效果']}")
    print(f"  介质：{e['介质']}")
    p = e["原提示词"]
    print(f"  原提示词：{p if full else p[:240] + ('…' if len(p) > 240 else '')}")


def zip_names():
    z = zipfile.ZipFile(ZIP)
    m = {}
    for i in z.infolist():
        n = i.filename
        try:
            n = n.encode("cp437").decode("gbk")
        except Exception:
            pass
        m[n.replace("\\", "/")] = i
    return z, m


def sheet(entries, out):
    from io import BytesIO
    from PIL import Image, ImageDraw, ImageFont
    z, m = zip_names()
    W, H, cols = 640, 360, min(3, len(entries))
    rows = (len(entries) + cols - 1) // cols
    img = Image.new("RGB", (W * cols, H * rows))
    d = ImageDraw.Draw(img)
    try:
        f = ImageFont.truetype("/System/Library/Fonts/STHeiti Medium.ttc", 26)
    except Exception:
        f = ImageFont.load_default()
    for k, e in enumerate(entries):
        info = m.get(e["原图"].split("/", 1)[1])
        if not info:
            continue
        im = Image.open(BytesIO(z.read(info))).convert("RGB")
        im.thumbnail((W, H))
        x, y = (k % cols) * W, (k // cols) * H
        img.paste(im, (x + (W - im.width) // 2, y + (H - im.height) // 2))
        d.rectangle([x, y, x + 90, y + 34], fill=(0, 0, 0))
        d.text((x + 6, y + 3), e["id"], fill=(255, 230, 0), font=f)
    img.save(out, quality=85)
    print("对比图：", out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--find", nargs="+")
    ap.add_argument("--cats", action="store_true")
    ap.add_argument("--full", action="store_true", help="原提示词不截断")
    ap.add_argument("--sheet")
    ap.add_argument("--recipes", action="store_true", help="列出全部风格配方")
    ap.add_argument("--recipe", nargs="+", help="打印配方英文全文")
    a = ap.parse_args()
    rec = json.load(open(RECIPES, encoding="utf-8"))["配方"]
    if a.recipes or a.recipe:
        for r in rec:
            if a.recipes or r["id"] in a.recipe:
                print(f"[{r['id']}] {r['名称']}（来源 {r['来源']}；适合 {r['适合']}）")
                if a.recipe:
                    print("  " + r["en"])
        return
    lib = load()
    by = {e["id"]: e for e in lib}
    if a.cats:
        for (big, cat), n in Counter((e["大类"], e["小类"]) for e in lib).items():
            print(f"{big} / {cat}：{n}")
        return
    hits = [by[i] for i in a.ids if i in by]
    for i in a.ids:
        if i not in by:
            print("没有这个编号：", i, file=sys.stderr)
    if a.find:
        for e in lib:
            text = " ".join([e["标题"], e["小类"], e["色调"], e["介质"], e["整组效果"], e["原提示词"]])
            if all(w.lower() in text.lower() for w in a.find):
                hits.append(e)
    for e in hits:
        show(e, a.full)
    print(f"共 {len(hits)} 条")
    if a.sheet and hits:
        sheet(hits[:12], a.sheet)


if __name__ == "__main__":
    main()
