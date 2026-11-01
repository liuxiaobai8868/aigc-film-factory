# 更新记录

## 0.9.0（2026-11-01）· 发布候选
- 打包为通用 skill：`SKILL.md`（通用入口）、`AGENTS.md`（Codex 等）、`CLAUDE.md`（Claude Code），`install.sh` 一键链接到各智能体的 skills 目录。
- 视频提示词每条交 A 白模预演版 + B 无预演版，写推荐理由；lint 分别检查并核对两版台词与切点一致。
- 新增白模预演工具 `tools/previs/`：镜头规格 JSON 一键渲染预演视频与关键帧拼图。
- 新增多接口出图 `tools/image_gen.py` + `config/image_providers.json`：多米、OpenAI、OpenAI 兼容中转、Google Gemini、火山方舟；每张图按推荐模型自动路由，接口不全时顺延。
- 圣经引擎规则扩到 40 条：事故复盘（18–26）、优秀提示词样本提炼（27–40）；长镜头必须写明理由（视觉张力 / 情绪层次 / 推进剧情）。
- 新增故事灵感库（docs/11）与框架审核评估（docs/12）。
