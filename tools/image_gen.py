#!/usr/bin/env python3
"""按《资产提示词》文档批量出图：自动按每张图的"推荐模型"选引擎，按已配置的 API 选接口，处理参考图依赖。

用法：
  python3 -I tools/image_gen.py <资产提示词.md> --out <输出目录> [--engine auto|image25|banana|seedream|mj]
                                [--provider duomi|openai|compat|google|ark] [--only 1,3] [--force] [--dry-run]
  python3 -I tools/image_gen.py --providers        # 看哪些接口已配好密钥

引擎（写法见 docs/10）：image25 = GPT Image（```text 代码块），banana = Nano Banana（```banana），
seedream = 火山 Seedream（```seedream，没有就用 ```banana），mj = Midjourney（```mj，仅多米）。
--engine auto（默认）：读出图清单的"推荐模型"列；没有这一列就按"类型"查 config/image_providers.json 的推荐表；
推荐的引擎没有配好接口或文档里没有对应代码块时，顺延到推荐表里的下一个。

密钥只从环境变量或 .env 读（见 .env.example）：DUOMI_API_KEY、OPENAI_API_KEY、COMPAT_API_KEY + COMPAT_BASE_URL、
GEMINI_API_KEY、ARK_API_KEY。已存在的输出默认跳过（--force 重出）；每张图旁写一个 .json 记录提示词、参考图、接口和任务 id。
付费接口：每张图都会计费，先用 --dry-run 看清会出哪些图、走哪个接口。
"""
import argparse
import base64
import json
import mimetypes
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = json.load(open(os.path.join(ROOT, "config", "image_providers.json"), encoding="utf-8"))
ALIASES = {"gpt": "image25", "image2.5": "image25", "gpt-image": "image25", "nano-banana": "banana", "gemini": "banana",
           "即梦": "seedream", "midjourney": "mj"}


# ---------- 配置与密钥 ----------

def load_env():
    for d in (os.getcwd(), ROOT):
        p = os.path.join(d, ".env")
        if not os.path.exists(p):
            continue
        for line in open(p, encoding="utf-8"):
            m = re.match(r"\s*([A-Z0-9_]+)\s*=\s*(.*?)\s*$", line)
            if m and not line.lstrip().startswith("#"):
                os.environ.setdefault(m.group(1), m.group(2).strip("'\""))


def key_for(provider):
    env = CFG["providers"][provider]["key_env"]
    k = os.environ.get(env, "").strip()
    if not k and provider == "duomi" and os.environ.get("DUOMI_KEY_FILE"):
        raw = open(os.path.expanduser(os.environ["DUOMI_KEY_FILE"]), "rb").read()
        txt = next((raw.decode(e) for e in ("utf-8", "gbk") if _decodes(raw, e)), "")
        m = re.search(r"API[^:：]*[:：]\s*(\S+)", txt)
        k = m.group(1) if m else ""
    if provider == "compat" and not os.environ.get("COMPAT_BASE_URL"):
        return ""
    return k


def _decodes(raw, enc):
    try:
        raw.decode(enc)
        return True
    except UnicodeDecodeError:
        return False


def base_url(provider):
    p = CFG["providers"][provider]
    return (os.environ.get(p.get("base_url_env", "")) or p["base_url"]).rstrip("/")


def provider_for(engine, forced=None):
    for pc in CFG["engines"][engine]["providers"]:
        if forced and pc["provider"] != forced:
            continue
        if forced or key_for(pc["provider"]):
            model = os.environ.get(pc.get("model_env", ""), "") or pc["model"]
            return dict(pc, model=model)
    return None


# ---------- 读文档 ----------

def parse_doc(path):
    t = open(path, encoding="utf-8").read()
    table, cols = {}, None
    for line in t.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if "文件名" in "".join(cells) and "序" in cells[0]:
            cols = cells
            continue
        if cols and cells and cells[0].isdigit():
            row = dict(zip(cols, cells))
            get = lambda *names: next((v for k, v in row.items() if any(n in k for n in names)), "")
            fname = re.search(r"[^\s（(]+\.(?:png|jpg|jpeg|webp)", get("文件名"))
            if not fname:
                continue
            table[int(cells[0])] = {"tag": get("标签"), "file": fname.group(0), "type": get("类型"),
                                    "rec": get("推荐模型", "出图模型"),
                                    "deps": [int(x) for x in re.findall(r"\d+", get("先要", "依赖"))]}
    for m in re.finditer(r"^### (\d+)｜.*?\n(.*?)(?=^### |^## |\Z)", t, re.M | re.S):
        n = int(m.group(1))
        if n not in table:
            continue
        for lang in ("text", "banana", "seedream", "mj"):
            b = re.search(rf"```{lang}\n(.*?)\n```", m.group(2), re.S)
            if b:
                table[n][lang] = b.group(1)
    return table


def engine_from_text(s):
    s = s.lower()
    for k, e in (("seedream", "seedream"), ("即梦", "seedream"), ("banana", "banana"), ("gemini", "banana"),
                 ("midjourney", "mj"), ("mj", "mj"), ("image 2.5", "image25"), ("image2.5", "image25"),
                 ("gpt", "image25"), ("image25", "image25")):
        if k in s:
            return e
    return None


def candidates(item):
    rec = engine_from_text(re.split(r"[／/（(；;，,]", item.get("rec", ""))[0])  # 只认第一个模型名，后面是理由和备选
    typ = re.sub(r"[\s\d]", "", item.get("type", ""))
    by_type = next((v for k, v in CFG["按资产类型推荐"].items() if k in typ), ["image25", "banana", "seedream"])
    order = ([rec] if rec else []) + [e for e in by_type if e != rec]
    return order


def prompt_for(item, engine):
    e = CFG["engines"][engine]
    return item.get(e["提示词代码块"]) or (item.get(e["回退代码块"]) if e.get("回退代码块") else None)


# ---------- HTTP ----------

def http_json(url, headers, body=None, timeout=300):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, headers=dict(headers, **({"Content-Type": "application/json"} if data else {})),
                               method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(r, timeout=timeout) as f:
            return json.loads(f.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}：{e.read().decode(errors='replace')[:500]}")


def http_multipart(url, headers, fields, files, timeout=300):
    bnd = uuid.uuid4().hex
    out = b""
    for k, v in fields.items():
        out += f"--{bnd}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
    for k, path in files:
        mime = mimetypes.guess_type(path)[0] or "image/png"
        out += (f"--{bnd}\r\nContent-Disposition: form-data; name=\"{k}\"; filename=\"{os.path.basename(path)}\"\r\n"
                f"Content-Type: {mime}\r\n\r\n").encode() + open(path, "rb").read() + b"\r\n"
    out += f"--{bnd}--\r\n".encode()
    r = urllib.request.Request(url, data=out, headers=dict(headers, **{"Content-Type": f"multipart/form-data; boundary={bnd}"}), method="POST")
    try:
        with urllib.request.urlopen(r, timeout=timeout) as f:
            return json.loads(f.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}：{e.read().decode(errors='replace')[:500]}")


def poll(fn, limit=1200, every=6):
    t0 = time.time()
    while True:
        time.sleep(every)
        try:
            done = fn()
        except (urllib.error.URLError, TimeoutError):
            done = None
        if done:
            return done
        if time.time() - t0 > limit:
            raise RuntimeError("超时")


def small_ref(path, max_side=2048):
    """内联上传的参考图压到长边 2048 的 JPEG（Gemini/方舟单请求有大小上限）；没装 Pillow 就原样上传。"""
    try:
        from PIL import Image
    except ImportError:
        return open(path, "rb").read(), mimetypes.guess_type(path)[0] or "image/png"
    import io
    im = Image.open(path).convert("RGB")
    im.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=92)
    return buf.getvalue(), "image/jpeg"


# ---------- 各接口 ----------

def duomi_ref_url(key, path):
    meta = json.load(open(os.path.splitext(path)[0] + ".json", encoding="utf-8"))
    if meta.get("url"):
        return meta["url"]
    if meta.get("provider", "duomi") != "duomi":
        raise RuntimeError(f"多米只收 URL 参考图，{os.path.basename(path)} 不是在多米出的：改用 --provider 同一家，或先把它传到图床")
    return http_json(f"{base_url('duomi')}/v1/tasks/{meta['task_id']}", {"Authorization": key})["data"]["images"][0]["url"]


def duomi_task_url(key, tid):
    def check():
        st = http_json(f"{base_url('duomi')}/v1/tasks/{tid}", {"Authorization": key})
        d = st.get("data") or {}
        state = st.get("state") or st.get("status") or d.get("state")
        if state in ("succeeded", "success", "completed") or str(d.get("status")) == "3":
            imgs = d.get("images") or []
            return imgs[0]["url"] if imgs else d.get("image_url")
        if state in ("failed", "error", "canceled", "cancelled"):
            raise RuntimeError(f"任务失败：{json.dumps(st, ensure_ascii=False)[:500]}")
    return poll(check)


def call_duomi(engine, pc, key, prompt, refs, log):
    h = {"Authorization": key}
    b = base_url("duomi")
    urls = [duomi_ref_url(key, r) for r in refs]
    if engine == "image25":
        body = {"model": pc["model"], "prompt": prompt, "size": pc.get("size", "3840x2160"), "n": 1}
        if urls:
            body["image"] = urls
        res = http_json(f"{b}/v1/images/generations?async=true", h, body)
        tid = res.get("id") or res.get("task_id") or (res.get("data") or {}).get("id")
    elif engine == "banana":
        body = {"model": pc["model"], "prompt": prompt, "image_size": pc.get("image_size", "4K"), "aspect_ratio": pc.get("aspect", "16:9")}
        if urls:
            body["image_urls"] = urls
        res = http_json(f"{b}/api/gemini/nano-banana{'-edit' if urls else ''}", h, body)
        tid = (res.get("data") or {}).get("task_id")
    elif engine == "mj":
        res = http_json(f"{b}/api/midjourney/imagine/fast", h, {"action": "generate", "prompt": " ".join(urls + [prompt])})
        tid = (res.get("data") or {}).get("task_id")
        log["task_id"] = tid

        def feed():
            d = http_json(f"{b}/api/midjourney/feed?task_id={tid}", h).get("data") or {}
            if d.get("state") == "succeeded":
                return d["image_url"]
            if d.get("state") in ("error", "failed"):
                raise RuntimeError(f"任务失败：{d.get('msg')}")
        return {"url": poll(feed)}
    else:
        raise RuntimeError(f"多米不支持引擎 {engine}")
    if not tid:
        raise RuntimeError(f"提交无任务 id：{json.dumps(res, ensure_ascii=False)[:400]}")
    log["task_id"] = tid
    return {"url": duomi_task_url(key, tid)}


def call_openai(engine, pc, key, prompt, refs, log, provider="openai"):
    b = base_url(provider)
    h = {"Authorization": f"Bearer {key}"}
    if refs:
        res = http_multipart(f"{b}/images/edits", h, {"model": pc["model"], "prompt": prompt, "size": pc.get("size", "1536x1024"), "n": "1"},
                             [("image[]", r) for r in refs])
    else:
        res = http_json(f"{b}/images/generations", h, {"model": pc["model"], "prompt": prompt, "size": pc.get("size", "1536x1024"), "n": 1})
    d = (res.get("data") or [{}])[0]
    if d.get("b64_json"):
        return {"bytes": base64.b64decode(d["b64_json"])}
    if d.get("url"):
        return {"url": d["url"]}
    raise RuntimeError(f"没有返回图片：{json.dumps(res, ensure_ascii=False)[:400]}")


def call_google(engine, pc, key, prompt, refs, log):
    parts = [{"text": prompt}]
    for r in refs:
        data, mime = small_ref(r)
        parts.append({"inline_data": {"mime_type": mime, "data": base64.b64encode(data).decode()}})
    body = {"contents": [{"parts": parts}],
            "generationConfig": {"responseModalities": ["IMAGE"],
                                 "imageConfig": {"aspectRatio": pc.get("aspect", "16:9"), "imageSize": pc.get("image_size", "4K")}}}
    res = http_json(f"{base_url('google')}/models/{pc['model']}:generateContent", {"x-goog-api-key": key}, body)
    for c in res.get("candidates", []):
        for p in (c.get("content") or {}).get("parts", []):
            inline = p.get("inlineData") or p.get("inline_data")
            if inline and inline.get("data"):
                return {"bytes": base64.b64decode(inline["data"])}
    raise RuntimeError(f"没有返回图片（可能被安全策略拦下）：{json.dumps(res, ensure_ascii=False)[:500]}")


def call_ark(engine, pc, key, prompt, refs, log):
    body = {"model": pc["model"], "prompt": prompt, "size": pc.get("size", "4K"), "response_format": "url",
            "watermark": False, "sequential_image_generation": "disabled"}
    if refs:
        uris = []
        for r in refs:
            data, mime = small_ref(r)
            uris.append(f"data:{mime};base64,{base64.b64encode(data).decode()}")
        body["image"] = uris[0] if len(uris) == 1 else uris
    res = http_json(f"{base_url('ark')}/images/generations", {"Authorization": f"Bearer {key}"}, body)
    d = (res.get("data") or [{}])[0]
    if d.get("url"):
        return {"url": d["url"]}
    if d.get("b64_json"):
        return {"bytes": base64.b64decode(d["b64_json"])}
    raise RuntimeError(f"没有返回图片：{json.dumps(res, ensure_ascii=False)[:400]}")


CALLS = {"duomi": call_duomi, "openai": call_openai, "google": call_google, "ark": call_ark,
         "compat": lambda *a: call_openai(*a, provider="compat")}


# ---------- 保存 ----------

def image_size(data):
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", data[16:24])
    if data[:3] == b"\xff\xd8\xff":
        i = 2
        while i < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return w, h
            i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
    return None


def save(data, dst):
    """平台常返回 JPEG/WebP：转成真正的 PNG（Pillow 或 macOS sips），都没有就按原格式另存并改扩展名。"""
    is_png = data[:8] == b"\x89PNG\r\n\x1a\n"
    if is_png or not dst.lower().endswith(".png"):
        open(dst, "wb").write(data)
        return dst
    try:
        from PIL import Image
        import io
        Image.open(io.BytesIO(data)).save(dst, "PNG")
        return dst
    except ImportError:
        pass
    tmp = dst + ".tmp"
    open(tmp, "wb").write(data)
    if shutil.which("sips"):
        subprocess.run(["sips", "-s", "format", "png", tmp, "--out", dst], capture_output=True)
        os.remove(tmp)
        return dst
    ext = ".jpg" if data[:3] == b"\xff\xd8\xff" else ".webp"
    alt = dst[:-4] + ext
    os.replace(tmp, alt)
    print(f"  没有 Pillow 也没有 sips，按原格式保存为 {os.path.basename(alt)}（pip install pillow 可自动转 PNG）")
    return alt


# ---------- 主流程 ----------

def show_providers():
    print("接口密钥状态：")
    for name, p in CFG["providers"].items():
        ok = bool(key_for(name))
        print(f"  {'✓' if ok else '·'} {name:7s} {p['名称']}（{p['key_env']}{' + ' + p['base_url_env'] if name == 'compat' else ''}）")
    print("\n引擎可用的接口：")
    for e, ec in CFG["engines"].items():
        pc = provider_for(e)
        print(f"  {e:9s} {ec['名称']}：{pc['provider'] + ' / ' + pc['model'] if pc else '未配置'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("doc", nargs="?")
    ap.add_argument("--out")
    ap.add_argument("--engine", default="auto")
    ap.add_argument("--provider", choices=list(CFG["providers"]))
    ap.add_argument("--only", default="")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="只列出每张图会走的引擎、接口和参考图，不调用、不计费")
    ap.add_argument("--providers", action="store_true", help="看哪些接口已配好密钥")
    a = ap.parse_args()
    load_env()
    if a.providers:
        show_providers()
        return
    if not a.doc or not a.out:
        ap.error("需要 <资产提示词.md> 和 --out")
    os.makedirs(a.out, exist_ok=True)
    table = parse_doc(a.doc)
    if not table:
        sys.exit("文档里没找到出图清单（表头要有「序」「文件名」两列）")
    only = {int(x) for x in a.only.split(",") if x.strip()} or set(table)
    forced = ALIASES.get(a.engine, a.engine)
    for n in sorted(only):
        it = table.get(n)
        if not it:
            continue
        order = [forced] if forced != "auto" else candidates(it)
        choice = None
        for e in order:
            pc = provider_for(e, a.provider)
            if (pc or a.dry_run) and prompt_for(it, e):
                choice = (e, pc)
                break
        if not choice:
            print(f"[{n}] {it['tag']}：引擎 {order} 都没有可用接口或对应提示词代码块，跳过", flush=True)
            continue
        engine, pc = choice
        dst = os.path.join(a.out, it["file"])
        refs = [os.path.join(a.out, table[d]["file"]) for d in it["deps"] if d in table]
        where = f"{pc['provider']} / {pc['model']}" if pc else "未配置密钥"
        if a.dry_run:
            print(f"[{n}] {it['tag']}（{it['type']}）→ {CFG['engines'][engine]['名称']}｜{where}｜参考 {[os.path.basename(r) for r in refs] or '无'}｜提示词 {len(prompt_for(it, engine))} 字")
            continue
        if os.path.exists(dst) and not a.force:
            print(f"[{n}] 已存在，跳过：{it['file']}", flush=True)
            continue
        missing = [r for r in refs if not os.path.exists(r)]
        if missing:
            print(f"[{n}] 缺参考图 {[os.path.basename(m) for m in missing]}，先出它们", flush=True)
            continue
        key = key_for(pc["provider"])
        prompt = prompt_for(it, engine)
        log = {"n": n, "tag": it["tag"], "engine": engine, "provider": pc["provider"], "model": pc["model"],
               "refs": [os.path.basename(r) for r in refs], "prompt": prompt}
        for attempt in (1, 2):
            try:
                print(f"[{n}] {it['tag']} → {CFG['engines'][engine]['名称']}（{where}）第 {attempt} 次…", flush=True)
                res = CALLS[pc["provider"]](engine, pc, key, prompt, refs, log)
                if res.get("url"):
                    log["url"] = res["url"]
                    with urllib.request.urlopen(res["url"], timeout=300) as f:
                        res["bytes"] = f.read()
                wh = image_size(res["bytes"])
                if engine == "image25" and pc["provider"] == "duomi" and attempt == 1 and wh and wh[0] < int(pc.get("size", "3840x2160").split("x")[0]) * 0.9:
                    raise RuntimeError(f"尺寸只有 {wh[0]}x{wh[1]}，重出")  # sunburst 偶尔不按尺寸出
                out = save(res["bytes"], dst)
                log["pixels"] = f"{wh[0]}x{wh[1]}" if wh else "?"
                json.dump(log, open(os.path.splitext(out)[0] + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
                print(f"[{n}] 完成：{out}（{log['pixels']}）", flush=True)
                break
            except Exception as e:  # noqa: BLE001
                print(f"[{n}] 出错：{e}", flush=True)
                if attempt == 2:
                    log["error"] = str(e)
                    json.dump(log, open(os.path.splitext(dst)[0] + ".error.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
