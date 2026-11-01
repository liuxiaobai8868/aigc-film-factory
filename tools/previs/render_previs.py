#!/usr/bin/env python3
"""白模预演一键渲染：镜头规格 JSON → previs_<名>.mp4 + 每镜中点关键帧拼图。

用法：
    python3 tools/previs/render_previs.py <spec.json> --out <输出目录> [--stills-only]

需要：Blender 4.x（环境变量 BLENDER_BIN，或 macOS 默认路径，或 PATH 里的 blender）和 ffmpeg。
先用 --stills-only 看每镜构图，对了再渲全片。
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def blender_bin():
    cands = [os.environ.get("BLENDER_BIN"),
             "/Applications/Blender.app/Contents/MacOS/Blender",
             shutil.which("blender"),
             r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe"]
    for c in cands:
        if c and os.path.exists(c):
            return c
    sys.exit("找不到 Blender：安装 Blender 4.x，或设置环境变量 BLENDER_BIN 指向可执行文件")


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"命令失败：{' '.join(cmd[:3])}…\n{r.stderr[-2000:] or r.stdout[-2000:]}")
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--out", required=True)
    ap.add_argument("--stills-only", action="store_true")
    a = ap.parse_args()
    spec = json.load(open(a.spec, encoding="utf-8"))
    name = spec.get("name", os.path.splitext(os.path.basename(a.spec))[0])
    os.makedirs(a.out, exist_ok=True)
    if not shutil.which("ffmpeg"):
        sys.exit("找不到 ffmpeg：请先安装（macOS: brew install ffmpeg）")
    bl = blender_bin()
    tmp = tempfile.mkdtemp(prefix="previs_")
    script = os.path.join(HERE, "build_from_spec.py")
    stills = os.path.join(tmp, "stills")
    run([bl, "-b", "--factory-startup", "-P", script, "--", os.path.abspath(a.spec), stills, "--stills"])
    n = len(glob.glob(os.path.join(stills, "still_*.png")))
    cols = min(n, 4)
    rows = (n + cols - 1) // cols
    sheet = os.path.join(a.out, f"previs_{name}_关键帧.png")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", os.path.join(stills, "still_%02d.png"),
         "-vf", f"scale=640:-1,tile={cols}x{rows}:padding=6:color=white", "-frames:v", "1", sheet])
    print(f"关键帧拼图：{sheet}（{n} 个镜头，每镜取中点）")
    if a.stills_only:
        return
    frames = os.path.join(tmp, "frames")
    run([bl, "-b", "--factory-startup", "-P", script, "--", os.path.abspath(a.spec), frames])
    fps = spec.get("fps", 24)
    mp4 = os.path.join(a.out, f"previs_{name}.mp4")
    run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", os.path.join(frames, "f_%04d.png"),
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", mp4])
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"预演视频：{mp4}（{spec['duration']} 秒，{fps}fps）")


if __name__ == "__main__":
    main()
