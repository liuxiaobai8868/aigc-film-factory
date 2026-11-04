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
# 有动机的运镜（docs/20 第四节"张力"）：kind → (中文, 英文)
MOVES = {"push": ("推近", "the camera pushes in"), "pull": ("拉远", "the camera pulls back"),
         "truck_left": ("向左横移", "the camera trucks left"), "truck_right": ("向右横移", "the camera trucks right"),
         "rise": ("升起", "the camera cranes up"), "drop": ("降下", "the camera cranes down"),
         "orbit_left": ("向左环绕", "the camera arcs left around the subject"), "orbit_right": ("向右环绕", "the camera arcs right around the subject"),
         "handheld": ("手持，轻微晃动", "handheld, with a slight unsteady sway")}
SPEEDS = {"slow": ("缓慢", "slowly"), "steady": ("匀速", "steadily"), "sudden": ("突然", "suddenly")}
SIZE_RANK = {"大特写": 0, "特写": 1, "近景": 2, "中景": 3, "全景": 4, "大全景": 5}


def move_text(mv, lang="zh"):
    kind, sp = MOVES[mv["kind"]], SPEEDS.get(mv.get("speed", "slow"), SPEEDS["slow"])
    if mv["kind"] == "handheld":
        return kind[0] if lang == "zh" else kind[1]
    if lang == "zh":
        return f"镜头{sp[0]}{kind[0]}" + (f"到{mv['to']}" if mv.get("to") else "")
    return f"{kind[1]} {sp[1]}"


def shot_rank(s):
    if s.get("size") in SIZE_RANK:
        return SIZE_RANK[s["size"]]
    return {"wide": 4, "insert": 1}.get(s.get("type"), 2 if s.get("type") == "single" else 3)
PALETTE = [[0.95, 0.8, 0.15], [0.2, 0.35, 0.85], [0.85, 0.2, 0.15], [0.95, 0.6, 0.75], [0.3, 0.75, 0.4], [0.6, 0.35, 0.8]]
PALETTE_ZH = ["黄", "蓝", "红", "粉", "绿", "紫"]
BOXCOLOR = {"wood": [0.35, 0.25, 0.18], "white": [0.92, 0.92, 0.9], "stone": [0.45, 0.47, 0.5], "floor": [0.5, 0.5, 0.52],
            "dark": [0.12, 0.12, 0.14], "red": [0.85, 0.12, 0.1], "gold": [1.0, 0.75, 0.2], "glass": [0.75, 0.8, 0.9]}
LIP = ("对白：普通话，自然口语。所有角色只说花括号里的台词；每句台词只有说话的那一个角色动嘴，其余角色闭着嘴；画外音不对任何人的口型；"
       "人声干净贴近，有人说话时配乐和环境声自动压低。画面全程是纯影像，没有字幕。")
ANCHOR = "人物都是正常的人体结构：两只手各五根手指。"
SAVIOR = re.compile(r"金手指|系统(发|奖|签到)|签到|认亲|亲孙子|赘婿|战神|龙王|跪地求|求复合|豪门|一夜暴富|神豪|重生复仇|打脸")  # docs/20 第一节：等救主结构
CORE_KEYS = {"want": "主角想要什么", "need": "他真正需要什么", "choice": "关键时刻他自己做的选择", "cost": "这个选择让他失去什么",
             "image": "能说出主题的那个画面"}
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

def models_of(proj):
    p = os.path.join(proj, "production.json")
    return json.load(open(p, encoding="utf-8")).get("video_models", ["seedance"]) if os.path.exists(p) else ["seedance"]


def validate(bible, board, models=("seedance",)):
    """返回 (errors, warnings)，每条都带"怎么改"。models 里有 hailuo 时，额外要求英文字段（H3 官方提示词是英文分段格式）。"""
    E, W = [], []
    need_en = "hailuo" in models
    EN = "（要出海螺 H3：官方提示词是英文分段格式，英文由你在数据里写一次，编译器不临场翻译）"
    recipes = {r["id"] for r in json.load(open(os.path.join(ROOT, "config", "style_recipes.json"), encoding="utf-8"))["配方"]}
    for k in ("title", "short", "film", "worlds", "people_recipe", "three", "music", "characters", "locations"):
        if k not in bible:
            E.append(f"设定.json 缺字段 {k}")
    if E:
        return E, W
    core = bible.get("core") or {}
    for k, zh in CORE_KEYS.items():  # docs/20 第三节内核闸门 A–E
        if len(str(core.get(k, "")).strip()) < 4:
            E.append(f"设定.json 的 core.{k} 没写或太短：{zh}（docs/20 第三节；写不出来说明故事内核还没立住，回到故事阶段）")
    if core and core.get("choice") and re.search(r"被|等|得到|获得|认出|揭晓", str(core.get("choice"))[:6]):
        W.append("core.choice 读起来像是主角在等或被动得到；关键选择要是他主动做的（docs/20 第三节 A）")
    hit = SAVIOR.search(" ".join(str(x) for x in [core, bible.get("three", ""), bible.get("title", "")]))
    if hit:
        E.append(f"故事内核里出现「{hit.group(0)}」：这是等救主结构（docs/20 第一节、第三节 F），本工厂不做；回到故事阶段换内核")
    for w, v in bible["worlds"].items():
        if v.get("recipe") not in recipes:
            E.append(f"世界「{w}」的 recipe {v.get('recipe')} 不在 config/style_recipes.json（用 tools/mj_style.py --recipes 看）")
    if bible["people_recipe"] not in recipes:
        E.append(f"people_recipe {bible['people_recipe']} 不存在")
    if need_en and not bible.get("music_en"):
        E.append("设定.json 缺 music_en：配乐的英文一两句（没有配乐写 \"N/A\"）" + EN)
    chars = {c["name"]: c for c in bible["characters"]}
    props = {p["name"]: p for p in bible.get("props", [])}
    locs = {l["name"]: l for l in bible["locations"]}
    crowds = {c["world"]: c for c in bible.get("crowds", [])}
    for c in bible["characters"]:
        for k in ("lock", "brief_en", "must_en", "height", "voice") + (("voice_en",) if need_en else ()):
            if k not in c:
                E.append(f"人物「{c.get('name')}」缺 {k}" + (EN if k == "voice_en" else ""))
        if len(str(c.get("silhouette", ""))) < 4:
            E.append(f"人物「{c.get('name')}」缺 silhouette：剪影识别点，只看轮廓就认得出是谁（发型、体型、标志物件）（crew/07）")
        if re.search(r"毛孔|瑕疵|颗粒|pores?|blemish|grain", c.get("lock", "") + c.get("must_en", ""), re.I):
            E.append(f"人物「{c.get('name')}」描述里写了毛孔 / 瑕疵 / 颗粒：出图模型会照字面画成砂纸皮肤和噪点（docs/16 第二节），改写成具体的雀斑、痣、细纹和光泽")
        if re.search(r"\d+\s*岁|岁的|小孩|孩子|少年|少女", c.get("lock", "")):
            E.append(f"人物「{c['name']}」描述锁写了年龄词，改成'二十出头的成年人'这类写法（不写具体岁数、不写未成年）")
    for l in bible["locations"]:
        for k in ("world", "lock", "en", "must_en", "stage"):
            if k not in l:
                E.append(f"场景「{l.get('name')}」缺 {k}")
        if l.get("world") not in bible["worlds"]:
            E.append(f"场景「{l.get('name')}」的 world 不在 worlds 里")
        for k, zh in (("light", "光逻辑：主光是什么、在哪、什么色温，辅光从哪来"), ("era", "时代锁：可以出现 / 不能出现的物件"),
                      ("wear", "使用痕迹：被谁用过、怎么磨损（磨亮的扶手、墙角水渍……）")):
            if len(str(l.get(k, ""))) < 6:
                E.append(f"场景「{l.get('name')}」缺美术字段 {k}：{zh}（crew/06，docs/20 美术指导）")
        if len(str(l.get("contrast", ""))) < 6:
            E.append(f"场景「{l.get('name')}」缺 contrast：这个场景的对冲，明暗 / 冷暖 / 大小 / 新旧 / 静动至少一组（docs/20 第四节\"张力\"）")
        if not l.get("anchor"):
            E.append(f"场景「{l.get('name')}」缺 anchor：锚点物列表，观众记得住、模型钉得住的 1–3 件东西（crew/06）")
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
    for p in bible.get("props", []):
        used = [s for c in board.get("clips", []) if p["name"] in c.get("props", []) for s in c.get("shots", [])
                if s.get("type") == "insert" or p["name"] in json.dumps(s.get("action", ""), ensure_ascii=False)]
        if used and len(str(p.get("mechanism", ""))) < 6:
            E.append(f"道具「{p['name']}」会被手操作，缺 mechanism：手怎么动 → 道具怎么响应 → 结果状态（crew/06 道具操作机制；不写会出现手在动、东西不动）")
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
        turn, sig = clip.get("turn") or {}, clip.get("signature") or {}
        if not (turn.get("from") and turn.get("to")) or turn.get("from") == turn.get("to"):
            E.append(f"{tag} 缺价值翻转 turn: {{\"from\": 开头的处境, \"to\": 结尾的处境}}，两头要相反（docs/20 第四节）")
        if not isinstance(sig.get("shot"), int) or not 1 <= sig["shot"] <= len(shots) or len(str(sig.get("why", ""))) < 6:
            E.append(f"{tag} 缺视听高光 signature: {{\"shot\": 第几镜, \"why\": 构图、光、运动、声音怎么同时发力}}（docs/20 第四节）")
        if len(str(clip.get("tension", ""))) < 8:
            E.append(f"{tag} 缺压力源 tension：谁想要什么、什么挡着、观众比角色多知道还是少知道什么（docs/20 第四节\"张力\"）")
        durs = [s.get("dur", 0) for s in shots if s.get("dur")]
        if len(durs) >= 3 and max(durs) < 1.5 * min(durs):
            E.append(f"{tag} 镜头时长 {durs} 太平均，节奏四平八稳：高光镜头给足时长，之前用短镜头加速，最长至少是最短的 1.5 倍（docs/20 第四节）")
        moving = [s for s in shots if s.get("move") or s.get("type") in ("track", "pov") or (s.get("cam") or {}).get("end")]
        if shots and not moving and len(str(clip.get("stillness", ""))) < 6:
            E.append(f"{tag} 整条都是固定机位：给转折那一镜一个有动机的 move（推近、横移揭示、手持），或写 stillness 说明为什么要静、静之后哪里爆发（docs/20 第四节）")
        ranks = {shot_rank(s) for s in shots}
        if len(shots) >= 3 and len(ranks) < 3:
            W.append(f"{tag} 只用了 {len(ranks)} 种景别，每条至少三种（docs/20 第五节分镜师）")
        for k in range(1, len(shots)):
            a, b = shots[k - 1], shots[k]
            if a.get("type") == b.get("type") and shot_rank(a) == shot_rank(b) and not b.get("move"):
                E.append(f"{tag} 镜{k} 和镜{k + 1} 类型和景别都一样，像跳切：换景别或角度（docs/14 第三节）")
        if need_en and not clip.get("summary_en"):
            E.append(f"{tag} 缺 summary_en：这一条的英文一句话" + EN)
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
            mv = s.get("move")
            if mv:
                if mv.get("kind") not in MOVES:
                    E.append(f"{st} move.kind 要是 {list(MOVES)} 之一")
                elif mv.get("speed", "slow") not in SPEEDS:
                    E.append(f"{st} move.speed 要是 {list(SPEEDS)} 之一")
                if len(str(mv.get("why", ""))) < 4:
                    E.append(f"{st} 运镜要写动机 move.why：跟视线、跟情绪，还是为了揭示什么；说不出动机就用固定机位（docs/20 第四节）")
                if t in ("track", "pov") or s.get("cam"):
                    E.append(f"{st} {t if not s.get('cam') else 'cam'} 镜头自带机位运动，不能再加 move")
                if mv.get("speed") == "sudden" and s.get("dur", 0) < 2:
                    E.append(f"{st} 突然的运镜单镜不短于 2 秒，模型才做得出来")
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
            if need_en:
                for a in acts:
                    if not (isinstance(a, dict) and a.get("en")):
                        E.append(f"{st} 动作要写成 {{\"text\": 中文, \"en\": 英文}}（可加 \"at\": 秒）" + EN)
                for snd in s.get("sound", []):
                    if isinstance(snd, dict) and not snd.get("en"):
                        E.append(f"{st} 声音「{snd.get('text')}」缺 en" + EN)
                if s.get("crowd") and not s["crowd"].get("doing_en"):
                    E.append(f"{st} crowd 缺 doing_en" + EN)
                if t == "insert" and not s.get("object_en"):
                    E.append(f"{st} 插入镜头缺 object_en（拍的物件，英文）" + EN)
                if t == "insert" and s.get("hand") and not s.get("hand_en"):
                    E.append(f"{st} 插入镜头缺 hand_en（谁的手，英文）" + EN)
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
                if not acts:
                    E.append(f"{st} 对白镜头要先写一个手上的动作（剥橘子、拉袖子、摘耳机……），模型会把动作演成说话的自然停顿；"
                             "没有动作的台词容易念得像背书（docs/20 台词对白、crew/23）")
                if len(SEP.sub("", txt)) > 12 and not re.search(r"[，、…—？！?!,]", txt.rstrip("。.？！?!")):
                    W.append(f"{st} 台词「{txt}」超过 12 个字中间没有停顿：用逗号、省略号、问号写出呼吸，或拆成半句 + 回问")
                if need_en and line.get("delivery") and not line.get("delivery_en"):
                    E.append(f"{st} 台词写了 delivery，缺 delivery_en" + EN)
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
    all_shots = [s for c in board.get("clips", []) for s in c.get("shots", [])]
    if all_shots and all(s.get("line") for s in all_shots):
        W.append("全片每一镜都有台词：至少留一段不靠台词、只用画面和声音讲的戏（docs/20 第二节第 5 条）")
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
                             art=f"剪影识别点：{c['silhouette']}" if c.get("silhouette") else "",
                             brief_en=c["brief_en"], voice_en=c.get("voice_en", ""),
                             use=use(f"@{c['name']}"), lock=c["lock"],
                             en=f"Create a character reference sheet for a {film}: {c['brief_en']}", must=must,
                             check=c.get("check", []) + ["正面全身像的脸模糊成椭圆，右侧大头像清楚", "没有文字"],
                             duty=f"「{c['name']}」：脸只从右侧大头像取；体型和服装从左侧全身像取；正面全身像的模糊椭圆不是脸；不继承灰底和三视图版式。"))
        for v in c.get("variants", []):
            push(v["name"], dict(tag=f"@{v['name']}", world="__people__", file=f"{v['name']}_三视图.png", type="状态变体", rec=REC,
                                 brief_en=v.get("brief_en", c["brief_en"]), voice_en=c.get("voice_en", ""),
                                 deps=str(idx[c["name"]]), use=use(f"@{v['name']}"), lock=v["lock"],
                                 en=f"Edit Image 1, the character sheet of {c['brief_en']}. Keep the face, body, layout and background exactly the same.",
                                 must=f"Change only: {v['edit_en']}", check=v.get("check", []) + ["脸和版式不变"],
                                 duty=f"「{c['name']}」的另一个状态（{v['name']}）：脸只从右侧大头像取；不继承灰底和三视图版式。"))
    for p in bible.get("props", []):
        dep = [p["ref"]] if p.get("ref") in idx else []
        ref = "The prop must match the one carried by the character in Image 1. " if dep else ""
        push("prop:" + p["name"], dict(tag=f"@prop_{p['name']}", world="__people__", file=f"道具_{p['name']}.png", type="道具", rec=REC, brief_en=p["en"],
                                       deps=_num(dep, idx), use=use(f"@prop_{p['name']}"), lock=p["lock"],
                                       en=f"A prop reference for a {film}, on a seamless neutral grey background, three-quarter view: {p['en']} {ref}".strip(),
                                       must=p["must_en"] + " No text, symbols or labels.", check=p.get("check", []) + ["没有文字"],
                                       duty=f"「{p['name']}」：只取外形、材质和状态；不继承灰底。"))
    for l in bible["locations"]:
        hv = l.get("human_view")
        anchors = "、".join(l.get("anchor", []))
        art = f"锚点物：{anchors}；光逻辑：{l.get('light', '')}；时代：{l.get('era', '')}；使用痕迹：{l.get('wear', '')}" + (f"；画面对冲：{l['contrast']}" if l.get('contrast') else "")
        push("loc:" + l["name"], dict(tag=f"@loc_{l['name']}", world=l["world"], file=f"场景_{l['name']}.png", brief_en=l["en"], art=art,
                                      geo_note=f"「{l['name']}」美术：{art}。",
                                      type="人类视角机位" if hv else "场景主图", rec=REC, deps="—", use=use(f"@loc_{l['name']}"), lock=l["lock"],
                                      en=f"A location reference image for a {film}, no characters: {l['en']}",
                                      must=l["must_en"] + " The scene is completely uninhabited. Full-frame image with no black bars. No readable text or signs.",
                                      check=l.get("check", []) + [f"锚点物都在：{anchors}", "光的方向和冷暖符合光逻辑", "没有人", "没有黑边", "没有文字"],
                                      duty=f"「{l['name']}」：只取空间结构、材质和光；不作首帧，不继承构图。"))
        if l.get("grid"):
            push("grid:" + l["name"], dict(tag=f"@loc_{l['name']}_grid", world=l["world"], file=f"场景_{l['name']}_宫格.png", type="场景宫格", rec=REC,
                                           brief_en="a 2x2 multi-view sheet of " + l["en"],
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
        it["brief_en"] = c["world_en"]
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
        cm = self._camera(s, t0)
        mv = s.get("move")
        if not mv or mv.get("kind") not in MOVES or len(cm["keys"]) > 1:
            return cm
        p, lk, kind = cm["keys"][0]["pos"], cm["look_at"], mv["kind"]
        v = _v(p, lk)
        L = math.hypot(v[0], v[1]) or 1.0
        f, side = [v[0] / L, v[1] / L, 0.0], [-v[1] / L, v[0] / L, 0.0]
        amt = float(mv.get("amount", 0.4))  # 推拉：走掉机位到主体距离的比例；横移 / 升降：米 = amount × 距离
        if kind == "handheld":
            cm["handheld"] = 0.015
            return cm
        if kind in ("push", "pull"):
            d = L * amt * (1 if kind == "push" else -1)
            end = [p[0] + f[0] * d, p[1] + f[1] * d, p[2]]
        elif kind in ("truck_left", "truck_right"):
            d = L * amt * (1 if kind == "truck_left" else -1)
            end = [p[0] + side[0] * d, p[1] + side[1] * d, p[2]]
        elif kind in ("rise", "drop"):
            end = [p[0], p[1], max(0.3, p[2] + L * amt * (1 if kind == "rise" else -1))]
        else:
            ang = math.radians(35 * amt / 0.4) * (1 if kind == "orbit_left" else -1)
            dx, dy = p[0] - lk[0], p[1] - lk[1]
            end = [lk[0] + dx * math.cos(ang) - dy * math.sin(ang), lk[1] + dx * math.sin(ang) + dy * math.cos(ang), p[2]]
        cm["keys"].append({"t": t0 + s["dur"], "pos": [round(x, 4) for x in end]})
        return cm

    def _camera(self, s, t0):
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
        mv = s.get("move")
        mtxt = MOVE[t] if not mv else (move_text(mv) if t in ("wide", "single") else f"{MOVE[t]}，{move_text(mv)}")
        parts = [f"{deg}，{s.get('size', '') + '，' if s.get('size') else ''}{mtxt}"]
        acts = s.get("action", [])
        for a in (acts if isinstance(acts, list) else [acts]):
            parts.append(f"第 {a['at']} 秒，{a['text']}" if isinstance(a, dict) and "at" in a else (a["text"] if isinstance(a, dict) else a))
        if s.get("line"):
            ln = s["line"]
            how = f"（{ln['delivery']}）" if ln.get("delivery") else ""
            say = {"on": f"{ln['who']}{how}说：", "back": f"背对镜头的{ln['who']}{how}说：", "off": f"画外，{ln['who']}的声音{how}："}[ln.get("mode", "on")]
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
            acts = s.get("action", [])
            acts = acts if isinstance(acts, list) else [acts]
            sh["struct"] = {k: v for k, v in dict(
                type=s["type"], size=s.get("size"), lens=cm["lens"], subject=s.get("subject"), fg=s.get("fg"), who=s.get("who"),
                object=s.get("object"), object_en=s.get("object_en"), hand=s.get("hand"), hand_en=s.get("hand_en"), view=s.get("view"),
                action=[{"at": a.get("at"), "zh": a.get("text"), "en": a.get("en")} if isinstance(a, dict) else {"zh": a} for a in acts],
                line=s.get("line"), sound=[{"zh": x.get("text"), "en": x.get("en"), "source": x.get("source")} for x in s.get("sound", []) if isinstance(x, dict)],
                crowd=s.get("crowd"), move=({"kind": s["move"]["kind"], "en": move_text(s["move"], "en")} if s.get("move") and s["move"].get("kind") in MOVES else None)).items() if v}  # 结构化镜头：可灵 / 海螺 / 万相的专用编译器用
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
                    constraint=axis_txt + c.get("constraint", "") + "".join(
                        f"道具操作（{p['name']}）：{p['mechanism']}。" for p in self.b.get("props", []) if p["name"] in c.get("props", []) and p.get("mechanism")), axis={"a": ots["fg"], "b": ots["subject"]} if ots else None,
                    people=self.people(), shots=shots, extra_boxes=[], fail=c.get("fail", "人物脸和服装与参考图不一致；画面出现文字。"),
                    risk=c.get("risk", "—"), splice=c.get("splice", "—"), summary_en=c.get("summary_en"),
                    style_en=self.style_en)


def build_assets(proj):
    bible, board = load(proj)
    E, W = validate(bible, board, models_of(proj))
    if E:
        raise Bad("\n".join(E))
    en, _, note = style_map(bible)
    its = items(bible, board)
    K.write_asset_doc(proj, bible["title"], its, en, note, "出图顺序：人物三视图 → 状态变体 → 道具 → 场景 → 宫格 → 群像。")
    return len(its), W


def build_stress(proj):
    """角色压力测试（crew/07）：每个主角 3 张——本片光下 3/4 中近景、暗处全身远景、和另一个主角同框。
    写 交付/01b-角色压力测试.md；前面照抄主角三视图条目（已出好的图会被跳过，当作参考图）。"""
    bible, board = load(proj)
    en, _, _ = style_map(bible)
    film = bible["film"]
    sheets = [it for it in items(bible, board) if it["type"] == "人物三视图"]
    locs = bible["locations"]
    out = [dict(it) for it in sheets]
    idx = {it["tag"]: i + 1 for i, it in enumerate(out)}
    for k, c in enumerate(bible["characters"]):
        me = idx[f"@{c['name']}"]
        la, lb = locs[k % len(locs)], locs[(k + 1) % len(locs)]
        partner = bible["characters"][(k + 1) % len(bible["characters"])] if len(bible["characters"]) > 1 else None
        same = "Image 1 is the approved character sheet: render this exact person (face from the large portrait on the right), " \
               "same face, hair, costume and body; clearly an adult; no text anywhere."
        tests = [("3/4 中近景 · " + la["name"] + "的光", f"A cinematic photoreal still of a {film}: a three-quarter medium close-up of {c['brief_en']} "
                  f"inside {la['en']}", f"{same} Lit by the scene's own light: {la.get('light', '')}.", la["world"], str(me)),
                 ("暗处全身远景 · " + lb["name"], f"A cinematic photoreal still of a {film}: a wide full-body shot of {c['brief_en']} standing in a dim corner of {lb['en']}",
                  f"{same} Low-key light; the person is small in frame but still recognisable by silhouette: {c.get('silhouette', '')}.", lb["world"], str(me))]
        if partner:
            tests.append(("双人同框 · " + partner["name"], f"A cinematic photoreal still of a {film}: a medium two-shot of {c['brief_en']} and {partner['brief_en']} "
                          f"facing each other inside {la['en']}", f"Images 1 and 2 are the approved character sheets of the two people; keep each face, "
                          "hair and costume exactly, never swap or blend them; both clearly adults; no text anywhere.", la["world"],
                          f"{me}、{idx['@' + partner['name']]}"))
        for j, (name, en_txt, must, world, deps) in enumerate(tests, 1):
            out.append(dict(tag=f"@压测_{c['name']}_{j}", world=world, file=f"压测_{c['name']}_{j}.png", type="压力测试", rec=REC, deps=deps,
                            use=name, lock=c["lock"], en=en_txt, must=must,
                            check=["脸和三视图大头像是同一个人", "发型、服装、剪影识别点都对", "皮肤自然、不像 AI 渲染", "没有文字"],
                            duty="只用于定稿前检查，不进视频"))
    path = os.path.join(proj, "交付")
    K.write_asset_doc(proj, bible["title"] + " · 角色压力测试", out, en, "与资产提示词相同的风格配方", "前几行是已定稿的三视图（会被跳过，只作参考图）。")
    os.replace(os.path.join(path, "01-资产提示词.md"), os.path.join(path, "01b-角色压力测试.md"))
    build_assets(proj)  # 恢复正式资产文档
    return len(out) - len(sheets), []


def build_specs(proj):
    bible, board = load(proj)
    E, W = validate(bible, board, models_of(proj))
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
        world = cl.loc["world"]
        vid = lambda x: x.replace(" still;", " footage;").replace(" still ", " footage ").replace("still shot on", "footage shot on")  # noqa: E731  配方原是出图用语
        cl.style_en = f"Setting look: {vid(en[world])}." + (f" People look: {vid(en['__people__'])}." if en["__people__"] != en[world] else "")
        clips.append(cl.build(idx))
        if c["location"] not in seen:
            boxes += cl.boxes()
            seen.add(c["location"])
    voice = {c["name"]: f"{c['name']}：{c['voice']}" for c in bible["characters"]}
    texts = dict(THREE=bible["three"], STYLE=zh, MUSIC=bible["music"], MUSIC_EN=bible.get("music_en"), VOICE=voice, LIP=bible.get("lip", LIP),
                 ANCHOR=ANCHOR + bible.get("anchor_extra", ""))
    os.makedirs(os.path.join(proj, "预演规格"), exist_ok=True)
    colors = "，".join(f"{PALETTE_ZH[i % 6]}色圆柱={c['name']}" for i, c in enumerate(bible["characters"])) + "，灰白方块=场景和道具"
    K.export(proj, bible["title"], bible["short"], its, boxes, clips, texts, colors)
    return len(clips), W


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ("check", "assets", "specs", "stress"):
        sys.exit(__doc__)
    proj = os.path.abspath(sys.argv[2])
    try:
        if sys.argv[1] == "check":
            E, W = validate(*load(proj), models_of(proj))
            for w in W:
                print("WARN ", w)
            for e in E:
                print("ERROR", e)
            print("通过" if not E else f"{len(E)} 处错误")
            sys.exit(1 if E else 0)
        n, W = {"assets": build_assets, "specs": build_specs, "stress": build_stress}[sys.argv[1]](proj)
        for w in W:
            print("WARN ", w)
        print(f"完成：{n}")
    except Bad as e:
        print("ERROR", str(e).replace("\n", "\nERROR "))
        sys.exit(1)


if __name__ == "__main__":
    main()
