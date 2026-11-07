#!/usr/bin/env python3
"""自动出片（docs/18 第六节）：把 Seedance 投喂包按条号顺序提交给 APIMart 的 seedance-2.5，下载成片，接下一条的尾帧，最后粗剪。

  python3 tools/produce.py projects/<项目> plan                 只算：每条多少秒、参考视频多少秒、预计多少钱，不调用、不计费
  python3 tools/produce.py projects/<项目> next [--res 720p]    出下一条（按条号顺序，已出的跳过），出完停下等目检
  python3 tools/produce.py projects/<项目> all  [--res 720p]    一路出完（每条之间照样截尾帧、重编下一条）
  python3 tools/produce.py projects/<项目> resume              接着轮询上次没等完的任务
  python3 tools/produce.py projects/<项目> post                全部出完后粗剪成片（tools/post.py --ambience）

付费闸门：production.json 里 budget.video.approved（元）必须覆盖预计花费；由用户确认后 `pipeline.py approve <项目> video <元>` 写入。
密钥只从 .env 读 APIMART_API_KEY。参考图和白模先用 APIMart 的上传接口换成公网 URL（免费，72 小时 2000 个），按文件指纹缓存在 logs/上传缓存.json。
同一场连续的戏：上一条出完，用接口返回的最后一帧（return_last_frame）存成 交付/衔接/第N条_尾帧.png，再跑一遍流水线重编下一条，尾帧就作为参考图进去了。
每条出完：成片放 出片/第N条.mp4，跑 `pipeline.py qc` 量时长、切点、音量，写 logs/出片记录.md 和 production.json（任务号、花费）。
"""
import argparse
import hashlib
import json
import mimetypes
import os
import re
import subprocess
import sys
import time
import urllib.request
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://api.apimart.ai/v1"
MODEL = "seedance-2.5"
# 720p：1280×720×24÷1024 = 21600 token / 秒；计费秒数 = 输出秒数 + 参考视频秒数（≤30）。单价以账单为准，见 config/prices.json
TOKENS_PER_SEC = {"480p": 854 * 480 * 24 / 1024, "720p": 1280 * 720 * 24 / 1024, "1080p": 1920 * 1080 * 24 / 1024}
RISKY = re.compile(r"编辑|延长|续写|删除|替换|继续生成")  # APIMart：提示词里有这类词会被判成编辑 / 延长任务，尺寸和时长被强制改掉


def load_env():
    p = os.path.join(ROOT, ".env")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            m = re.match(r"\s*([A-Z0-9_]+)\s*=\s*(.*?)\s*$", line)
            if m and not line.lstrip().startswith("#") and m.group(2):
                os.environ.setdefault(m.group(1), m.group(2).strip("'\""))
    if not os.environ.get("APIMART_API_KEY"):
        sys.exit("没有 APIMART_API_KEY：在 .env 里填上（不要贴在对话里）")
    return os.environ["APIMART_API_KEY"]


def price():
    cfg = json.load(open(os.path.join(ROOT, "config", "prices.json"), encoding="utf-8"))
    it = next((v for v in cfg["视频"] if v.get("model") == "seedance_apimart"), None)
    return it or {"每百万token_含视频输入": 42.0, "币种": "CNY", "来源": "火山方舟官方价（含视频输入），APIMart 以账单为准"}


def http_json(method, url, key, body=None, timeout=120):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, method=method,
                                 headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def upload(path, key, cache):
    h = hashlib.sha256(open(path, "rb").read()).hexdigest()
    if h in cache and cache[h].get("expires", 0) > time.time():
        return cache[h]["url"]
    kind = "videos" if path.lower().endswith((".mp4", ".mov", ".webm")) else "images"
    src = path
    if kind == "images" and os.path.getsize(path) > 25 * 1024 * 1024:  # 上限 30 MB：先压成 jpg
        src = os.path.splitext(path)[0] + "_上传.jpg"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", path, "-q:v", "3", src], check=True)
    boundary = uuid.uuid4().hex
    mime = mimetypes.guess_type(src)[0] or "application/octet-stream"
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{os.path.basename(src)}\"\r\n"
            f"Content-Type: {mime}\r\n\r\n").encode() + open(src, "rb").read() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(f"{API}/uploads/{kind}", data=body, method="POST",
                                 headers={"Authorization": "Bearer " + key, "Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=300) as r:
        url = json.loads(r.read().decode())["url"]
    cache[h] = {"url": url, "file": os.path.basename(path), "expires": time.time() + 70 * 3600}
    return url


def packs(proj):
    root = os.path.join(proj, "交付", "投喂包", "seedance")
    if not os.path.isdir(root):
        sys.exit("还没有 Seedance 投喂包：先跑 `pipeline.py run` 到 compile")
    out = []
    for d in os.listdir(root):
        m = re.match(r"第([\d.]+)条(?:_(\d+))?$", d)
        if m:
            out.append((m.group(1), int(m.group(2) or 0), os.path.join(root, d)))
    return sorted(out, key=lambda x: ([int(v) for v in x[0].split(".")], x[1]))


def pack_info(pack):
    req = json.load(open(os.path.join(pack, "api_request.json"), encoding="utf-8"))
    prompt = open(os.path.join(pack, "提示词.txt"), encoding="utf-8").read().strip()
    imgs = sorted(f for f in os.listdir(pack) if re.match(r"\d\d_", f) and f.lower().endswith((".png", ".jpg", ".jpeg", ".webp")))
    vid = os.path.join(pack, "视频1_白模.mp4")
    dur = req.get("duration") or 0
    vsec = 0.0
    if os.path.exists(vid):
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", vid], capture_output=True, text=True)
        vsec = float(r.stdout.strip() or 0)
    missing = [f for f in os.listdir(pack) if f.endswith((".缺图.txt", ".缺白模.txt"))]
    return {"req": req, "prompt": prompt, "imgs": [os.path.join(pack, f) for f in imgs], "video": vid if os.path.exists(vid) else None,
            "dur": dur, "vsec": min(vsec, 30.0), "missing": missing, "ratio": req.get("ratio", "16:9")}


def estimate(info, res):
    p = price()
    tok = (info["dur"] + info["vsec"]) * TOKENS_PER_SEC[res]
    rate = p.get("每百万token_含视频输入" if info["vsec"] else "每百万token", p.get("每百万token_含视频输入", 42.0))
    return tok, tok / 1e6 * rate, p.get("币种", "CNY")


def state(proj):
    p = os.path.join(proj, "production.json")
    d = json.load(open(p, encoding="utf-8"))
    d.setdefault("budget", {}).setdefault("video", {"approved": 0, "used": 0})
    d.setdefault("video_tasks", {})
    return d


def save(proj, d):
    json.dump(d, open(os.path.join(proj, "production.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def cmd_plan(proj, res):
    rows, total = [], 0.0
    for n, k, pack in packs(proj):
        info = pack_info(pack)
        tok, cost, cur = estimate(info, res)
        total += cost
        warn = []
        if info["missing"]:
            warn.append("缺图或白模")
        if RISKY.search(info["prompt"]):
            warn.append("提示词有'编辑/延长'类词：" + "、".join(sorted(set(RISKY.findall(info["prompt"])))))
        if not float(info["dur"]).is_integer():
            warn.append(f"时长 {info['dur']} 秒不是整数（接口只收 4–30 的整数）")
        done = os.path.exists(os.path.join(proj, "出片", f"第{n}条.mp4"))
        rows.append(f"| {n}{'_' + str(k) if k else ''} | {info['dur']} 秒 | {info['vsec']:.1f} 秒 | {len(info['imgs'])} 张 | {tok / 1e6:.2f} M | {cost:.1f} {cur} | "
                    f"{'已出' if done else '—'} | {'；'.join(warn) or '—'} |")
    p = price()
    text = "\n".join([f"# 出片计划（{MODEL}，{res}，APIMart）", "",
                      f"单价：{p.get('每百万token_含视频输入')} {p.get('币种')} / 百万 token（带参考视频），来源：{p.get('来源')}；**以账单为准**，出完第一条用 data.cost 校准。",
                      "计费秒数 = 输出秒数 + 参考视频（白模）秒数；失败和审核拦截全额退款。", "",
                      "| 条 | 输出 | 白模 | 参考图 | token | 预计 | 状态 | 提醒 |", "|---|---|---|---|---|---|---|---|"] + rows +
                     ["", f"**合计约 {total:.0f} {p.get('币种')}**（{len(rows)} 条，按 {res}）。用户确认后：`python3 tools/pipeline.py approve {os.path.relpath(proj, ROOT)} video {int(total * 1.15) + 1}`（留 15% 余量）。"])
    os.makedirs(os.path.join(proj, "logs"), exist_ok=True)
    open(os.path.join(proj, "logs", "出片计划.md"), "w", encoding="utf-8").write(text + "\n")
    print(text)
    return total


def splice_and_recompile(proj, n):
    """上一条出完：如果下一条要接戏而尾帧已经有了，重跑流水线把尾帧编进投喂包。"""
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "pipeline.py"), "run", proj], capture_output=True, text=True)
    tail = (r.stdout + r.stderr).strip().splitlines()[-3:]
    print("重编投喂包：" + " / ".join(tail))


def poll(key, tid, timeout=3600):
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = http_json("GET", f"{API}/tasks/{tid}", key)
        st = (r.get("data") or {}).get("status")
        if st in ("completed", "failed"):
            return r
        time.sleep(15)
    return None


def finish(proj, d, n, pack, tid, r):
    data = r.get("data") or {}
    if data.get("status") != "completed":
        d["video_tasks"][n] = {"task": tid, "status": "failed", "error": json.dumps(data.get("error") or data, ensure_ascii=False)[:400]}
        save(proj, d)
        sys.exit(f"第{n}条失败（失败任务全额退款）：{d['video_tasks'][n]['error']}")
    vids = (data.get("result") or {}).get("videos") or []
    url = vids[0]["url"][0] if isinstance(vids[0]["url"], list) else vids[0]["url"]
    os.makedirs(os.path.join(proj, "出片"), exist_ok=True)
    dst = os.path.join(proj, "出片", f"第{n}条.mp4")
    urllib.request.urlretrieve(url, dst)
    json.dump(r, open(os.path.join(pack, f"结果_{tid}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    lf = vids[0].get("last_frame_url")
    if lf:
        tail = os.path.join(proj, "交付", "衔接", f"第{n}条_尾帧.png")
        os.makedirs(os.path.dirname(tail), exist_ok=True)
        urllib.request.urlretrieve(lf[0] if isinstance(lf, list) else lf, tail)
    else:
        subprocess.run([sys.executable, os.path.join(ROOT, "tools", "pipeline.py"), "splice", proj, n, dst], capture_output=True)
    cost = data.get("cost")
    d["video_tasks"][n] = {"task": tid, "status": "completed", "cost_usd": cost, "file": os.path.relpath(dst, proj), "at": time.strftime("%Y-%m-%d %H:%M")}
    d["budget"]["video"]["used"] = round(d["budget"]["video"].get("used", 0) + (cost or 0) * 7.2, 2)  # 账单是美元，按 7.2 粗折人民币记账
    save(proj, d)
    qc = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "pipeline.py"), "qc", proj, f"第{n}条", dst], capture_output=True, text=True)
    log = os.path.join(proj, "logs", "出片记录.md")
    with open(log, "a", encoding="utf-8") as f:
        f.write(f"| 第{n}条 | 第 1 抽（自动） | 待审 | {tid} | 花费 {cost} USD | {time.strftime('%m-%d %H:%M')} |\n")
    print(f"第{n}条出完：{os.path.relpath(dst, ROOT)}；花费 {cost} USD。机检：{(qc.stdout or qc.stderr).strip().splitlines()[-1:] }")


def produce_one(proj, key, res):
    d = state(proj)
    todo = [(n, k, p) for n, k, p in packs(proj) if not os.path.exists(os.path.join(proj, "出片", f"第{n}条.mp4"))]
    if not todo:
        print("全部出完。NEXT：目检每一条后跑 `python3 tools/produce.py <项目> post` 粗剪")
        return False
    n, k, pack = todo[0]
    if k:
        sys.exit(f"第{n}条在 Seedance 投喂包里被拆成了几段：本工具只提交整条（≤30 秒），先把这一条压到 30 秒内")
    info = pack_info(pack)
    if info["missing"]:
        sys.exit(f"第{n}条投喂包缺素材：{info['missing']}；先出完图 / 白模再 run")
    if RISKY.search(info["prompt"]):
        sys.exit(f"第{n}条提示词里有 {sorted(set(RISKY.findall(info['prompt'])))}：会被当成编辑 / 延长任务，先改数据重编")
    tok, cost, cur = estimate(info, res)
    b = d["budget"]["video"]
    if b.get("used", 0) + cost > b.get("approved", 0):
        sys.exit(f"出片预算不够：已批 {b.get('approved', 0)} 元，已用约 {b.get('used', 0)} 元，这一条约 {cost:.1f} {cur}。"
                 f"先 `produce.py plan` 报给用户，用户确认后 `pipeline.py approve <项目> video <元>`")
    spec = json.load(open(os.path.join(proj, "交付", "规格单", f"第{n}条.json"), encoding="utf-8"))
    sp = spec.get("splice_in")
    if sp and not os.path.exists(os.path.join(proj, "交付", sp["file"])):
        sys.exit(f"第{n}条要接第{sp['from']}条的尾帧，可尾帧还没有：先出第{sp['from']}条")
    if sp and not any("尾帧" in os.path.basename(x) for x in info["imgs"]):
        splice_and_recompile(proj, n)
        info = pack_info(pack)
    cache_p = os.path.join(proj, "logs", "上传缓存.json")
    cache = json.load(open(cache_p, encoding="utf-8")) if os.path.exists(cache_p) else {}
    img_urls = [upload(p, key, cache) for p in info["imgs"]]
    vid_urls = [upload(info["video"], key, cache)] if info["video"] else []
    json.dump(cache, open(cache_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    body = {"model": MODEL, "prompt": info["prompt"], "size": info["ratio"], "resolution": res, "duration": int(round(float(info["dur"]))),
            "image_urls": img_urls, "video_urls": vid_urls, "generate_audio": True, "return_last_frame": True,
            "omni_reference_task_type": "reference", "watermark": False}
    json.dump(dict(body, prompt=body["prompt"][:200] + "…"), open(os.path.join(pack, "提交.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    r = http_json("POST", f"{API}/videos/generations", key, body)
    tid = (r.get("data") or [{}])[0].get("task_id") if isinstance(r.get("data"), list) else (r.get("data") or {}).get("task_id")
    if not tid:
        sys.exit(f"提交失败：{json.dumps(r, ensure_ascii=False)[:500]}")
    d["video_tasks"][n] = {"task": tid, "status": "submitted", "at": time.strftime("%Y-%m-%d %H:%M"), "estimate": round(cost, 1)}
    save(proj, d)
    print(f"第{n}条已提交：任务 {tid}，预计 {cost:.1f} {cur}，轮询中…")
    r = poll(key, tid)
    if r is None:
        sys.exit(f"第{n}条一小时没出完：稍后跑 `produce.py {os.path.relpath(proj, ROOT)} resume`")
    finish(proj, state(proj), n, pack, tid, r)
    return True


def cmd_resume(proj, key):
    d = state(proj)
    for n, t in d["video_tasks"].items():
        if t.get("status") == "submitted":
            pack = next(p for m, _, p in packs(proj) if m == n)
            r = poll(key, t["task"])
            if r is None:
                sys.exit(f"第{n}条还没出完，稍后再 resume")
            finish(proj, state(proj), n, pack, t["task"], r)
    print("没有在等的任务了")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("cmd", choices=["plan", "next", "all", "resume", "post"])
    ap.add_argument("--res", default="720p", choices=list(TOKENS_PER_SEC))
    a = ap.parse_args()
    proj = os.path.abspath(a.project)
    if a.cmd == "plan":
        return cmd_plan(proj, a.res) and 0
    if a.cmd == "post":
        return subprocess.call([sys.executable, os.path.join(ROOT, "tools", "post.py"), proj, "--ambience"])
    key = load_env()
    if a.cmd == "resume":
        return cmd_resume(proj, key)
    if a.cmd == "next":
        produce_one(proj, key, a.res)
        print("NEXT：逐帧目检这一条（docs/04 24 分制，对照白模和参考图），记进 logs/出片记录.md；过了再 `produce.py next`")
        return 0
    while produce_one(proj, key, a.res):
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
