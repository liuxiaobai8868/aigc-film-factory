#!/usr/bin/env python3
"""Seedance 2.5 提示词机检（《提示词圣经》第十节的可机检部分）。

用法：
    python3 tools/prompt_lint.py 10-提示词/S03-G1-v1.md [--duration 30] [--ban 灯塔,岛]
    python3 tools/prompt_lint.py 交付/02-Seedance提示词.md --all   # 逐条检查整份交付文档

--all 模式按"## 第 N 条"分节，每节读第一个 ```text 块，时长取"界面参数"里的"N 秒"，
画外禁名取"**画外禁名**：A、B（…）"一行。

读取文件里第一个 ```text 代码块作为提示词，检查：
字符数上限、年龄词、淡出、平台参数混入、时间段连续性、人数锁、声音抑制位置、
正文中 @标签做主语、必备段落。只做机检，不替代场记与导演的人工审核。
"""
import argparse
import re
import sys

LIMIT = 5000
AGE_WORDS = ["男孩", "女孩", "孩子", "小孩", "少年", "少女", "年轻", "幼", "岁",
             "boy", "girl", "kid", "child", "teen", "young"]
PLATFORM_WORDS = ["分辨率", "1080p", "720p", "480p", "4K", "16:9", "9:16", "21:9", "画幅", "Seedance"]
REQUIRED = ["【场景上下文】", "【时间轴】", "【声音】"]


def extract_prompt(text):
    m = re.search(r"```text\n(.*?)\n```", text, re.S)
    return m.group(1) if m else text


def check(prompt, duration, ban=()):
    issues, warns = [], []
    # 画外禁名：本条画面里不该出现的实体，名字一出现模型就会画（G2 灯塔事故）
    for w in ban:
        k = prompt.count(w)
        if k:
            issues.append(f"画外禁名「{w}」出现 {k} 次：画外实体不点名，只写它在画面里的效果和画框方位")
    geo = prompt.split("【空间地图】", 1)[1] if "【空间地图】" in prompt else ""
    geo = re.split(r"\n【", geo, 1)[0]
    for line in geo.splitlines():
        if re.search(r"不入画|在画外|画框外", line) and line.strip().startswith("—"):
            issues.append(f"空间地图里写了画外实体：{line.strip()[:30]}…（删掉这一行，只写画面里看得见的效果）")
    if re.search(r"光束|光带|光柱|探照|扫亮|光[^。；，]{0,10}[扫滑]过", prompt) and "光源本体" not in prompt:
        warns.append("有扫过的光但没写「画面里看不见光源本体」：模型会把光源画成正对镜头的光团")
    if re.search(r"朝镜头(跑|走|冲)", prompt) and not re.search(r"离(镜头|机位)约\s*\d+", prompt):
        warns.append("人物朝镜头运动但没写停在离镜头几米：落点会贴到镜头上变大脸")
    if re.search(r"@视频\d+\s*(是本条的)?白模预演|@视频\d+\s*只提供", prompt):
        tl_lines = [l for l in (prompt.split("【时间轴】", 1)[-1].split("\n【", 1)[0]).splitlines()
                    if re.match(r"\s*\d+(?:\.\d+)?\s*[–\-~]", l)]
        loose = [l[:12] for l in tl_lines if "预演" not in l]
        if loose:
            issues.append(f"有白模预演但时间轴这几行没对应预演段：{loose}（每行写「同预演 X–Y 秒」，切点与预演一致）")
    if "一镜到底" in prompt and (duration or 0) >= 15 and "@视频" not in prompt:
        warns.append("一镜到底 ≥15 秒且没有 @视频 结构参考：机位与人物距离变化大时先做白模预演（crew/25）")
    if "慢动作" in prompt and not re.search(r"\d(?:\.\d+)?\s*倍", prompt):
        warns.append("写了慢动作但没写倍速：慢动作只给一整个镜头并写倍速，如「18–21 秒整段 0.4 倍慢动作」（圣经第 29 条）")
    empty = [w for w in ("电影感", "大师级", "超高清", "8K", "高级感", "史诗感", "masterpiece", "highly detailed", "UE5", "虚幻引擎") if w in prompt]
    if empty:
        warns.append(f"有空词 {empty}：删掉以后画面仍要具体（克制测试，docs/06 第六节第 8 条）")
    n = len(prompt)
    if n > LIMIT:
        issues.append(f"字符数 {n} 超过硬上限 {LIMIT}")
    elif n > 4800:
        warns.append(f"字符数 {n} 接近上限 {LIMIT}")

    for w in AGE_WORDS:
        for m in re.finditer(re.escape(w), prompt, re.I):
            ctx = prompt[max(0, m.start() - 8): m.end() + 8].replace("\n", " ")
            if w == "岁" and not re.search(r"\d+\s*岁|[一二三四五六七八九十]+岁", ctx):
                continue
            issues.append(f"年龄词「{w}」: …{ctx}…")
    if re.search(r"(?<![不无])淡出|(?<!no )fade ?out", prompt, re.I):
        issues.append("出现「淡出」：改为「硬切黑，不淡出」")
    for w in PLATFORM_WORDS:
        if w in prompt:
            warns.append(f"疑似平台参数写进正文：「{w}」（应在界面设置）")
    for sec in REQUIRED:
        if sec not in prompt:
            warns.append(f"缺少段落 {sec}")
    if not re.search(r"画面中(始终)?只有\s*\S+\s*个", prompt):
        warns.append("开头未见人数锁（例：画面中只有 2 个角色：A、B）")
    if re.search(r"\([^)]*(无|不要|没有)[^)]*(音乐|BGM)[^)]*\)", prompt):
        issues.append("音乐抑制写在 () 里，可能被当成音乐指令")

    # 时间段连续性
    spans = [(float(a), float(b)) for a, b in re.findall(r"(\d+(?:\.\d+)?)\s*[–\-~至]\s*(\d+(?:\.\d+)?)\s*秒", prompt)]
    tl = prompt.split("【时间轴】", 1)[1] if "【时间轴】" in prompt else ""
    tl = re.split(r"\n【", tl, 1)[0]
    tspans = [(float(a), float(b)) for a, b in re.findall(r"(?m)^\s*(\d+(?:\.\d+)?)\s*[–\-~]\s*(\d+(?:\.\d+)?)\s*秒", tl)]
    if tspans:
        if tspans[0][0] != 0:
            issues.append(f"时间轴不从 0 秒开始：{tspans[0]}")
        for (a1, b1), (a2, b2) in zip(tspans, tspans[1:]):
            if a2 != b1:
                issues.append(f"时间段不连续或重叠：{a1}–{b1} 之后是 {a2}–{b2}")
        for a, b in tspans:
            if b - a < 2.5:
                warns.append(f"时间段 {a}–{b} 秒短于 2.5 秒")
        if duration and tspans[-1][1] != duration:
            issues.append(f"时间轴总长 {tspans[-1][1]} 秒 ≠ 设定时长 {duration} 秒")
    elif spans:
        warns.append("【时间轴】段内未找到行首时间段")

    # 正文 @标签做主语
    body = prompt.split("【场景上下文】", 1)[1] if "【场景上下文】" in prompt else ""
    tags = re.findall(r"@(?:图片|视频|音频|Image|Video|Audio)\s*\d+", body)
    if tags:
        warns.append(f"参考映射之外出现标签 {sorted(set(tags))}：2.5 正文应写「名字+可见标记」")

    # 台词容量粗估
    lines = re.findall(r"\{([^}]*)\}", prompt)
    chars = sum(len(re.sub(r"[\s，。！？、…\.,!?]", "", l)) for l in lines)
    if duration and chars > duration * 3.5:
        warns.append(f"台词 {chars} 字，超过 {duration} 秒的舒适容量（约 {int(duration*3)} 字）")
    return n, chars, issues, warns


RISK_WORDS = {
    "镜面/倒影": r"镜子|镜中|倒影|反射出|水面映",
    "画面文字": r"招牌上写|屏幕上显示|字样|标语|写着",
    "形变/VFX": r"变身|变形|化为|溶解|爆炸|雷电|能量|光束|魔法|传送",
    "物理事件": r"撞|碎|破裂|倒塌|飞出|溅|爆|摔|击中|踢中|砸",
}


def complexity(prompt, chars, duration):
    """docs/06 杠杆 4 的复杂度预算（启发式估算，人工复核）。返回 [(项, 数值, 等级)]。"""
    rows = []
    m = re.search(r"画面中(?:始终)?只有\s*(\d+)\s*个", prompt)
    people = int(m.group(1)) if m else None
    if people is not None:
        rows.append(("同框角色", people, "绿" if people <= 2 else "黄" if people == 3 else "红"))
    shots = len(set(re.findall(r"镜头\s*(\d+)", prompt.split("【时间轴】", 1)[-1])))
    if shots:
        rows.append(("镜头数", shots, "绿" if shots <= 7 else "黄" if shots <= 10 else "红"))
    if duration:
        cap = duration * 2  # 30 秒 ≈ 60 字为绿
        rows.append(("台词字数", chars, "绿" if chars <= cap else "黄" if chars <= duration * 3 else "红"))
    tl = prompt.split("【时间轴】", 1)[-1]
    for name, pat in RISK_WORDS.items():
        k = len(re.findall(pat, tl))
        if name in ("镜面/倒影", "画面文字"):
            rows.append((name, k, "绿" if k == 0 else "红"))
        elif name == "形变/VFX":
            rows.append((name, k, "绿" if k <= 1 else "黄" if k == 2 else "红"))
        else:
            rows.append((name, k, "绿" if k <= 2 else "黄" if k <= 4 else "红"))
    return rows


LONG_TAKE_PURPOSES = ("视觉张力", "情绪层次", "推进剧情")


def lint_one(prompt, duration, ban, reason=None, label=""):
    n, chars, issues, warns = check(prompt, duration, ban)
    issues += version_check(prompt, label)
    # 圣经第 26 条：长镜头必须说清是为视觉张力、情绪层次还是推进剧情，并写高级点落在第几秒
    if re.search(r"一镜到底|长镜头", prompt):
        if not reason or not any(k in reason for k in LONG_TAKE_PURPOSES):
            issues.append("一镜到底/长镜头没写理由：在上传清单下加一行「**长镜头理由**：视觉张力 / 情绪层次 / 推进剧情——高级点落在第 X 秒的什么画面」")
        elif not re.search(r"\d", reason):
            warns.append("长镜头理由没写高级点落在第几秒")
    print(f"字符数：{n}/{LIMIT}　台词字数：{chars}")
    for i in issues:
        print("FAIL  " + i)
    for w in warns:
        print("WARN  " + w)
    rows = complexity(prompt, chars, duration)
    if rows:
        level = "红" if any(r[2] == "红" for r in rows) else "黄" if any(r[2] == "黄" for r in rows) else "绿"
        print("复杂度预算（启发式，人工复核）：" + "　".join(f"{a} {b}[{c}]" for a, b, c in rows))
        print(f"复杂度等级：{level}" + ("　→ 红色不得交付：拆条或简化" if level == "红" else "　→ 签字单写明替代方案" if level == "黄" else ""))
    print("结论：" + ("FAIL" if issues else "机检通过（仍需人工审核）"))
    return not issues


def _field(name, *texts):
    for t in texts:
        m = re.search(r"\*\*" + name + r"\*\*：([^\n]+)", t)
        if m:
            return m.group(1)
    return None


def sections(doc):
    """逐条、逐版本产出 (标题, 提示词, 时长, 画外禁名, 长镜头理由, 版本, 本条提醒)。
    每条默认只有 A 预演版；没有 Blender 时可加"### B 无预演版"（docs/09 第三节）。"""
    for part in re.split(r"\n(?=## 第)", doc)[1:]:
        title = part.splitlines()[0].lstrip("# ").strip()
        if "```text" not in part:
            continue
        subs = [x for x in re.split(r"\n(?=### )", part) if "```text" in x]
        versions = []
        for sub in subs:
            head = sub.splitlines()[0]
            label = "A" if re.search(r"### .*(A|预演版)", head) and "无预演" not in head else "B" if re.search(r"### .*(B|无预演)", head) else ""
            versions.append((label, sub))
        notes = []
        labels = {v for v, _ in versions}
        if labels == {"A", "B"}:
            pa, pb = (extract_prompt(next(x for v, x in versions if v == k)) for k in ("A", "B"))
            if re.findall(r"\{([^}]*)\}", pa) != re.findall(r"\{([^}]*)\}", pb):
                notes.append("FAIL  A、B 两版的台词不一致：两个版本必须逐字同一套台词、同一顺序")
            cuts = lambda p: re.findall(r"\d+(?:\.\d+)?", (re.search(r"只在以下时间点硬切：([^秒]*)秒", p) or [None, ""])[1])
            if cuts(pa) != cuts(pb):
                notes.append(f"FAIL  A、B 两版的切点清单不一致：A {cuts(pa)}，B {cuts(pb)}")
        if labels == {"A", "B"} and not _field("推荐", part):
            notes.append("FAIL  两个版本但没有「**推荐**：A 版 / B 版（理由：…）」一行")
        elif labels and labels != {"A", "B"} and "" not in labels:
            pass  # 默认只出 A 白模预演版（docs/09 第三节），单版本不再提醒
        for label, sub in versions:
            m = re.search(r"界面参数\*\*：[^\n]*?(\d+(?:\.\d+)?)\s*秒", sub) or re.search(r"界面参数\*\*：[^\n]*?(\d+(?:\.\d+)?)\s*秒", part)
            b = _field("画外禁名", sub, part)
            ban = [w.strip() for w in re.split(r"[、,，]", re.split(r"[（(]", b)[0]) if w.strip() and w.strip() not in ("无", "<同 A 版>")] if b else []
            if b and "同 A 版" in b:
                a_sub = next((x for v, x in versions if v == "A"), "")
                ab = _field("画外禁名", a_sub) or ""
                ban = [w.strip() for w in re.split(r"[、,，]", re.split(r"[（(]", ab)[0]) if w.strip() and w.strip() != "无"]
            reason = _field("长镜头理由", sub, part)
            yield title, extract_prompt(sub), float(m.group(1)) if m else None, ban, reason, label, notes
            notes = []


def version_check(prompt, label):
    issues = []
    if label == "B" and re.search(r"预演|@视频", prompt):
        issues.append("B 无预演版里出现了「预演」或「@视频」：B 版的结构只能来自文字（米数、切点清单、首帧图）")
    if label == "A" and "@视频" not in prompt:
        issues.append("A 预演版没有 @视频1 的素材职责句")
    if label == "B" and re.search(r"硬切|切至", prompt) and "只在以下时间点硬切" not in prompt:
        issues.append("B 无预演版是多镜头却没有切点清单（圣经第 28 条：本条只在以下时间点硬切：…）")
    return issues


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--duration", type=float, default=None, help="界面设定的时长（秒）")
    ap.add_argument("--ban", default="", help="画外禁名，逗号分隔")
    ap.add_argument("--all", action="store_true", help="逐条检查整份交付文档")
    args = ap.parse_args()
    doc = open(args.file, encoding="utf-8").read()
    if args.all:
        ok = True
        for title, prompt, dur, ban, reason, label, notes in sections(doc):
            tag = {"A": " · A 预演版", "B": " · B 无预演版"}.get(label, "")
            print(f"\n==== {title}{tag}（{dur:g} 秒，画外禁名：{'、'.join(ban) or '无'}）")
            for n_ in notes:
                print(n_)
                ok &= not n_.startswith("FAIL")
            ok &= lint_one(prompt, dur, ban, reason, label)
        sys.exit(0 if ok else 1)
    ban = [w for w in re.split(r"[、,，]", args.ban) if w]
    r = re.search(r"\*\*长镜头理由\*\*：([^\n]+)", doc)
    sys.exit(0 if lint_one(extract_prompt(doc), args.duration, ban, r.group(1) if r else None) else 1)


if __name__ == "__main__":
    main()
