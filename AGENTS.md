# AGENTS.md

本仓库是 **AIGC 制片工厂**：把一句创意或剧本做成可直接复制粘贴的 Seedance 2.5 视频提示词和资产出图提示词。

**任何智能体（Codex、WorkBuddy / CodeBuddy、Cursor、Claude Code 等）在本仓库工作时，先完整读 `SKILL.md`，按它的流程与"按需加载"表执行。** 本文件只是入口。

要点：
- 默认两文档交付：`交付/01-资产提示词.md`（每张图标推荐出图模型）和 `交付/02-Seedance提示词.md`（每条 A 白模预演版 + B 无预演版）。用户只确认故事和剧本两次。
- 用户项目放在 `projects/<项目名>/`；示例在 `projects/_示例-雨夜还钥匙/`。
- 写完 Seedance 提示词必须跑 `python3 tools/prompt_lint.py projects/<项目>/交付/02-Seedance提示词.md --all`，全部通过才交付。
- 出图与出视频都是付费调用：只在用户明确要求并确认花费后执行；先 `--dry-run`。
- 密钥只放 `.env`（模板 `.env.example`），不得写进文档或提交。
- 始终用中文和用户交流。
