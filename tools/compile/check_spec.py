#!/usr/bin/env python3
"""零抽卡闸门 · 规格自检：出片前对镜头规格单逐镜过一遍（docs/14 第四节）。

用法：python3 -I tools/compile/check_spec.py <规格单.json 或目录>
退出码 0 = 无 FAIL。规则都来自真实翻车：
  时长      规格时长 = 白模时长 = 最后一镜的结束时间（差 5 秒，模型就自己多加一个镜头）
  短镜      < 1.0 秒 FAIL，< 1.5 秒 WARN（1 秒的镜头会被模型并掉）
  画面里    每一镜都要写"画面里："（不写，模型会自己加人）
  台词速度  每镜台词 > 5.5 字/秒 FAIL，> 4.5 字/秒 WARN
  说话人    每句台词的说话人要在"画面里"，或者写明画外 / 背对镜头 / 过肩 / 齐声
  齐声      齐声要放在背对镜头或画外的镜头里（十几只同时动嘴，口型必乱）
  否定写法  镜头描述（台词以外）出现"不要 / 不能 / 别 / 不会"WARN（模型对否定句的理解不稳定）
"""
import json
import os
import re
import subprocess
import sys

NEG = re.compile(r"不要|不能|别再|不会|禁止")
SPEAKER = re.compile(r"([一-龥]{1,6})[：:]\s*\{")


def probe(path):
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                           capture_output=True, text=True, check=True)
        return float(r.stdout.strip())
    except Exception:
        return None


def in_frame(body):
    m = re.search(r"画面里：([^。]*)。", body)
    return m.group(1) if m else None


def check(path):
    s = json.load(open(path, encoding="utf-8"))
    base = os.path.dirname(os.path.dirname(os.path.abspath(path)))
    out = []
    dur = s["duration"]
    shots = s["shots"]
    if shots[-1]["t1"] != dur:
        out.append(("FAIL", f"最后一镜结束在 {shots[-1]['t1']} 秒，规格时长是 {dur} 秒"))
    pv = probe(os.path.join(base, s["previs"]))
    if pv is None:
        out.append(("FAIL", f"找不到白模 {s['previs']}"))
    elif abs(pv - dur) > 0.05:
        out.append(("FAIL", f"白模 {pv:g} 秒 ≠ 规格 {dur} 秒（界面时长、白模、规格三者必须一致）"))
    t = 0
    for sh in shots:
        tag = f"镜头{sh['id']}（{sh['t0']:g}–{sh['t1']:g} 秒）"
        if sh["t0"] != t:
            out.append(("FAIL", f"{tag} 和上一镜不连续"))
        t = sh["t1"]
        L = sh["t1"] - sh["t0"]
        if L < 1.0:
            out.append(("FAIL", f"{tag} 只有 {L:g} 秒，会被模型并掉"))
        elif L < 1.5:
            out.append(("WARN", f"{tag} 只有 {L:g} 秒，短镜容易被并掉；人间冷镜头至少给 1.5 秒"))
        body = sh["body"]
        who = in_frame(body)
        if who is None:
            out.append(("FAIL", f"{tag} 没写\"画面里：……。\""))
        lines = re.findall(r"\{([^}]*)\}", body)
        chars = sum(len(re.sub(r"[\s，。！？、…\.,!?—]", "", x)) for x in lines)
        if lines:
            rate = chars / L
            if rate > 5.5:
                out.append(("FAIL", f"{tag} 台词 {chars} 字 / {L:g} 秒 = {rate:.1f} 字/秒，说不完"))
            elif rate > 4.5:
                out.append(("WARN", f"{tag} 台词 {rate:.1f} 字/秒，偏快"))
        # 说话人：有三视图的角色 + 音色锁里写了名字的人（如"老汉：沙哑…"）+ 规格单可选的 chorus 列表（齐声的群体）
        chorus = s.get("chorus", [])
        names = [x["name"] for x in s["assets"] if x["kind"] == "character" and x["name"]] + \
            [v.split("：")[0] for v in s.get("voices", []) if "：" in v] + chorus
        prev = 0
        for m in re.finditer(r"\{[^}]*\}", body):
            seg = body[prev:m.start()]
            seg = re.split(r"[；。]", seg)[-1] if re.search(r"[；。]", seg) else seg
            prev = m.end()
            if re.search(r"画外|背对镜头|过肩|齐声|传出", seg):
                continue
            hits = [(seg.rfind(n), n) for n in names if n in seg]
            if not hits:
                continue  # 同一个人接着说（上一句的说话人）
            name = max(hits)[1]
            if name in chorus:
                out.append(("WARN", f"{tag} 齐声没有写背对镜头或画外"))
            elif who and name not in who:
                out.append(("FAIL", f"{tag} 说话人「{name}」不在画面里（画面里：{who}），要么让他入画，要么写明画外 / 背对镜头"))
        plain = re.sub(r"\{[^}]*\}", "", body)
        if NEG.search(plain):
            out.append(("WARN", f"{tag} 有否定写法「{NEG.search(plain).group(0)}」，改成肯定句"))
    return s, out


def main():
    p = sys.argv[1]
    paths = sorted(os.path.join(p, f) for f in os.listdir(p) if f.endswith(".json")) if os.path.isdir(p) else [p]
    bad = 0
    for path in paths:
        s, out = check(path)
        n_fail = sum(1 for k, _ in out if k == "FAIL")
        bad += n_fail
        print(f"==== 第 {s['clip']} 条（{s['duration']} 秒）：{'通过' if not n_fail else f'{n_fail} 处 FAIL'}")
        for k, msg in out:
            print(f"{k}  {msg}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
