"""delivery-flow 插件 CLI 启动器：免安装，从插件根直接跑。

Skill 内统一调用：python "${CLAUDE_PLUGIN_ROOT}/delivery.py" <cmd> --root . --json
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE / "scripts"))

if __name__ == "__main__":
    sys.exit(runpy.run_module("delivery_flow.cli", run_name="__main__").get("main", lambda: 1)())