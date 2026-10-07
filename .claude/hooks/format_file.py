# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""PostToolUse hook: format a file Claude just edited.

frontend/ -> prettier (from frontend/node_modules), backend/*.py -> ruff format.
Skips silently when the formatter isn't installed yet; never blocks.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

PRETTIER_EXTS = {".ts", ".tsx", ".js", ".jsx", ".json", ".css", ".html", ".md"}


def run(cmd: list[str], cwd: Path) -> None:
    try:
        subprocess.run(cmd, cwd=cwd, capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        pass


def main() -> None:
    data = json.load(sys.stdin)
    file_path = data.get("tool_input", {}).get("file_path")
    if not file_path:
        return
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or ".").resolve()
    path = Path(file_path).resolve()
    try:
        rel = path.relative_to(root)
    except ValueError:
        return  # outside the repo
    if not rel.parts:
        return

    if rel.parts[0] == "frontend" and path.suffix in PRETTIER_EXTS:
        frontend = root / "frontend"
        prettier = frontend / "node_modules" / "prettier" / "bin" / "prettier.cjs"
        if prettier.exists():
            run(["node", str(prettier), "--write", str(path)], frontend)

    elif rel.parts[0] == "backend" and path.suffix == ".py":
        backend = root / "backend"
        if (backend / ".venv").exists():
            run(["uv", "run", "--no-sync", "ruff", "format", str(path)], backend)


if __name__ == "__main__":
    main()
