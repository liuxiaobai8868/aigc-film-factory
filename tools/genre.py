#!/usr/bin/env python3
"""类型片库与时长档位查询（docs/21）。

  python3 -I tools/genre.py --menu              类型菜单（给用户挑）
  python3 -I tools/genre.py --card G18          一张类型卡全文
  python3 -I tools/genre.py --tiers             时长档位表（含估价）
  python3 -I tools/genre.py --estimate 142      按秒数估算视频花费（各模型）
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(name):
    return json.load(open(os.path.join(ROOT, "config", name), encoding="utf-8"))


def lib():
    return {c["id"]: c for c in load("genre_library.json")["类型"]}


def tiers():
    return {t["id"]: t for t in load("duration_tiers.json")["档位"]}


def estimate(sec):
    out = []
    for v in load("prices.json")["视频"]:
        if v.get("每秒"):
            out.append(f"{v['名称']} 约 {v['每秒'] * sec:.0f} {v['币种']}（{v['每秒']}/秒，{v['分辨率']}）")
    return out


def menu():
    cur = None
    for c in lib().values():
        if c["大类"] != cur:
            cur = c["大类"]
            print(f"\n【{cur}】")
        print(f"  {c['id']} {c['名称']} —— {c['一句话']}（参考：{'；'.join(c['参考'])}）")


def card(gid):
    c = lib()[gid]
    for k, v in c.items():
        if k == "剪辑":
            v = f"平均镜长 {v['平均镜长'][0]}–{v['平均镜长'][1]} 秒；{v['说明']}"
        print(f"{k}：{'、'.join(v) if isinstance(v, list) else v}")


def tier_table():
    p = load("prices.json")
    img = p["出图"]["每张"]
    for t in tiers().values():
        lo, hi = t["秒"]
        cost = "；".join(estimate(hi))
        print(f"{t['id']:>6} {t['名称']}：{t['条'][0]}–{t['条'][1]} 条，场景 ≤{t['场景上限']}，有名字的角色 ≤{t['角色上限']}，{t['结构']}；"
              f"资产 {t['资产'][0]}–{t['资产'][1]} 张（约 {t['资产'][1] * img:.1f} USD）；按 {hi} 秒估视频：{cost}")


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    if a[0] == "--menu":
        menu()
    elif a[0] == "--card":
        card(a[1])
    elif a[0] == "--tiers":
        tier_table()
    elif a[0] == "--estimate":
        print("\n".join(estimate(float(a[1]))) + "\n（以平台账单为准，未含重拍）")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
