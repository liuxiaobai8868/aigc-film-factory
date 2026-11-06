#!/usr/bin/env python3
"""扩写工作单（docs/21 第四节）：把一部已确认的片子扩到更长的时长档位。

  python3 -I tools/expand.py projects/<项目> <目标档位>     如 3-5、5-8（见 tools/genre.py --tiers）

不改任何数据，只写 logs/扩写工作单.md：
  - 现在多长、目标档位要多长、要加几条；
  - 锁住不动的：内核五格、结尾那一条、每条的价值翻转和高光镜头；
  - 能量曲线和建议的插入点（哪两条之间能量跳得最大、哪里缺一次起落）；
  - 五种扩写手法的空表，智能体据此写 3 个方向给用户选。
用户选定方向后：新条用小数编号插在原条之间（如 2.1、2.2），原条不改；在 分镜.json 里按播放顺序排；
新场景、新人物写进 设定.json，流水线只给新增的资产出图。
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

METHODS = [
    ("副线", "给一个配角一条自己的线：他想要什么、他的价值翻转在哪一条；第三幕汇入主线"),
    ("前史 / 余波", "开头之前的一场（让观众更早在乎那个具体的东西），或结尾之后的一场（余味）"),
    ("二幕三阶升级", "主角的困境升三次级，每一级代价更大；每级一条"),
    ("对手视角", "反派、上级、怪物那一边：他们的规矩和算计，让观众比主角多知道"),
    ("静默戏", "一段不靠台词、只用画面和声音讲的戏（docs/20 第二节第 5 条）"),
]


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    proj, tid = os.path.abspath(sys.argv[1]), sys.argv[2]
    bible = json.load(open(os.path.join(proj, "设定.json"), encoding="utf-8"))
    board = json.load(open(os.path.join(proj, "分镜.json"), encoding="utf-8"))
    tiers = {t["id"]: t for t in json.load(open(os.path.join(ROOT, "config", "duration_tiers.json"), encoding="utf-8"))["档位"]}
    if tid not in tiers:
        sys.exit(f"没有档位 {tid}；可选：{'、'.join(tiers)}")
    t = tiers[tid]
    clips = board["clips"]
    dur = [sum(s.get("dur", 0) for s in c["shots"]) for c in clips]
    total = sum(dur)
    goal = (t["秒"][0] + t["秒"][1]) / 2
    add_sec = max(0.0, goal - total)
    add_n = max(t["条"][0] - len(clips), round(add_sec / 28))
    core = bible.get("core", {})
    L = [f"# 扩写工作单：{bible.get('title', '')} → {t['名称']}", "",
         f"- 现在：{len(clips)} 条，{total:g} 秒。",
         f"- 目标档位：{t['名称']}，{t['秒'][0]}–{t['秒'][1]} 秒，{t['条'][0]}–{t['条'][1]} 条；结构：{t['结构']}；规则：{t['规则']}。",
         f"- 大约要加 **{add_n} 条**（按每条约 28 秒、目标 {goal:g} 秒算）。场景上限 {t['场景上限']}，有名字的角色上限 {t['角色上限']}。",
         "", "## 一、锁住不动", "",
         "| 项 | 内容 |", "|---|---|"]
    for k, zh in (("want", "想要"), ("need", "需要"), ("choice", "选择"), ("cost", "代价"), ("image", "主题画面")):
        L.append(f"| 内核·{zh} | {core.get(k, '—')} |")
    last = clips[-1]
    L += [f"| 结尾那一条 | 第{last['n']}条 {last.get('title', '')}：{last.get('turn', {}).get('from', '')} → {last.get('turn', {}).get('to', '')} |", "",
          "原条的台词、价值翻转、高光镜头都不改；只允许为了衔接改 context 和站位。", "",
          "## 二、能量曲线与插入点", "", "| 条 | 时长 | 能量 入→出 | 价值翻转 | 高光 |", "|---|---|---|---|---|"]
    for c, d in zip(clips, dur):
        e = c.get("energy") or {}
        sig = c.get("signature") or {}
        L.append(f"| {c['n']} {c.get('title', '')} | {d:g} 秒 | {e.get('in', '?')} → {e.get('out', '?')} | "
                 f"{c.get('turn', {}).get('from', '')} → {c.get('turn', {}).get('to', '')} | 第 {sig.get('shot', '?')} 镜 |")
    gaps, cont = [], []
    for a, b in zip(clips, clips[1:]):
        if a.get("location") == b.get("location") and not b.get("time_jump"):
            cont.append(f"第{a['n']}条 → 第{b['n']}条")  # 同一场连续的戏，插进去会断掉尾帧衔接
            continue
        ea, eb = (a.get("energy") or {}).get("out", 3), (b.get("energy") or {}).get("in", 3)
        gaps.append((abs(eb - ea), a["n"], b["n"], ea, eb))
    gaps.sort(reverse=True)
    L += ["", "建议插入点（相邻两条能量跳得最大的地方最需要过渡或升级）："]
    for g, a, b, ea, eb in gaps[:3]:
        L.append(f"- 第{a}条 → 第{b}条：能量 {ea} → {eb}，新条编号用 {a}.1、{a}.2……")
    if cont:
        L.append(f"- 不要插在这些地方（同一场连续的戏，插进去会断掉尾帧衔接）：{'、'.join(cont)}")
    if t["秒"][0] >= 300:
        L.append("- 本档位必须有副线和中点：中点放在全片 45%–55% 处，让前半段被重新理解。")
    L += ["", "## 三、扩写方向（智能体写 3 个方向给用户选，方向之间拉开）", ""]
    for i in range(1, 4):
        L += [f"### 方向 {i}：（一句话）", "", "| 手法 | 用不用 | 新增几条 | 新增什么（场景 / 人物 / 道具） | 新条的价值翻转 |", "|---|---|---|---|---|"]
        L += [f"| {m}（{why}） |  |  |  |  |" for m, why in METHODS]
        L += ["", "新资产：……　新增花费估算：出图 … 张；视频 … 秒（`tools/genre.py --estimate`）", ""]
    L += ["## 四、用户选定之后", "",
          "1. `设定.json` 的 `look.tier` 改成新档位；新场景、新人物、新道具写进设定（按 docs/19 填齐美术字段）。",
          "2. `分镜.json` 按播放顺序插入新条，编号用小数（2.1、2.2）；和前后条同一场连续的，站位要接上，否则写 time_jump。",
          "3. 重排全片能量曲线（energy），过内核闸门和张力机检：`python3 tools/storyboard.py check <项目>`。",
          "4. `pipeline.py run`：只给新增资产出图（报张数和花费，用户点头再 approve），只重渲新条和受影响的条的白模。",
          "5. 剧本三件套同步更新（03-剧本.md 插入新条、节奏曲线、回扣表），并在开头写清这次扩写改了什么。"]
    out = os.path.join(proj, "logs", "扩写工作单.md")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(f"已写 {out}：{len(clips)} 条 {total:g} 秒 → {t['名称']}，约加 {add_n} 条")


if __name__ == "__main__":
    main()
