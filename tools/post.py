#!/usr/bin/env python3
"""后期粗剪（docs/21 第五节、docs/14 4.2 修片阶梯）：按条号把出好的片段拼成一条，顺手修掉模型的固定毛病。

  python3 tools/post.py projects/<项目> [--src 出片] [--head 1] [--tail 0] [--hold 0]
                        [--audio keep|mute|<音频文件>] [--size 1920x1080] [--out 文件]

片段放在 <项目>/出片/（--src 改目录），文件名以"第N条"开头，如 第1条.mp4、第2.1条_第2抽.mp4。
同一条有多个文件时，优先用名字里带"选"的，否则用最新的。

每条做的事：
  --head N   剪掉开头 N 帧（Seedance 2.5 第一帧过锐，默认 1）
  --tail N   剪掉结尾 N 帧（2.5 最后几帧会突然跳成尾帧的样子）
  --hold N   剪掉结尾 N 帧后，用最后一张好帧补回 N 帧，时长不变（对白、卡点不错位）
  按 BT.601 解码、BT.709 输出（Seedance 的 mp4 按 601 解码颜色才对）；lanczos 放大到 --size 并轻微锐化；24 帧。
  --audio keep 保留片段自带的声音（默认）；mute 静音；给一个音频文件就整轨替换（2.5 常混进不要的配乐）。
  --ambience  每条下面按 分镜.json 的场景铺一层环境底（交付/声音/环境_<场景>.wav，sound 阶段生成），压在 -20 dB，接缝处不断声。
输出 交付/成片/<片名>_粗剪.mp4，切点清单写进 logs/粗剪记录.md。旧文件不覆盖，同名时加序号。
"""
import argparse
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FPS = 24


def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries",
                        "stream=nb_read_packets,r_frame_rate:format=duration", "-of", "json", path], capture_output=True, text=True)
    d = json.loads(r.stdout or "{}")
    st = (d.get("streams") or [{}])[0]
    num, den = (st.get("r_frame_rate") or "24/1").split("/")
    has_a = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", path],
                           capture_output=True, text=True).stdout.strip() != ""
    return float(d.get("format", {}).get("duration", 0)), int(st.get("nb_read_packets", 0)), float(num) / float(den), has_a


def pick(src):
    by = {}
    for f in sorted(os.listdir(src)):
        m = re.match(r"第([\d.]+)条", f)
        if m and f.lower().endswith((".mp4", ".mov")):
            by.setdefault(m.group(1), []).append(os.path.join(src, f))
    out = []
    for n, fs in by.items():
        sel = [f for f in fs if "选" in os.path.basename(f)]
        out.append((n, sel[0] if sel else max(fs, key=os.path.getmtime)))
    return sorted(out, key=lambda x: [int(v) for v in x[0].split(".")])


def uniq(path):
    base, ext = os.path.splitext(path)
    k, p = 1, path
    while os.path.exists(p):
        k += 1
        p = f"{base}_{k}{ext}"
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--src", default="出片")
    ap.add_argument("--head", type=int, default=1)
    ap.add_argument("--tail", type=int, default=0)
    ap.add_argument("--hold", type=int, default=0)
    ap.add_argument("--audio", default="keep")
    ap.add_argument("--size", default="1920x1080")
    ap.add_argument("--out")
    ap.add_argument("--ambience", action="store_true")
    ap.add_argument("--bed-db", type=float, default=-20.0)
    a = ap.parse_args()
    proj = os.path.abspath(a.project)
    src = a.src if os.path.isabs(a.src) else os.path.join(proj, a.src)
    if not os.path.isdir(src):
        sys.exit(f"没有片段目录 {src}：把出好的片段按 第N条.mp4 放进去")
    items = pick(src)
    if not items:
        sys.exit(f"{src} 里没有以 第N条 开头的视频")
    W, H = a.size.split("x")
    tmp = os.path.join(proj, "logs", "_post_tmp")
    os.makedirs(tmp, exist_ok=True)
    log = ["# 粗剪记录", "", f"参数：剪头 {a.head} 帧，剪尾 {a.tail} 帧，补尾 {a.hold} 帧，声音 {a.audio}，{a.size}，{FPS} 帧", "",
           "| 条 | 文件 | 原时长 | 成片时长 | 在成片中的起止 |", "|---|---|---|---|---|"]
    parts, t = [], 0.0
    locs = {}
    bp = os.path.join(proj, "分镜.json")
    if a.ambience and os.path.exists(bp):
        locs = {str(c["n"]): c.get("location") for c in json.load(open(bp, encoding="utf-8")).get("clips", [])}
    for n, f in items:
        bed = os.path.join(proj, "交付", "声音", f"环境_{locs.get(n)}.wav") if locs.get(n) else None
        bed = bed if bed and os.path.exists(bed) else None
        dur, frames, fps, has_a = probe(f)
        start = a.head / fps
        end = max(start + 0.5, dur - a.tail / fps)
        vf = (f"trim=start={start:.4f}:end={end:.4f},setpts=PTS-STARTPTS,fps={FPS},"
              f"scale={W}:{H}:flags=lanczos:in_color_matrix=bt601:out_color_matrix=bt709,unsharp=5:5:0.4,setsar=1")
        if a.hold:
            vf += f",tpad=stop_mode=clone:stop={a.hold}"
        seg = end - start + a.hold / FPS
        out = os.path.join(tmp, f"{n}.mp4")
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", f]
        if bed and a.audio in ("keep", "mute"):
            bf = f"aresample=48000,atrim=0:{seg:.4f},volume={a.bed_db}dB"
            if a.audio == "keep" and has_a:
                af = f"atrim=start={start:.4f}:end={end:.4f},asetpts=PTS-STARTPTS,aresample=48000,apad=whole_dur={seg:.4f}"
                fc = f"[0:v]{vf}[v];[0:a]{af}[a0];[1:a]{bf}[b];[a0][b]amix=inputs=2:duration=first:normalize=0[a]"
            else:
                fc = f"[0:v]{vf}[v];[1:a]{bf},apad=whole_dur={seg:.4f}[a]"
            cmd += ["-stream_loop", "-1", "-i", bed, "-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-c:a", "aac", "-b:a", "192k", "-t", f"{seg:.4f}"]
        elif a.audio == "keep" and has_a:
            af = f"atrim=start={start:.4f}:end={end:.4f},asetpts=PTS-STARTPTS,aresample=48000,apad=whole_dur={seg:.4f}"
            cmd += ["-filter_complex", f"[0:v]{vf}[v];[0:a]{af}[a]", "-map", "[v]", "-map", "[a]", "-c:a", "aac", "-b:a", "192k"]
        else:
            cmd += ["-f", "lavfi", "-t", f"{seg:.4f}", "-i", "anullsrc=r=48000:cl=stereo",
                    "-filter_complex", f"[0:v]{vf}[v]", "-map", "[v]", "-map", "1:a", "-c:a", "aac", "-b:a", "192k", "-shortest"]
        cmd += ["-c:v", "libx264", "-crf", "16", "-preset", "medium", "-pix_fmt", "yuv420p",
                "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", out]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"第{n}条处理失败：{r.stderr[-600:]}")
        real = probe(out)[0]
        log.append(f"| {n} | {os.path.basename(f)}{'（铺环境底）' if bed else ''} | {dur:.2f} 秒 | {real:.2f} 秒 | {t:.2f}–{t + real:.2f} 秒 |")
        t += real
        parts.append(out)
    lst = os.path.join(tmp, "list.txt")
    open(lst, "w", encoding="utf-8").write("".join(f"file '{p}'\n" for p in parts))
    title = os.path.basename(proj)
    final = a.out or uniq(os.path.join(proj, "交付", "成片", f"{title}_粗剪.mp4"))
    os.makedirs(os.path.dirname(final), exist_ok=True)
    concat = ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst]
    if a.audio not in ("keep", "mute"):
        concat += ["-i", a.audio, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest"]
    else:
        concat += ["-c", "copy"]
    r = subprocess.run(concat + ["-movflags", "+faststart", final], capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"拼接失败：{r.stderr[-600:]}")
    log += ["", f"成片：{os.path.relpath(final, proj)}，{probe(final)[0]:.2f} 秒。",
            "抽查：每个切点前后各 3 帧用 `python3 tools/pipeline.py qc` 或肉眼看；还没做的：按首帧调色匹配、转场、混音（docs/21 第五节）。"]
    open(os.path.join(proj, "logs", "粗剪记录.md"), "w", encoding="utf-8").write("\n".join(log) + "\n")
    for p in parts:
        os.remove(p)
    os.remove(lst)
    print("\n".join(log))


if __name__ == "__main__":
    main()
