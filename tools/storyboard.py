#!/usr/bin/env python3
"""分镜数据 → 资产文档 + 白模规格 + 镜头规格单（docs/19）。

智能体只填两份 JSON：
  <项目>/设定.json   片名、世界与风格配方、人物、道具、场景（含白模站位）、群像
  <项目>/分镜.json   每条：地点、谁在哪、每镜的类型 / 景别 / 主体 / 台词 / 动作 / 声音
机位坐标、"画面里"的写法、说话人写法、群演点名、过肩轴线、素材清单都由本工具按固定规则算出来，
所以同一份数据交给任何智能体，产物都一样。

  python3 tools/storyboard.py check <项目>     只校验，列出错误和改法（不写文件）
  python3 tools/storyboard.py assets <项目>    校验 + 写 交付/01-资产提示词.md
  python3 tools/storyboard.py specs <项目>     校验 + 写 预演规格/第N条.json 和 交付/规格单/第N条.json
"""
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import projectkit as K  # noqa: E402

REC = "Image 2.5（APIMart 2K）"
SIZES = {"大特写": (135, 0.6, 0.93), "特写": (85, 0.9, 0.92), "近景": (50, 1.4, 0.88), "中景": (50, 2.4, 0.8),
         "全景": (35, 5.0, 0.6), "大全景": (24, 11.0, 0.55)}  # 景别 → (焦距, 机位距离 米, 机位高度占身高比例)
TYPES = ("wide", "single", "ots", "insert", "track", "pov")
MOVE = {"wide": "固定", "single": "固定", "ots": "过肩", "insert": "俯拍特写", "track": "跟拍", "pov": "主观视角"}
PALETTE = [[0.95, 0.8, 0.15], [0.2, 0.35, 0.85], [0.85, 0.2, 0.15], [0.95, 0.6, 0.75], [0.3, 0.75, 0.4], [0.6, 0.35, 0.8]]
PALETTE_ZH = ["黄", "蓝", "红", "粉", "绿", "紫"]
BOXCOLOR = {"wood": [0.35, 0.25, 0.18], "white": [0.92, 0.92, 0.9], "stone": [0.45, 0.47, 0.5], "floor": [0.5, 0.5, 0.52],
            "dark": [0.12, 0.12, 0.14], "red": [0.85, 0.12, 0.1], "gold": [1.0, 0.75, 0.2], "glass": [0.75, 0.8, 0.9]}
LIP = ("对白：普通话，自然口语。所有角色只说花括号里的台词；每句台词只有说话的那一个角色动嘴，其余角色闭着嘴；画外音不对任何人的口型；"
       "人声干净贴近，有人说话时配乐和环境声自动压低。画面全程是纯影像，没有字幕。")
ANCHOR = "人物都是正常的人体结构：两只手各五根手指。"
CROWD_WORDS = re.compile(r"路人|人群|群众|顾客们|村民|行人|正式工们|士兵们|客人们|观众")
HAND_WORDS = re.compile(r"手|拇指|食指|指尖|掌心")
SEP = re.compile(r"[，。！？、…\s\.,!?—~～「」“”\"'（）()]")


class Bad(Exception):
    pass


def load(proj):
    def rd(name):
        p = os.path.join(proj, name)
        if not os.path.exists(p):
            raise Bad(f"缺少 {name}（格式见 docs/19，样例 examples/样例-便利店/）")
        try:
            return json.load(open(p, encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise Bad(f"{name} 不是合法 JSON：{e}")
    return rd("设定.json"), rd("分镜.json")


# ---------------- 校验 ----------------

def validate(bible, board):
    """返回 (errors, warnings)，每条都带"怎么改"。"""
    E, W = [], []
    recipes = {r["id"] for r in json.load(open(os.path.join(ROOT, "config", "style_recipes.json"), encoding="utf-8"))["配方"]}
    for k in ("title", "short", "film", "worlds", "people_recipe", "three", "music", "characters", "locations"):
        if k not in bible:
            E.append(f"设定.json 缺字段 {k}")
    if E:
        return E, W
    for w, v in bible["worlds"].items():
        if v.get("recipe") not in recipes:
            E.append(f"世界「{w}」的 recipe {v.get('recipe')} 不在 config/style_recipes.json（用 tools/mj_style.py --recipes 看）")
    if bible["people_recipe"] not in recipes:
        E.append(f"people_recipe {bible['people_recipe']} 不存在")
    chars = {c["name"]: c for c in bible["characters"]}
    props = {p["name"]: p for p in bible.get("props", [])}
    locs = {l["name"]: l for l in bible["locations"]}
    crowds = {c["world"]: c for c in bible.get("crowds", [])}
    for c in bible["characters"]:
        for k in ("lock", "brief_en", "must_en", "height", "voice"):
            if k not in c:
                E.append(f"人物「{c.get('name')}」缺 {k}")
        if re.search(r"\d+\s*岁|岁的|小孩|孩子|少年|少女", c.get("lock", "")):
            E.append(f"人物「{c['name']}」描述锁写了年龄词，改成'二十出头的成年人'这类写法（不写具体岁数、不写未成年）")
    for l in bible["locations"]:
        for k in ("world", "lock", "en", "must_en", "stage"):
            if k not in l:
                E.append(f"场景「{l.get('name')}」缺 {k}")
        if l.get("world") not in bible["worlds"]:
            E.append(f"场景「{l.get('name')}」的 world 不在 worlds 里")
        st = l.get("stage", {})
        if "establish" not in st or "marks" not in st:
            E.append(f"场景「{l.get('name')}」的 stage 要有 marks（站位点）和 establish（全景机位）")
    for c in bible.get("crowds", []):
        if len(c.get("roster", [])) != 14:
            E.append(f"群像「{c.get('world')}」roster 要正好 14 人（现在 {len(c.get('roster', []))}）")
        for i, r in enumerate(c.get("roster", []), 1):
            if len(r) != 2 or "cm tall" not in r[1]:
                E.append(f"群像「{c.get('world')}」第 {i} 人要写成 [中文一句, 英文一句含 'about NNN cm tall']（docs/17）")
        if c.get("world") not in bible["worlds"]:
            E.append(f"群像的 world「{c.get('world')}」要是 worlds 里的一个世界")
        for n in c.get("refs", []):
            if n not in chars:
                E.append(f"群像「{c.get('world')}」refs 里的 {n} 不是人物")
    if E:
        return E, W
    for clip in board.get("clips", []):
        tag = f"第{clip.get('n')}条"
        loc = clip.get("location")
        if loc not in locs:
            E.append(f"{tag} location「{loc}」不在设定的 locations 里")
            continue
        marks = locs[loc]["stage"]["marks"]
        cast = clip.get("cast", {})
        for name, cv in cast.items():
            if name not in chars:
                E.append(f"{tag} cast 里的「{name}」不是设定里的人物")
            for p in ([cv] if "at" in cv else cv.get("path", [])):
                if isinstance(p.get("at"), str) and p["at"] not in marks:
                    E.append(f"{tag} 「{name}」的站位「{p['at']}」不在场景「{loc}」的 marks 里")
        for p in clip.get("props", []):
            if p not in props:
                E.append(f"{tag} props 里的「{p}」不在设定的 props 里")
        shots = clip.get("shots", [])
        total = sum(s.get("dur", 0) for s in shots)
        if not 4 <= total <= 30:
            E.append(f"{tag} 总时长 {total} 秒，要在 4–30 秒（超过就拆条）")
        pairs = set()
        for k, s in enumerate(shots, 1):
            st = f"{tag} 镜{k}"
            t = s.get("type")
            if t not in TYPES:
                E.append(f"{st} type 要是 {TYPES} 之一")
                continue
            if s.get("dur", 0) < 1.5:
                E.append(f"{st} 时长 {s.get('dur')} 秒，短于 1.5 秒模型做不出来，并到相邻镜头")
            if s.get("size") and s["size"] not in SIZES:
                E.append(f"{st} size 要是 {list(SIZES)} 之一")
            vis = set(s.get("who", []))
            for key in ("subject", "fg"):
                if s.get(key):
                    vis.add(s[key])
            for n in vis:
                if n not in cast:
                    E.append(f"{st} 「{n}」不在本条 cast 里（先在 cast 里给他站位）")
            if t in ("single", "ots", "track", "pov") and not s.get("subject"):
                E.append(f"{st} {t} 镜头要写 subject（拍谁）")
            if t == "ots":
                if not s.get("fg"):
                    E.append(f"{st} 过肩要写 fg（越过谁的肩膀）")
                else:
                    pairs.add(frozenset((s["fg"], s.get("subject"))))
            if t == "wide" and s.get("view") and s["view"] not in locs[loc]["stage"].get("views", {}):
                E.append(f"{st} view「{s['view']}」不在场景 stage.views 里")
            if t == "pov" and not s.get("look"):
                E.append(f"{st} 主观镜头要写 look（看向哪个站位或人物）")
            if t == "insert":
                if s.get("object") not in marks:
                    E.append(f"{st} 插入镜头的 object 要是场景 marks 里的点（拍哪个物件）")
                if s.get("action") and not s.get("hand") and not s.get("no_hand"):
                    E.append(f"{st} 插入镜头有动作，要写 hand：谁的手、什么样的手、袖口什么样（第 1 条实拍教训）；画面里确实没有手就写 no_hand: true")
            acts = s.get("action", [])
            acts = acts if isinstance(acts, list) else [acts]
            line = s.get("line")
            if line:
                txt = line.get("text", "")
                n = len(SEP.sub("", txt))
                if n / s["dur"] > 4.5:
                    E.append(f"{st} 台词 {n} 字 / {s['dur']} 秒 = {n / s['dur']:.1f} 字/秒，超过 4.5，删字或加长镜头")
                mode = line.get("mode", "on")
                who = line.get("who")
                if who not in chars:
                    E.append(f"{st} 台词的 who「{who}」不是人物")
                elif mode == "on" and who not in vis:
                    E.append(f"{st} 说话人「{who}」不在画里：让他入画，或 mode 写 back（背对镜头 / 过肩前景）或 off（画外）")
                elif mode == "back" and who != s.get("fg"):
                    E.append(f"{st} mode=back 只用于过肩镜头的前景人物说话")
                if len(acts) > 1:
                    E.append(f"{st} 对白镜头最多一个动作（现在 {len(acts)} 个），其余挪到别的镜头（第 1 条实拍教训）")
            for a in acts:
                a_txt = a.get("text", "") if isinstance(a, dict) else a
                if CROWD_WORDS.search(a_txt) and not s.get("crowd"):
                    E.append(f"{st} 动作里写到了路人，要用 crowd 点群演编号（docs/17），并在设定里有该世界的群像")
            if s.get("crowd"):
                world = locs[loc]["world"]
                if world not in crowds:
                    E.append(f"{st} 用了群演，但设定里没有世界「{world}」的群像")
                elif any(not 1 <= i <= 14 for i in s["crowd"].get("ids", [])):
                    E.append(f"{st} 群演编号要在 1–14")
            for snd in s.get("sound", []):
                if not isinstance(snd, dict) or not snd.get("source"):
                    E.append(f"{st} 声音要写成 {{\"text\": 声音, \"source\": 画里的发声者 或 \"画外\"}}，模型只给看得见的声源配音（第 1 条实拍教训）")
                elif snd["source"] != "画外" and snd["source"] not in vis and snd["source"] not in marks and not s.get("crowd"):
                    W.append(f"{st} 声音「{snd['text']}」的声源「{snd['source']}」不在画里，模型可能不出声")
        if len(pairs) > 1 and not clip.get("allow_axis_change"):
            E.append(f"{tag} 过肩用了 {len(pairs)} 组人物，轴线会乱；一条里只拍一组对话，或写 allow_axis_change: true 并在镜头里交代换轴")
    return E, W


# ---------------- 资产 ----------------

def _num(names, idx):
    return "、".join(str(idx[n]) for n in names) if names else "—"


def items(bible, board):
    film = bible["film"]
    uses = {}
    for clip in board.get("clips", []):
        loc = clip["location"]
        tags = [f"@{n}" for n in clip.get("cast", {})] + [f"@prop_{p}" for p in clip.get("props", [])] + [f"@loc_{loc}"]
        if any(s.get("crowd") for s in clip["shots"]):
            tags.append("@crowd_" + next(l["world"] for l in bible["locations"] if l["name"] == loc))
        for t in tags:
            uses.setdefault(t, []).append(clip["n"])
    use = lambda t: "第 " + "、".join(uses.get(t, [])) + " 条" if uses.get(t) else "备用"  # noqa: E731
    out, idx = [], {}

    def push(key, it):
        out.append(it)
        idx[key] = len(out)

    for c in bible["characters"]:
        must = f"MUST BE READABLE: {c['must_en']} PORTRAIT: {c.get('portrait_en', 'restrained expression, mouth closed.')}"
        push(c["name"], dict(tag=f"@{c['name']}", world="__people__", file=f"{c['name']}_三视图.png", type="人物三视图", rec=REC, deps="—",
                             use=use(f"@{c['name']}"), lock=c["lock"],
                             en=f"Create a character reference sheet for a {film}: {c['brief_en']}", must=must,
                             check=c.get("check", []) + ["正面全身像的脸模糊成椭圆，右侧大头像清楚", "没有文字"],
                             duty=f"「{c['name']}」：脸只从右侧大头像取；体型和服装从左侧全身像取；正面全身像的模糊椭圆不是脸；不继承灰底和三视图版式。"))
        for v in c.get("variants", []):
            push(v["name"], dict(tag=f"@{v['name']}", world="__people__", file=f"{v['name']}_三视图.png", type="状态变体", rec=REC,
                                 deps=str(idx[c["name"]]), use=use(f"@{v['name']}"), lock=v["lock"],
                                 en=f"Edit Image 1, the character sheet of {c['brief_en']}. Keep the face, body, layout and background exactly the same.",
                                 must=f"Change only: {v['edit_en']}", check=v.get("check", []) + ["脸和版式不变"],
                                 duty=f"「{c['name']}」的另一个状态（{v['name']}）：脸只从右侧大头像取；不继承灰底和三视图版式。"))
    for p in bible.get("props", []):
        dep = [p["ref"]] if p.get("ref") in idx else []
        ref = "The prop must match the one carried by the character in Image 1. " if dep else ""
        push("prop:" + p["name"], dict(tag=f"@prop_{p['name']}", world="__people__", file=f"道具_{p['name']}.png", type="道具", rec=REC,
                                       deps=_num(dep, idx), use=use(f"@prop_{p['name']}"), lock=p["lock"],
                                       en=f"A prop reference for a {film}, on a seamless neutral grey background, three-quarter view: {p['en']} {ref}".strip(),
                                       must=p["must_en"] + " No text, symbols or labels.", check=p.get("check", []) + ["没有文字"],
                                       duty=f"「{p['name']}」：只取外形、材质和状态；不继承灰底。"))
    for l in bible["locations"]:
        hv = l.get("human_view")
        push("loc:" + l["name"], dict(tag=f"@loc_{l['name']}", world=l["world"], file=f"场景_{l['name']}.png",
                                      type="人类视角机位" if hv else "场景主图", rec=REC, deps="—", use=use(f"@loc_{l['name']}"), lock=l["lock"],
                                      en=f"A location reference image for a {film}, no characters: {l['en']}",
                                      must=l["must_en"] + " The scene is completely uninhabited. Full-frame image with no black bars. No readable text or signs.",
                                      check=l.get("check", []) + ["没有人", "没有黑边", "没有文字"],
                                      duty=f"「{l['name']}」：只取空间结构、材质和光；不作首帧，不继承构图。"))
        if l.get("grid"):
            push("grid:" + l["name"], dict(tag=f"@loc_{l['name']}_grid", world=l["world"], file=f"场景_{l['name']}_宫格.png", type="场景宫格", rec=REC,
                                           deps=str(idx["loc:" + l["name"]]), use=use(f"@loc_{l['name']}"), lock=l["lock"],
                                           en="Image 1 is the only visual source. Rebuild the same place in 3D and render one 2x2 four-panel multi-view sheet, 16:9, no people, no text.",
                                           must=l.get("grid_en", "Panel 1: overhead plan. Panel 2: eye-level main view. Panel 3: reverse view. Panel 4: side view. Same materials and light in every panel."),
                                           check=["四格是同一个空间", "没有人、没有字"],
                                           duty=f"「{l['name']}」多视角宫格：保持同一空间的布局和光；不作首帧，不继承宫格版式。"))
    for c in bible.get("crowds", []):
        refs = [n for n in c.get("refs", [])]
        refs_en = (f"Images 1–{len(refs)} are the main characters." if len(refs) > 1 else "Image 1 is a main character.") if refs else ""
        it = K.crowd_item(c["world"], [tuple(r) for r in c["roster"]], f"@crowd_{c['world']}", f"群像_{c['world']}.png", _num(refs, idx),
                          use(f"@crowd_{c['world']}"), c["world"], refs_en, c["world_en"], film)
        push("crowd:" + c["world"], it)
    return out


def style_map(bible):
    rec = {r["id"]: r for r in json.load(open(os.path.join(ROOT, "config", "style_recipes.json"), encoding="utf-8"))["配方"]}
    en = {w: rec[v["recipe"]]["en"] for w, v in bible["worlds"].items()}
    en["__people__"] = rec[bible["people_recipe"]]["en"]
    zh = "；".join(f"{w}（{v['recipe']}）：{rec[v['recipe']]['zh']}" for w, v in bible["worlds"].items())
    zh += f"；人物（{bible['people_recipe']}）：{rec[bible['people_recipe']]['zh']}"
    note = "；".join(f"{w} {v['recipe']} {rec[v['recipe']]['名称']}" for w, v in bible["worlds"].items()) + \
        f"；人物与道具 {bible['people_recipe']} {rec[bible['people_recipe']]['名称']}"
    return en, "质感：" + zh + "。", note


# ---------------- 镜头 ----------------

def _v(a, b):
    return [b[0] - a[0], b[1] - a[1], b[2] - a[2]]


def _lerp(p, q, f):
    return [p[i] + (q[i] - p[i]) * f for i in range(3)]


class Clip:
    def __init__(self, bible, clip, li):
        self.b, self.c = bible, clip
        self.locs = {l["name"]: l for l in bible["locations"]}
        self.chars = {c["name"]: c for c in bible["characters"]}
        self.loc = self.locs[clip["location"]]
        self.origin = [li * 1000.0, 0.0, 0.0]
        self.marks = {k: K.add(self.origin, v) for k, v in self.loc["stage"]["marks"].items()}

    def pt(self, x):
        if isinstance(x, str):
            if x in self.marks:
                return self.marks[x]
            if x in self.c.get("cast", {}):
                return self.pos(x, 0)
            raise Bad(f"找不到点「{x}」")
        return K.add(self.origin, x)

    def path(self, name):
        cv = self.c["cast"][name]
        pts = cv["path"] if "path" in cv else [dict(cv, t=0)]
        return pts

    def pos(self, name, t):
        pts = self.path(name)
        prev = pts[0]
        for p in pts:
            if p["t"] <= t:
                prev = p
            else:
                f = (t - prev["t"]) / (p["t"] - prev["t"])
                return _lerp(self.pt(prev["at"]), self.pt(p["at"]), f)
        return self.pt(prev["at"])

    def face_dir(self, name, t):
        cv = self.c["cast"][name]
        f = None
        for p in self.path(name):
            if p["t"] <= t:
                f = p.get("face", cv.get("face"))
        pos = self.pos(name, t)
        if isinstance(f, (int, float)):
            ang = math.radians(f)
        elif f:
            tg = self.pos(f, t) if f in self.c["cast"] else self.pt(f)
            ang = math.radians(K.face_to(pos, tg))
        else:
            ang = 0.0
        return [math.sin(ang), -math.cos(ang), 0.0]

    def height(self, name):
        return self.chars[name]["height"]

    def people(self):
        out = []
        for i, name in enumerate(self.c["cast"]):
            keys = []
            for p in self.path(name):
                f = p.get("face", self.c["cast"][name].get("face", 0))
                face = f if isinstance(f, (int, float)) else (self.pos(f, p["t"]) if f in self.c["cast"] else self.pt(f))
                keys.append((p["t"], self.pt(p["at"]), face, p.get("lean", 0)))
            dur = sum(s["dur"] for s in self.c["shots"])
            keys.append((dur, keys[-1][1], keys[-1][2], keys[-1][3]))
            out.append(K.person(name, PALETTE[i % len(PALETTE)], self.height(name), keys))
        return out

    def boxes(self):
        st = self.loc["stage"]
        w, d = st.get("size", [20, 20])
        out = [K.bo(f"{self.loc['name']}_Floor", self.origin, [-w / 2, -d / 2, -0.1], [w / 2, d / 2, 0], BOXCOLOR["floor"])]
        for bx in st.get("boxes", []):
            out.append(K.bo(f"{self.loc['name']}_{bx['name']}", self.origin, bx["min"], bx["max"], BOXCOLOR.get(bx.get("color", "white"), BOXCOLOR["white"])))
        return out

    def camera(self, s, t0):
        t, size = s["type"], s.get("size")
        if s.get("cam"):  # 逃生口：直接给机位
            c = s["cam"]
            return K.cam(t0, c.get("lens", 35), self.pt(c["pos"]), self.pt(c["look"]), self.pt(c["end"]) if c.get("end") else None,
                         t0 + s["dur"] if c.get("end") else None)
        if t == "wide":
            e = self.loc["stage"]["views"][s["view"]] if s.get("view") else self.loc["stage"]["establish"]
            return K.cam(t0, e.get("lens", 35), self.pt(e["pos"]), self.pt(e["look"]))
        subj = s.get("subject")
        if t == "insert":
            o = self.pt(s["object"])
            off = s.get("cam_offset", [0.0, -0.45, 0.6])
            return K.cam(t0, 50, K.add(o, off), o)
        h = self.height(subj)
        if t == "ots":
            lens = SIZES[size or "中景"][0]
            fg, tg = self.pos(s["fg"], t0), self.pos(subj, t0)
            axis = self.axis_pts(t0)
            p = K.ots(fg, self.height(s["fg"]), tg, axis, back=s.get("back", 0.9), lat=s.get("lat", 0.3))
            return K.cam(t0, lens, p, K.head(tg, h))
        if t == "pov":
            p = K.head(self.pos(subj, t0), h)
            lk = self.pos(s["look"], t0) if s["look"] in self.c["cast"] else self.pt(s["look"])
            return K.cam(t0, SIZES[size or "中景"][0], p, lk)
        lens, dist, hr = SIZES[size or ("近景" if t == "single" else "中景")]
        def front(tt):
            pos, d = self.pos(subj, tt), self.face_dir(subj, tt)
            side = [-d[1], d[0], 0]
            return [pos[0] + d[0] * dist + side[0] * dist * 0.2, pos[1] + d[1] * dist + side[1] * dist * 0.2, pos[2] + h * hr], K.head(pos, h)
        p0, look = front(t0)
        if t == "track":
            p1, _ = front(t0 + s["dur"])
            return K.cam(t0, lens, p0, look, p1, t0 + s["dur"])
        return K.cam(t0, lens, p0, look)

    def axis_pts(self, t):
        pair = next(((s["fg"], s["subject"]) for s in self.c["shots"] if s["type"] == "ots"), None)
        return (self.pos(pair[0], t), self.pos(pair[1], t)) if pair else None

    def body(self, s, lens):
        b, t = [], s["type"]
        world = self.loc["world"]
        if t == "ots":
            b.append(f"画面一侧前景{s['fg']}虚化的肩膀")
        if t == "insert":
            b.append(f"{s['hand']}和{s['object']}" if s.get("hand") else s["object"])
        for n in ([s["subject"]] if s.get("subject") and t != "insert" else []) + [w for w in s.get("who", []) if w not in (s.get("subject"), s.get("fg"))]:
            b.append(n)
        if s.get("crowd"):
            ids = "、".join(map(str, s["crowd"].get("ids", [])))
            b.append(f"{world}群演（{ids} 号）{s['crowd'].get('doing', '')}")
        head = "画面里：" + "、".join(b) + "。"
        deg = K.LENS_DEG.get(lens, f"{lens}mm")
        parts = [f"{deg}，{s.get('size', '') + '，' if s.get('size') else ''}{MOVE[t]}"]
        acts = s.get("action", [])
        for a in (acts if isinstance(acts, list) else [acts]):
            parts.append(f"第 {a['at']} 秒，{a['text']}" if isinstance(a, dict) and "at" in a else (a["text"] if isinstance(a, dict) else a))
        if s.get("line"):
            ln = s["line"]
            say = {"on": f"{ln['who']}说：", "back": f"背对镜头的{ln['who']}说：", "off": f"画外，{ln['who']}的声音："}[ln.get("mode", "on")]
            parts.append(f"{say}{{{ln['text']}}}")
        snd = " ".join(f"<{x['text']}>" for x in s.get("sound", []))
        out = head + "；".join(parts) + (f"；{snd}" if snd else "")
        return out if out.endswith("}") else out + "。"

    def build(self, assets_idx):
        shots, t0 = [], 0.0
        for k, s in enumerate(self.c["shots"], 1):
            cm = self.camera(s, t0)
            sh = dict(t0=round(t0, 3), t1=round(t0 + s["dur"], 3), name=s.get("name", f"镜{k}"), lens=cm["lens"], cam=cm, body=self.body(s, cm["lens"]))
            glass = [f"{self.loc['name']}_{bx['name']}" for bx in self.loc["stage"].get("boxes", []) if bx.get("color") == "glass"]
            occ = list(s.get("allow_occlude", [])) + glass  # 玻璃是透明的，挡在前面不算遮挡
            if occ:
                sh["allow_occlude"] = occ
            if s.get("allow_small"):
                sh["allow_small"] = s["allow_small"]
            shots.append(sh)
            t0 += s["dur"]
        c = self.c
        cast = list(c["cast"])
        world = self.loc["world"]
        tags = [f"@{n}" for n in cast] + [f"@prop_{p}" for p in c.get("props", [])] + [f"@loc_{c['location']}"]
        if f"@loc_{c['location']}_grid" in assets_idx:
            tags.append(f"@loc_{c['location']}_grid")
        if any(s.get("crowd") for s in c["shots"]):
            tags.append(f"@crowd_{world}")
        speakers = []
        for s in c["shots"]:
            if s.get("line") and s["line"]["who"] not in speakers:
                speakers.append(s["line"]["who"])
        brief = "、".join(f"{n}（{self.chars[n].get('mark_zh', self.chars[n]['lock'].split('：', 1)[-1][:12])}）" for n in cast)
        crowd_note = f"另有{world}群演，按编号取自群像。" if "@crowd_" + world in tags else ""
        ots = next((s for s in c["shots"] if s["type"] == "ots"), None)
        axis_txt = f"{ots['fg']}和{ots['subject']}对话的轴线固定，整场不换边；" if ots else ""
        return dict(n=c["n"], dur=round(t0, 3), title=c["title"], summary=c.get("summary", c["title"]), model=c.get("model", "Seedance 2.5 + 白模"),
                    tags=tags, count=f"画面中始终只有 {len(cast)} 个有名字的角色：{brief}。{crowd_note}每一镜画面里有谁，以时间轴里\"画面里\"那一句为准。",
                    context=c.get("context", c.get("summary", "")), extra_chars=[], voices=speakers,
                    sfx=" ".join(f"<{x['text']}>" for s in c["shots"] for x in s.get("sound", [])) or "无",
                    constraint=axis_txt + c.get("constraint", ""), axis={"a": ots["fg"], "b": ots["subject"]} if ots else None,
                    people=self.people(), shots=shots, extra_boxes=[], fail=c.get("fail", "人物脸和服装与参考图不一致；画面出现文字。"),
                    risk=c.get("risk", "—"), splice=c.get("splice", "—"))


def build_assets(proj):
    bible, board = load(proj)
    E, W = validate(bible, board)
    if E:
        raise Bad("\n".join(E))
    en, _, note = style_map(bible)
    its = items(bible, board)
    K.write_asset_doc(proj, bible["title"], its, en, note, "出图顺序：人物三视图 → 状态变体 → 道具 → 场景 → 宫格 → 群像。")
    return len(its), W


def build_specs(proj):
    bible, board = load(proj)
    E, W = validate(bible, board)
    if E:
        raise Bad("\n".join(E))
    en, zh, _ = style_map(bible)
    its = items(bible, board)
    idx = {it["tag"] for it in its}
    loc_index = {l["name"]: i for i, l in enumerate(bible["locations"])}
    clips, boxes = [], []
    seen = set()
    for c in board["clips"]:
        cl = Clip(bible, c, loc_index[c["location"]])
        clips.append(cl.build(idx))
        if c["location"] not in seen:
            boxes += cl.boxes()
            seen.add(c["location"])
    voice = {c["name"]: f"{c['name']}：{c['voice']}" for c in bible["characters"]}
    texts = dict(THREE=bible["three"], STYLE=zh, MUSIC=bible["music"], VOICE=voice, LIP=bible.get("lip", LIP),
                 ANCHOR=ANCHOR + bible.get("anchor_extra", ""))
    os.makedirs(os.path.join(proj, "预演规格"), exist_ok=True)
    colors = "，".join(f"{PALETTE_ZH[i % 6]}色圆柱={c['name']}" for i, c in enumerate(bible["characters"])) + "，灰白方块=场景和道具"
    K.export(proj, bible["title"], bible["short"], its, boxes, clips, texts, colors)
    return len(clips), W


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ("check", "assets", "specs"):
        sys.exit(__doc__)
    proj = os.path.abspath(sys.argv[2])
    try:
        if sys.argv[1] == "check":
            E, W = validate(*load(proj))
            for w in W:
                print("WARN ", w)
            for e in E:
                print("ERROR", e)
            print("通过" if not E else f"{len(E)} 处错误")
            sys.exit(1 if E else 0)
        n, W = build_assets(proj) if sys.argv[1] == "assets" else build_specs(proj)
        for w in W:
            print("WARN ", w)
        print(f"完成：{n}")
    except Bad as e:
        print("ERROR", str(e).replace("\n", "\nERROR "))
        sys.exit(1)


if __name__ == "__main__":
    main()
