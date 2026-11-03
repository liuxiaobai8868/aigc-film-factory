#!/usr/bin/env python3
"""镜头规格单 → 四家视频模型的投喂包（网页手动出片用）和 API 请求（脚本出片用）。

用法：
  python3 -I tools/compile/compile_video.py <规格单.json> --model seedance|kling|hailuo|wan [--style lean|full] [--out <投喂包根目录>]
  python3 -I tools/compile/compile_video.py <规格单目录> --model all          # 整部片、四个模型一次出

每个投喂包是一个文件夹：
  01_xxx.png …     按上传顺序编号的参考图（复制件，网页上照编号顺序上传就不会错位）
  视频1_白模.mp4    白模预演（海螺、万相按切点截成 ≤15 秒的子段）
  提示词.txt        整段复制进提示词框
  界面参数.txt      模型、模式、时长、分辨率、比例、声音
  api_request.json  该家 API 的请求体（素材是本地路径占位，提交脚本 tools/video_submit.py 负责换成 URL 或 Base64）
  检查.txt          本模型的硬限制核对结果（时长、素材数、字数）

写法规则见 docs/13（四家各自的语法与限制）与 docs/14（规格单格式）。--style lean 是默认：
只保留素材职责、人数、轴线、时间轴、声音与约束，长描述锁交给参考图（Seedance 官方建议中文 ≤500 字，信息越多越容易被忽略）；
--style full 额外带上空间地图与角色描述锁。
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import model_prompts as MP  # noqa: E402

LIMITS = {  # docs/13 第一节，2026-11 官方
    "seedance": {"名称": "Seedance 2.5（即梦 / 火山方舟）", "dur": (4, 30), "images": 30, "videos": 10, "video_total": 30, "chars": 5000, "lean_target": 1500},
    "kling": {"名称": "可灵 4.0（全能参考）", "dur": (3, 30), "images": 10, "videos": 5, "video_total": 30, "chars": 8000, "lean_target": 2500},
    "hailuo": {"名称": "海螺 03 / MiniMax H3（全能参考 Ref2VA）", "dur": (4, 15), "images": 9, "videos": 3, "video_total": 15, "chars": 7000, "lean_target": 4000,
               "words": (350, 500)},
    "wan": {"名称": "万相 3.0（参考生视频）", "dur": (2, 15), "images": 10, "videos": 5, "video_total": 15, "chars": 20000, "lean_target": 1500},
}
SPLIT_MAX = {"seedance": 30, "kling": 30, "hailuo": 15, "wan": 15}


def fmt(x):
    return f"{x:g}"


# ---------- 规格单 ----------

def load_spec(path):
    s = json.load(open(path, encoding="utf-8"))
    s["_dir"] = os.path.dirname(os.path.dirname(os.path.abspath(path)))  # 规格单/ 的上一级 = 交付/
    return s


def split_by_cuts(spec, maxlen):
    """按硬切点把一条拆成若干个 ≤ maxlen 秒的子条；每个子条的时间轴从 0 开始。返回 [(t0, t1, shots)]。"""
    parts, cur, start = [], [], 0.0
    for sh in spec["shots"]:
        if cur and sh["t1"] - start > maxlen:
            parts.append((start, cur[-1]["t1"], cur))
            cur, start = [], sh["t0"]
        if sh["t1"] - sh["t0"] > maxlen:
            sys.exit(f"第 {spec['clip']} 条镜头 {sh['id']} 单镜 {sh['t1'] - sh['t0']:g} 秒，超过该模型单条上限 {maxlen} 秒：先在规格单里拆镜")
        cur.append(sh)
    if cur:
        parts.append((start, cur[-1]["t1"], cur))
    return parts


MIN_DUR = {"seedance": 4, "kling": 3, "hailuo": 4, "wan": 2}


def split_for(spec, model):
    """按模型拆条；尾段短于该模型下限时并进前一段（并后仍不超上限），并不了就把前一段的最后一镜让给尾段。"""
    parts = split_by_cuts(spec, SPLIT_MAX[model])
    lo, hi = MIN_DUR[model], SPLIT_MAX[model]
    if len(parts) > 1 and parts[-1][1] - parts[-1][0] < lo:
        (a0, a1, sa), (b0, b1, sb) = parts[-2], parts[-1]
        if b1 - a0 <= hi:
            parts[-2:] = [(a0, b1, sa + sb)]
        elif len(sa) > 1 and b1 - sa[-1]["t0"] <= hi and sa[-1]["t0"] - a0 >= lo:
            parts[-2:] = [(a0, sa[-1]["t0"], sa[:-1]), (sa[-1]["t0"], b1, [sa[-1]] + sb)]
    return parts


def lines_of(body):
    return re.findall(r"\{([^}]*)\}", body)


# ---------- 各家的素材叫法 ----------

def ref_name(model, kind, i):
    if model == "seedance":
        return {"image": f"@图片{i}", "video": f"@视频{i}"}[kind]
    if model == "kling":
        return {"image": f"@Image{i}", "video": f"@Video{i}"}[kind]
    if model == "hailuo":
        return {"image": f"参考图{i}", "video": f"参考视频{i}"}[kind]
    return {"image": f"图{i}", "video": f"视频{i}"}[kind]


def short_duty(a, ref):
    """精简版素材职责：一句话说清只取什么。"""
    n = a["name"] or a["tag"].lstrip("@")
    if a["kind"] == "character":
        return f"{ref} 是「{n}」的外观（脸只取右侧大头像，正面全身像的模糊椭圆不是脸；不继承灰底和三视图版式）。"
    if a["kind"] == "human_view":
        return f"{ref} 是人间「{n}」镜头的机位、构图和画里的人与物。"
    if a["kind"] == "crowd":
        return f"{ref} 是「{n}」的群众演员：画面里的路人从这张图里按编号取长相、服装和道具（第 1 排从左到右 1–7，第 2 排 8–14），每人只出现一次；这些人都不是主角；不继承白底和排队版式。"
    if a["kind"] == "prop":
        return f"{ref} 是「{n}」的外形与材质（不继承灰底与并排版式）。"
    return f"{ref} 是「{n}」的空间、材质和光（不作首帧，不继承构图）。"


def convert_refs(text, model, n_images):
    """把规格单里 Seedance 写法的 @图片N / @视频1 换成目标模型的叫法。"""
    text = re.sub(r"@图片(\d+)", lambda m: ref_name(model, "image", int(m.group(1))), text)
    return re.sub(r"@视频(\d+)", lambda m: ref_name(model, "video", int(m.group(1))), text)


def dialogue(text, model):
    """台词：Seedance 用 {台词}；其余三家用中文引号。"""
    if model == "seedance":
        return text
    return re.sub(r"\{([^}]*)\}", r"“\1”", text)


# ---------- 提示词 ----------

def shot_line(model, sh, t0, idx):
    a, b = sh["t0"] - t0, sh["t1"] - t0
    body = dialogue(sh["body"], model)
    if model == "seedance":
        return f"{fmt(a)}–{fmt(b)} 秒｜镜头{sh['id']} {sh['name']}（同预演 {fmt(a)}–{fmt(b)} 秒）：{body}"
    if model == "kling":
        return f"SHOT {idx} — {a:.1f}–{b:.1f}s（同 @Video1 的 {fmt(a)}–{fmt(b)} 秒）｜{sh['name']}：{body}"
    if model == "hailuo":
        return f"{fmt(a)}–{fmt(b)} 秒（同参考视频1 的 {fmt(a)}–{fmt(b)} 秒）｜{sh['name']}：{body}"
    return f"第{idx}个镜头[{fmt(a)}-{fmt(b)}秒]（同视频1 的 {fmt(a)}–{fmt(b)} 秒）｜{sh['name']}：{body}"


def previs_duty(model, spec, vref):
    return (f"{vref} 是本条的白模预演，只提供镜头路线、切点、构图、空间布局、人物整体位置与路线、事件先后；"
            f"外形、识别色、灰色无材质画面和中性光都不继承。识别色：{spec['previs_colors']}。")


def build_prompt(spec, model, style, part):
    t0, t1, shots = part
    imgs = [a for a in spec["assets"]]
    out = []
    head = {"seedance": "【素材职责】", "kling": "【素材职责】", "hailuo": "【参考素材】", "wan": "【参考素材】"}[model]
    out.append(head)
    for i, a in enumerate(imgs, 1):
        ref = ref_name(model, "image", i)
        if style == "full" and model == "seedance":
            out.append(a["duty"].replace("@图片N", ref))
        else:
            out.append(short_duty(a, ref))
    vref = ref_name(model, "video", 1)
    out.append(previs_duty(model, spec, vref))
    out.append("角色外貌、服饰、位置、台词互不交换；画面质感从第一帧开始就按下面的质感描述。")
    out += ["", convert_refs(spec["count"], model, len(imgs))]
    out += ["", "【场景上下文】" if model == "seedance" else "【总体设定】", spec["context"], spec["two_worlds"], spec["style"]]
    axis = [g for g in spec["geo"] if g.startswith("调度轴线")]
    if style == "full":
        out += ["", "【空间地图】"] + spec["geo"] + ["", "【角色】"] + spec["chars"]
    elif axis:
        out += ["", axis[0]]
    cuts = "、".join(fmt(sh["t0"] - t0) for sh in shots[1:])
    dur = t1 - t0
    out += ["", "【摄影规格】" if model == "seedance" else "【镜头】",
            (f"本条只在以下时间点硬切：{cuts} 秒（与预演视频一致），镜头不自行切换；同一个镜头号是同一个机位。每镜一个视场角、一个主运镜。"
             if cuts else "本条是一个连续镜头，中途不切。")]
    out += ["", "【时间轴】" if model in ("seedance", "hailuo", "wan") else "【事件顺序】"]
    for k, sh in enumerate(shots, 1):
        out.append(convert_refs(shot_line(model, sh, t0, k), model, len(imgs)))
    sound = [spec["music"], "现场声：" + spec["sfx"] + "。"]
    if spec["voices"]:
        sound.append("音色：" + "".join(spec["voices"]))
    lip = spec["lip"] if model == "seedance" else spec["lip"].replace("花括号", "引号")
    sound.append(lip)
    if model == "kling":
        sound.append("无字幕。")
    out += ["", "【声音】"] + sound + ["", "【约束】", spec["constraint"]]
    if dur != spec["duration"]:
        out.insert(0, f"（本段是第 {spec['clip']} 条的第 {fmt(t0)}–{fmt(t1)} 秒，单独生成，剪辑时按顺序接回去。）")
    return "\n".join(out)


# ---------- 投喂包 ----------

def cut_video(src, dst, a, b):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", fmt(a), "-i", src, "-t", fmt(b - a), "-c:v", "libx264", "-crf", "18",
                    "-pix_fmt", "yuv420p", "-an", dst], check=True)


def api_request(spec, model, prompt, files, video, dur):
    if model == "seedance":
        content = [{"type": "text", "text": prompt}]
        content += [{"type": "image_url", "image_url": {"url": f"file://{f}"}, "role": "reference_image"} for f in files]
        content.append({"type": "video_url", "video_url": {"url": f"file://{video}"}, "role": "reference_video"})
        return {"_endpoint": "POST https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks",
                "model": "doubao-seedance-2-5-260628", "content": content, "resolution": spec["resolution"], "ratio": spec["ratio"],
                "duration": int(dur), "generate_audio": True, "watermark": False, "omni_reference_task_type": "reference"}
    if model == "hailuo":
        content = [{"type": "text", "text": prompt}]
        content += [{"type": "image_url", "url": {"url": f"file://{f}"}, "role": "reference_image"} for f in files]
        content.append({"type": "video_url", "url": {"url": f"file://{video}"}, "role": "reference_video"})
        return {"_endpoint": "POST https://api.minimax.io/v2/video_generation", "model": "MiniMax-H3", "content": content,
                "resolution": "2K", "duration": int(dur), "ratio": spec["ratio"]}
    if model == "wan":
        media = [{"type": "reference_image", "url": f"file://{f}"} for f in files] + [{"type": "reference_video", "url": f"file://{video}"}]
        return {"_endpoint": "POST https://{WorkspaceId}.{region}.maas.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis",
                "_headers": {"X-DashScope-Async": "enable"}, "model": "wan3.0-video", "input": {"prompt": prompt, "media": media},
                "parameters": {"resolution": spec["resolution"].upper(), "ratio": spec["ratio"], "duration": int(dur), "audio": True,
                               "prompt_extend": False, "watermark": False}}
    return {"_说明": "可灵 4.0 的官方 API 字段尚未核实（官方文档页需登录渲染），先在可灵网页用本投喂包手动出片；字段核实后补上。",
            "mode": "omni_reference", "model": "kling-v4", "prompt": prompt, "images": files, "videos": [video], "duration": int(dur),
            "aspect_ratio": spec["ratio"], "resolution": "1080p"}


def ui_params(spec, model, dur, n_img):
    lim = LIMITS[model]
    rows = [f"模型：{lim['名称']}", f"时长：{fmt(dur)} 秒（必须和白模一样长）", f"比例：{spec['ratio']}"]
    if model == "seedance":
        rows += ["模式：全能参考", f"分辨率：{spec['resolution']}", "声音：开", "不开自动改写",
                 f"上传：先按编号上传 {n_img} 张图（@图片1…），再上传 视频1_白模.mp4（@视频1）"]
    elif model == "kling":
        rows += ["模式：全能参考（Omni Reference）。不要用关键帧入口：关键帧模式不收参考视频，白模用不上", "分辨率：1080p（试错：Kling 4.0 Flash 720p，≤ 20 秒）",
                 "声音：开（可灵默认）", "多镜头：开（默认）；提示词里已写死 SHOT 清单和硬切",
                 f"上传：按编号上传 {n_img} 张图（@Image1…），再上传 视频1_白模.mp4（@Video1）。参考视频单个 3–30 秒"]
    elif model == "hailuo":
        rows += ["模式：全能参考 Ref2VA（参考生视频）。不要同时传首尾帧：首尾帧模式不收参考视频，白模用不上",
                 "分辨率：官方网页 / API 选 2K（试错 768P）；本地部署只有 768P（2K 的 Regenerate 模型没开源）",
                 "提示词：整段粘贴，英文分段格式是 H3 官方 skill 的格式，台词保留中文在 <d>[Chinese] …</d> 里，不要翻译、不要改标签",
                 f"上传：按编号上传 {n_img} 张参考图（对应 <Subject 1…>），再上传 视频1_白模.mp4（<Video 1>）。参考视频 2–15 秒，素材合计 ≤ 12 个",
                 "本地部署（ComfyUI / diffusers，MiniMax-H3 Ref2VA 权重）：同一份提示词和素材，输出 768P、24fps"]
    else:
        rows += ["模式：参考生视频（多模态参考）。不要用首帧 / 首尾帧入口：那两个模式不收参考视频，白模用不上", "分辨率：720P（试错用 480P）",
                 "智能扩写（prompt_extend）：关（开着会改写提示词，分镜和台词会被改）", "声音：开", "输出帧率 30fps（白模 24fps 不影响）",
                 f"上传：按编号上传 {n_img} 张图（图1…），再上传 视频1_白模.mp4（视频1）。参考视频合计 ≤ 15 秒，输入 + 输出 ≤ 30 秒"]
    return "\n".join(rows) + "\n"


def compile_one(spec, model, style, out_root):
    lim = LIMITS[model]
    base = spec["_dir"]
    previs = os.path.join(base, spec["previs"])
    parts = split_for(spec, model)
    made = []
    for k, part in enumerate(parts, 1):
        t0, t1, shots = part
        name = f"第{spec['clip']}条" + (f"_{k}" if len(parts) > 1 else "")
        d = os.path.join(out_root, model, name)
        if os.path.isdir(d):
            shutil.rmtree(d)
        os.makedirs(d)
        assets = spec["assets"][:lim["images"]]
        files = []
        for i, a in enumerate(assets, 1):
            src = os.path.join(base, a["file"])
            dst = os.path.join(d, f"{i:02d}_{os.path.basename(a['file'])}")
            if os.path.exists(src):
                shutil.copy2(src, dst)
            else:  # 图还没出：先占位，出完图重编一次即可
                open(dst + ".缺图.txt", "w", encoding="utf-8").write(f"等待定稿图：{a['file']}\n")
            files.append(dst)
        video = os.path.join(d, "视频1_白模.mp4")
        if not os.path.exists(previs):
            open(video + ".缺白模.txt", "w", encoding="utf-8").write(f"等待白模：{spec['previs']}\n")
        elif len(parts) == 1:
            shutil.copy2(previs, video)
        else:
            cut_video(previs, video, t0, t1)
        notes = []
        if model == "seedance":
            prompt = build_prompt(spec, model, style, part)
        else:
            prompt, fallback = MP.BUILD[model](spec, part, short_duty)
            if fallback:
                notes.append(f"WARN  镜头 {fallback} 没有结构化数据（项目不是 设定.json + 分镜.json 写的），这几镜退回中文正文，不是{lim['名称']}官方格式；改用 docs/19 的数据格式可得到完整官方格式")
        open(os.path.join(d, "提示词.txt"), "w", encoding="utf-8").write(prompt + "\n")
        open(os.path.join(d, "界面参数.txt"), "w", encoding="utf-8").write(ui_params(spec, model, t1 - t0, len(files)))
        json.dump(api_request(spec, model, prompt, files, video, t1 - t0), open(os.path.join(d, "api_request.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        chk = check_limits(spec, model, prompt, t1 - t0, len(spec["assets"]), style) + notes
        missing = [a["file"] for a in assets if not os.path.exists(os.path.join(base, a["file"]))]
        if missing:
            chk.append(f"WAIT  还缺 {len(missing)} 张定稿图：{'、'.join(os.path.basename(m) for m in missing)}；出完图重编一次")
        open(os.path.join(d, "检查.txt"), "w", encoding="utf-8").write("\n".join(chk) + "\n")
        made.append((d, len(prompt), chk))
    return made


def check_limits(spec, model, prompt, dur, n_assets, style):
    lim = LIMITS[model]
    out = []
    lo, hi = lim["dur"]
    out.append(("PASS" if lo <= dur <= hi else "FAIL") + f"  时长 {fmt(dur)} 秒（{lim['名称']} 允许 {lo}–{hi} 秒）")
    out.append(("PASS" if n_assets <= lim["images"] else "FAIL") + f"  参考图 {n_assets} 张（上限 {lim['images']}）"
               + ("：超出的图没有放进投喂包，先在规格单里减图" if n_assets > lim["images"] else ""))
    n = len(prompt)
    out.append(("PASS" if n <= lim["chars"] else "FAIL") + f"  提示词 {n} 字（上限 {lim['chars']}）")
    if lim.get("words"):
        w = MP.english_words(prompt)
        lo_w, hi_w = lim["words"]
        out.append(("PASS" if w <= hi_w * 1.5 else "WARN") + f"  英文 {w} 词（H3 官方：生成任务通常 {lo_w}–{hi_w} 词，台词多时以台词为先）")
    if style == "lean" and n > lim["lean_target"]:
        out.append(f"WARN  精简版仍有 {n} 字，超过建议的 {lim['lean_target']} 字：信息越多越容易被模型忽略，考虑压镜头描述")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec", help="规格单 .json，或整个规格单目录")
    ap.add_argument("--model", required=True, choices=list(LIMITS) + ["all"])
    ap.add_argument("--style", default="lean", choices=["lean", "full"])
    ap.add_argument("--out", default=None, help="投喂包根目录，默认 交付/投喂包")
    a = ap.parse_args()
    paths = sorted(os.path.join(a.spec, f) for f in os.listdir(a.spec) if f.endswith(".json")) if os.path.isdir(a.spec) else [a.spec]
    models = list(LIMITS) if a.model == "all" else [a.model]
    for p in paths:
        spec = load_spec(p)
        out_root = a.out or os.path.join(spec["_dir"], "投喂包")
        for m in models:
            for d, n, chk in compile_one(spec, m, a.style, out_root):
                bad = [c for c in chk if c.startswith("FAIL")]
                print(f"{'FAIL' if bad else 'OK  '} {os.path.relpath(d, spec['_dir'])}  {n} 字" + ("  " + "；".join(bad) if bad else ""))


if __name__ == "__main__":
    main()
