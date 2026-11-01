# Skill 调研评估报告

> 调研对象：[awesome-short-drama-skills](https://github.com/wp746/awesome-short-drama-skills)（元数据 2026-10-23）收录的 83 个 skill 仓库（另 16 个完整应用平台不是 skill，未纳入）。
> 调研时间：2026-10-30。方式：83 个仓库全部浅克隆到本地，共 538 个 SKILL.md。
> - **全部仓库**：读了每个 SKILL.md 的名称、描述和结构清单。
> - **深读（约 20 个）**：Seedance 2.5 / 导演 / 表演 / 资产锁定 / 质检这几类核心仓库，连同它们的 references 一起读。
> 说明：这份报告评的是"它的方法能不能拿来用在 Seedance 2.5 工业流程里"，不是在实际出片中测出来的效果。剧本类排名参考了原清单作者的两轮盲测。

## 评级

- **S 核心吸收**：方法被工厂直接采纳为标准（写进《提示词圣经》或岗位 SKILL）。
- **A 参考借鉴**：吸收其中某个机制。
- **B 重复/过时**：内容被 S/A 覆盖，或是针对 Seedance 2.0 的旧写法。
- **C 不适用**：面向其他模型（MiniMax H3 / 可灵 / ComfyUI 本地）、营销广告、或与影视无关。

---

## 一、Seedance 提示词与视频导演（工厂最核心的知识来源）

| 仓库 | 评级 | 吸收了什么 / 为什么 |
|---|---|---|
| OSideMedia/higgsfield-ai-prompt-skill（36 个 skill） | **S** | 全库最深。`seedance-2-5`：四种模式路由、参考职责+禁继承+保真等级、五步多参、分幕+结束状态、括号语法、首尾帧、按"活的种类"拆生成；`ENGINE-RULES`：11 条引擎规则；`HELL-GRIND`：95 分钟 AI 长片生产手册（四图角色设定、去头全身、空间地图 GEO、首秒全景定位、人数锁、外科式迭代、10–15 次法则）；`acting`：五支柱、表演母本、活眼睛、状态而非过程；`scene-engine`：五要素戏剧发动机；FOV 离散锚点。缺点：围绕 Higgsfield 付费平台，部分参数不适用即梦 |
| liyue-aigc/seedance-2-5-video-director | **S** | 基于即梦官方《Seedance 2.5 User Guide》rev.419 快照：硬参数、稳定区间、八种主模式、官方示例（30 秒精确结构、超长视频、延长、编辑、Clay、无缝转场、多宫格）、写实表演模式、台词容量（3–5 字/秒）、物理因果链、矛盾审计 |
| babicat4242-svg/seedance-2-5-prompting | **S** | 运镜编译器（目的→起始→主运镜→路径→速度→走位→焦段→结束）、运镜易混对照、八段式顺序、提示词长度合同（≤5000 字符）、修订编译器（每次输出完整替换稿） |
| UncleWang2088/short-drama-director | **S** | `CINEDANCE 提示词导演`（中文版块结构与 4-D 静默 QA）、`真实演技对话提示词`（话轮、言语不流畅类型学、唇部防崩、持械视线对齐）；`导演思维`、`红果审剧本` 为 A |
| LearnPrompt/awesome-seedance（15 个 skill） | **S** | 207 条真实高热案例归纳的模板与"常见坑"（叙事短片、对白口型、动漫画风锁、故事板转视频等）；七维审片表；生产工作流状态机 |
| machina-exm/film-studio-skills | **S** | 资产护照、压力测试矩阵（角色 10/10 才锁定）、十五块镜头提示词、生成日志与只改一行、`/generations` 与 `/selects` 分离 |
| luanyi824-hash/xiaxia | A | 场次时长预算（单动作 1–2.5 秒、超 4 秒的镜头必须有持续表演）、"每镜新增一种信息"、生成组切分规则、返修顺序 |
| wuwangzhang1216/DirectorSKILL | A | 视觉论点必须是可拍摄的变化；节拍≠镜头；20 位导演风格参数模块（只取方法，不抄镜头） |
| woodfantasy/Seedance-ShotDesign-Skills | A | 六步流程与 2.5 各模式规则，与 liyue 大量重叠 |
| oiuv/ai-short-drama（sd25-pe） | A | 素材映射置信度处理、"素材不可读时不假装看过" |
| nigo-studio/ai-film-skills | A | R2V 单镜合同；角色一致性三联图 |
| AtlasCloudAI/awesome-seedance-2.5-prompts-skills | A | T2V/R2V/I2V 路线选择、Seedream 故事板；厂商 API 绑定，广告类居多 |
| alchaincyf/seedance-skill（花叔） | A | 用 scene.json 生成白模参考视频再对齐提示词——工厂"白模预演"思路来源（本工厂改用 Blender） |
| smixs/visual-skills | A | Murch 剪辑六规则 + 走位/蒙太奇法则 |
| liyue-aigc/seedance-2-5-fight-director、ZzzAloong/fight-scene-director、irenerachel/fight-prompt-director、qualsenWeb/fight-video-create-skill | A | 打戏：波段拆解、耗时反推、招式库；合并进分镜师的动作段落规则 |
| zhouwei713/chinese-epic-scene-director | A | 东方史诗：可量化尺度证据、五层空间 |
| 62656456/ai-film-skills | A | 类型视觉预设（武侠/黑色/恐怖/赛博/史诗…）；场景"主图+反打图" |
| lixiaoxiao9888-create/manju-laoli-skill（13 个） | A | 投喂前六道闸门、台词完整性对照（4-gram 覆盖率）、素材形态声明（M0/M1/M2）。体量大、规则多，部分整合他人内容 |
| djyy1031/ai-comic-drama-director-skills | A | 生成前执行连续性检查（首帧、站位、朝向、视线、道具手、轴线、光向） |
| dexhunter/seedance2-skill、liangdabiao/make-prompt-seedance2、cclank/lanshu（seedance-prompter/storyboard/debugger） | B | Seedance 2.0 时代写法（固定 3 秒切、8 要素公式）；debugger 的 12 类故障表并入修片表 |
| liangdabiao/Seedance2-Storyboard-Generator、smy-seedance-storyboard | B | 2.0 多集分镜；上美影风格可作为风格预设参考 |
| jnMetaCode/ai-shortfilm-prompts | B | 通用五段式，未针对 2.5 |
| T8mars/minimax-h3-prompt-skill-T8 | C | H3 案例库（仓库过大未完整克隆） |
| phileiny/h3-storyboard-skill、MIKA6941/Comfy-H3-Director、mini-yifan/open-source-video-gen-skill、SlavaSexton/ComfyUI-Agent-Kit | C | 面向 MiniMax H3 / ComfyUI；h3-storyboard 的表演节拍表思路已由 acting 覆盖 |

## 二、全流程（剧本 → 分镜 → 成片）

| 仓库 | 评级 | 说明 |
|---|---|---|
| zenstory-ai/drama-skills（12 个） | **S**（编剧） | 盲测剧本三次全赢对照组。"每场改变信息/权力/关系/情绪/风险"、对白必须在争取或回避、能演的不说、生产标签 `[VO][SFX][连续性]`；五文档路由 |
| ilkaydemiralay/vision_art_creator（11 个） | A | 影视部门式岗位划分（编剧/导演/摄影/美术/角色/分镜/镜头表/提示词/声音/剪辑/总监）——工厂岗位设计的参照之一 |
| JohnKeating1997/spark-video（7 个） | A | 逐条 6 轴自动审片 + 重试状态机（逻辑/比例/物理/风格/选角一致/对白归属，≥7 分通过） |
| eternityspring/shuohao-skills（7 个） | A | 开场站位排布（从场景图推俯视平面）、角色参考图"先出正面锚点，其余视图只参考锚点" |
| wddxh/ShortVideoDirector（71 个） | A | 生产者与独立审核者严格分离；资产图逐目标视觉审核 |
| lixiaoxiao9888-create/manju-laoli-skill | A | 见上 |
| A-cat-with-carrots/OnlyShot | A | 17 种失败模式；分镜图作为视频首帧的工业层 |
| Hao0321/ai-short-drama | A | 爽剧题材编译；人物大纲盲测三次全赢 |
| xixihhhh/ai-short-drama-skill（Dramake） | A | 横竖屏与平台适配、自带 evals |
| mengxiujie/ManjuForge | A | 7 个记忆文件 + 22 项一致性检查（适合长连载） |
| leynos/visual-storytelling-skills | A | 场景清单抽取 + 重置关键状态（continuity inventory） |
| suihe1/short-drama-production | B | 5 个 novel-* skill 与 shuohao 相同；H3 导向 |
| SwotAtmk/infinite-creation（52 个） | B | 大量为其他仓库副本（含 manju-laoli 套装）；本地 ComfyUI + H3 |
| Tencent/workrally | C | 腾讯 CLI 工具集的操作说明，非方法论 |
| zhaihao118/Micro-Drama-Skills | B | 2.0 时代 9 宫格 + 15 秒两段，已过时（超 180 天未更新） |
| liuxiao20051106-prog/ai-manga-drama、jxshow/jingju-skills、senmanx/novel-to-manju、oiuv/ai-short-drama、muxia0396、momo5213/live-action-drama-16x9、kevinchin12/storyboard-director、zlbigger/story-video-director、LuoJiangYong/muse-video-skill、jlam00-dev/hardcore-director、AharaOoO/acheng-director-skill | B | 全流程思路相近，核心机制已被 S 级覆盖；acheng 的"132 运镜索引 + 连续性账本"、hardcore-director 的模块路由可作参考 |

## 三、编剧 / 改编 / 审稿 / 编剧基本功

| 仓库 | 评级 | 说明 |
|---|---|---|
| Shanyin-ai/shanyin-screenwriting-master | **S** | 盲测剧本三次全赢：对白短、有潜台词、情绪落在动作上 |
| jtydhr88/screenwriting-skills（26 个） | **S** | 盲测三次全赢；Field/Snyder/McKee/Truby/Egri 结构，场景与对白手艺，小津、契诃夫风格 |
| adoria111/emma-screenwriting-skills（24 个） | **S** | 盲测三次全赢；台词效率逐句评分（<5 删、5–7 重写）、期待设计、逐集钩子 |
| Vi7QY/screenwriter-skill | A | 红果 Top100 操盘经验 38 条审稿规则 |
| zhlmi/screenplay-review-checklist、narrative-to-screen-reader | A | 37 条对抗式踩雷判据；改编可拍性读本 |
| lixiaoxiao9888-create/short-drama-factory | A | 付费卡点、六母型钩子、五大断章公式（短剧赛道需要时启用） |
| 0xsline/short-drama | A | 四层反派、五维评分、出海格式 |
| catyiqian/qianqianwriting、pipivv/gushi-skill、geslie1/kunka、e06084/claude-screenwriting | B | 救猫咪/麦基/Vogler 方法，jtydhr88 已更完整 |
| SoloEnt-AI/5min-drama-contest、egguy886、zhu5859243-free、mudden2380078550、YvonneMovingon、VanGong1999（62 个，多为小工具） | B | 赛事/平台向或功能碎片化 |
| ciel-oliver/analyze-hit-novel | A | 拆书：时间线、钩子节奏曲线（改编项目上游用） |

## 四、角色 / 资产 / 静帧

| 仓库 | 评级 | 说明 |
|---|---|---|
| popopo-99/zy-cinematic-realism | A | 有动机的叙事关键帧（CC BY-NC，只借方法） |
| zhurui0523/XiaoLuo-AI-Drama-Skill | B | 提示词文件集，角色三视图/表情/服装 |
| UncleWang2088 的 cinema-dna-21x9x3 | A | 21:9 构图压力、视线流量、去 CG 油腻感 |

## 五、配套：去 AI 味

| 仓库 | 评级 | 说明 |
|---|---|---|
| blader/humanizer、KKKKhazix/human-writing、Nanako0129/sepia | A | 只用于剧本对白和旁白的去 AI 腔；不要用于提示词（提示词要的是具体，不是文风） |

---

## 结论：这个生态的共同缺口（也是本工厂补上的）

1. **大多数 skill 停在 2.0 的写法**：固定 3 秒切镜、"完全参考"、强塞 BGM。真正按 2.5 官方手册写的只有 4–5 个。
2. **几乎没有人讲"30 秒怎么装一场戏"**：都在讲提示词格式，不讲戏剧结构如何映射到时间预算 → 见《03-30秒电影化叙事法》。
3. **资产门禁普遍缺失**：只有 film-studio-skills 和 Higgsfield 长片手册坚持"资产不锁定不生成"。这是省钱最多的一条。
4. **生产者兼任审核者**：多数全流程 skill 自己写自己审。工厂把审核岗位独立（剧本医生、场记、合规官、审片员）。
5. **表演层普遍薄弱**：多数写"表情悲伤"。工厂把表演指导设成独立岗位，母本 + 逐场改写 + 活眼睛 + 话轮。
6. **重复严重**：同一套内容在 3–4 个仓库里出现（shuohao/suihe1、manju-laoli/infinite-creation、H3 写作 skill 至少 5 份）。
