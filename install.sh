#!/usr/bin/env bash
# 把本仓库作为名为 aigc-film-factory 的 skill 链接进各智能体的 skills 目录。
# 用法：
#   ./install.sh                 # 自动找 ~/.claude、~/.codex、~/.codebuddy，存在哪个装哪个
#   ./install.sh <skills目录>     # 装到指定目录（如你的智能体用别的路径）
set -euo pipefail
REPO="$(cd "$(dirname "$0")" && pwd)"
NAME="aigc-film-factory"

link_into() {
  local dir="$1"
  mkdir -p "$dir"
  if [ -e "$dir/$NAME" ] && [ ! -L "$dir/$NAME" ]; then
    echo "跳过 $dir/$NAME：已存在且不是链接，请先手动处理"
    return
  fi
  ln -sfn "$REPO" "$dir/$NAME"
  echo "已安装：$dir/$NAME -> $REPO"
}

if [ $# -ge 1 ]; then
  link_into "$1"
else
  found=0
  for home in "$HOME/.claude" "$HOME/.codex" "$HOME/.codebuddy"; do
    if [ -d "$home" ]; then
      link_into "$home/skills"
      found=1
    fi
  done
  [ $found -eq 1 ] || echo "没找到 ~/.claude、~/.codex 或 ~/.codebuddy：用 ./install.sh <skills目录> 指定位置"
fi

[ -f "$REPO/.env" ] || echo "提示：cp .env.example .env 并填入你有的出图 API 密钥"
command -v ffmpeg >/dev/null || echo "提示：没有 ffmpeg，白模预演不可用（只能交 B 无预演版）"
