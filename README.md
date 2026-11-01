# AIGC 制片工厂 · v0.9

一套按影视工业流程搭建的 AI 出片框架，专为 **Seedance 2.5（单次最长 30 秒）** 设计：从一句创意或剧本出发，交付两份可以直接复制粘贴的文档——

1. **《资产提示词》**：人物三视图、状态变体、道具、场景主图与宫格多视角、首帧。每张图标好**推荐出图模型和理由**（Image 2.5 / Nano Banana / Seedream / Midjourney）；接上 API 一条命令批量出图。
2. **《Seedance 提示词》**：按剧情逐条、带时间戳，**每条两个版本**——A 白模预演版（多传一段 Blender 预演视频，结构最稳）和 B 无预演版（只传图片）——并写明推荐哪个、为什么。

背后是 25 个岗位的专业视角（编剧、导演、摄影、美术、表演、台词、声音、武戏、VFX、场记、合规……）、40 条 Seedance 引擎规则、提示词机检、白模预演工具和多接口出图工具。框架成熟度与已知风险见 [docs/12-框架审核评估.md](docs/12-框架审核评估.md)。

## 安装

```bash
git clone <本仓库地址> aigc-film-factory
cd aigc-film-factory
./install.sh            # 把本仓库作为 skill 链接进 Claude Code / Codex / CodeBuddy 的 skills 目录
cp .env.example .env    # 填你有的出图 API 密钥（填一家就能跑）
```

| 智能体 | 怎么用 |
|---|---|
| **Claude Code** | 在仓库目录里打开即可（读 `CLAUDE.md`）；或 `install.sh` 后在任何目录用 `aigc-film-factory` skill |
| **Codex** | 在仓库目录里打开（读 `AGENTS.md`）；或 `install.sh` 后作为 skill 加载 |
| **WorkBuddy / CodeBuddy** | 支持 SKILL.md 格式 skill 的版本：`./install.sh <它的 skills 目录>`（默认会试 `~/.codebuddy/skills`）；不支持的版本把仓库作为工作目录，让它先读 `SKILL.md` |
| **其他智能体** | 把仓库作为工作目录，或把 `SKILL.md` 的内容作为系统提示词，并允许它读写本仓库文件、运行 `python3` |

依赖：Python 3.9+（出图转 PNG 建议 `pip install pillow`）；白模预演需要 Blender 4.x 和 ffmpeg（没有也能用，只交 B 版）。

## 用法

对智能体说：

```
~start 我的项目名
```

或者直接说"帮我出几个故事创意""这是我的剧本，做成 Seedance 提示词"。它会先问立项信息（风格、画幅、时长、出图 API、有没有 Blender），然后只在**故事**和**剧本**两处让你确认，之后一次交付全部文档。

出图（付费，先看路由再出）：

```bash
python3 -I tools/image_gen.py --providers
python3 -I tools/image_gen.py projects/<项目>/交付/01-资产提示词.md --out projects/<项目>/交付/资产图 --dry-run
python3 -I tools/image_gen.py projects/<项目>/交付/01-资产提示词.md --out projects/<项目>/交付/资产图
```

白模预演与机检：

```bash
python3 tools/previs/render_previs.py tools/previs/examples/示例_门口对峙.json --out /tmp/previs
python3 tools/prompt_lint.py projects/<项目>/交付/02-Seedance提示词.md --all
```

## 目录

```
├── SKILL.md / AGENTS.md / CLAUDE.md   # 智能体入口（通用 / Codex 等 / Claude Code）
├── docs/
│   ├── 02-Seedance2.5提示词圣经.md      # 40 条引擎规则、十二段式、表演/声音/运镜、十六问
│   ├── 03-30秒电影化叙事法.md
│   ├── 06-一次成片方法论.md              # 降抽卡、复杂度预算
│   ├── 07-30秒以上长片衔接.md
│   ├── 09-两文档交付模式.md              # 默认流程与 A/B 双版本
│   ├── 10-出图模型技巧.md                # 四个出图模型的选型、写法、接口
│   ├── 11-故事灵感库.md                  # 用户口味样本（换成你自己喜欢的片子）
│   ├── 12-框架审核评估.md
│   └── 00/01/04/05/08                    # 调研、完整模式、质检、目录契约、精简模式
├── crew/                     # 25 个岗位（SOUL.md + SKILL.md）
├── .claude/agents/           # Claude Code subagent 定义（其他智能体可忽略）
├── templates/                # 交付文档模板与其他模板
├── config/image_providers.json   # 出图引擎与接口配置
├── tools/
│   ├── prompt_lint.py        # 提示词机检
│   ├── image_gen.py          # 多接口出图（duomi_image.py 是旧命令兼容壳）
│   └── previs/               # 白模预演：规格 JSON 渲染器、公共库、范例
└── projects/                 # 你的项目（只有示例项目进仓库）
```

## 岗位（按流水线顺序，25 个）

| 阶段 | 岗位 | 负责 |
|---|---|---|
| 统筹 | 总制片人 | 立项、选模式、调度、门禁、预算、付费生成前取得授权 |
| P0.5 参考 | 风格参考总监 | 把参考导演/参考电影拆成叙事、视听、表演、声音四层可执行参数，只学方法不抄镜头 |
| P1–P2 编剧 | 故事架构师 / 编剧 / 剧本医生（审） | 故事圣经与分场表（每场 ≤30 秒戏核）→ 剧本 → 对抗式审稿 |
| P3 导演 | 总导演 | 全片调性、视觉论点、每场 30 秒时间建筑；所有创作分歧的最终裁决 |
| P4 开发 | 摄影指导（兼灯光）/ 美术指导（兼道具）/ 角色造型师 / 表演指导 / 声音导演 / 台词对白导演 | 影像圣经；场景、空间地图、道具操作机制；角色护照与压测；表演母本；音色锁与声音世界；全片台词总表与容量预审 |
| P5 资产 | Image 2.5 资产提示词大师 / 多模态资产主管 | 《资产提示词总册》：人物三视图单图、道具状态图、场景主图与宫格多视角；登记、版本、对账 |
| P6 分镜与调度 | 文戏导演 / 武戏导演 / VFX 导演 / 台词对白导演 / 声音导演 / 分镜师 | 按场次类型出调度与覆盖、动作因果、特效设计；台词时间表（每句第几秒、话轮、口型）；逐镜声音设计；镜头卡、首帧、站位示意图 |
| P6 门6 | 总导演 + 剪辑调色师 | 创作审 + 剪辑预审（覆盖够不够剪、接缝能不能接、节奏对不对） |
| P7 编译 | Seedance 编译师 | 十二段式提示词（一个作者，五道内部关）+ 素材接线单 + 一次成片签字单 |
| P8 四签 | 资产主管对账 → 场记 / 提示词独立质检官 / 合规官 / 总导演 | 连续性与台词逐字；对抗审查、红色一票否决；合规；创作放行 |
| P9 审片 | 审片质检员（汇总）+ 表演指导、台词对白导演、声音导演、场记分维度打分 | 24 分制审片与修复循环 |
| P10 后期 | 剪辑调色师 / 后期声音与混音师 | 剪辑、调色、字幕、交付；对白清理、接缝环境声、配乐、混音、响度 |

## 三种模式

- **两文档交付（默认）**：用户确认两次，后台一次合成，见 `docs/09`。
- **完整模式**：25 个岗位、12 阶段、9 道门禁，见 `docs/01`。
- **精简模式**：30 秒–5 分钟，18 个席位，见 `docs/08`。

## 知识来源

调研了 [awesome-short-drama-skills](https://github.com/wp746/awesome-short-drama-skills) 收录的 83 个 skill 仓库（538 个 SKILL.md），评级见 `docs/00`。主要吸收自：即梦官方《Seedance 2.5 User Guide》快照（liyue-aigc）、Higgsfield 开源的 95 分钟 AI 长片生产手册与表演系统（OSideMedia）、Seedance 2.5 运镜编译器与长度规范（babicat4242-svg）、CINEDANCE 与对白演技（UncleWang2088）、goodcase.ai 实测模板库（LearnPrompt）、资产护照与压力测试（machina-exm），以及编剧盲测中胜出的几套编剧 skill。

模型能力以你账号的实际界面为准。界面和《圣经》不一致时，按界面提交，并把差异记进项目的 `logs/平台差异.md`。
