#!/usr/bin/env python3
"""兼容旧命令：等同于 tools/image_gen.py --provider duomi。

  python3 -I tools/duomi_image.py <资产提示词.md> --out <目录> [--engine gpt|mj|banana] [--only 1,3] [--force]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import image_gen  # noqa: E402

if "--provider" not in sys.argv:
    sys.argv += ["--provider", "duomi"]
if "--engine" not in sys.argv:
    sys.argv += ["--engine", "image25"]
image_gen.main()
