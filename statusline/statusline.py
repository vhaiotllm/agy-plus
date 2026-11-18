#!/usr/bin/env python3
"""
AGY Plus Enhanced Statusline HUD (Claude Code Powerline + OpenAI Codex TUI style).
Displays: [Workspace & Git Branch/Dirty] | [Context Window %] | [Model (Effort)] | [Quota %] | [Ralph/Goals · Memories · Undo]
"""

import json
import os
import subprocess
import sys
from pathlib import Path

PLUS_DIR = Path.home() / ".gemini" / "antigravity-cli" / "agy_plus"
if PLUS_DIR.is_dir():
    sys.path.insert(0, str(PLUS_DIR))


def format_tokens(num: int) -> str:
    if num >= 1_000_000:
        return f"{num / 1_000_000:.1f}M"
    if num >= 1_000:
        return f"{num / 1_000:.1f}k"
    return str(num)


def get_git_segment(cwd: str) -> str:
    if not cwd or not os.path.isdir(cwd):
        return ""
    name = os.path.basename(os.path.abspath(cwd)) or cwd
    try:
        branch = subprocess.check_output(
            ["git", "-C", cwd, "rev-parse", "--abbrev-ref", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=0.12,
        ).strip()
        porcelain = subprocess.check_output(
            ["git", "-C", cwd, "status", "--porcelain", "-uno"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=0.12,
        ).splitlines()
        dirty = f"*{len(porcelain)}" if porcelain else ""
        return f"{name}:{branch}{dirty}"
    except Exception:
        return name


def main() -> None:
    try:
        raw = sys.stdin.read()
        if not raw:
            return
        data = json.loads(raw)

        cwd = (
            data.get("cwd")
            or (data.get("workspace") or {}).get("current_dir")
            or os.getcwd()
        )
        ctx = data.get("context_window") or {}
        model = data.get("model") or {}

        in_tokens = int(ctx.get("total_input_tokens") or 0)
        out_tokens = int(ctx.get("total_output_tokens") or 0)
        total_tokens = in_tokens + out_tokens

        window_size = int(ctx.get("context_window_size") or 1_048_576)
        used_pct = float(ctx.get("used_percentage") or 0.0)
        if not used_pct and window_size > 0:
            used_pct = (total_tokens / window_size) * 100.0

        model_name = model.get("display_name") or model.get("id") or "Gemini"
        effort = model.get("effort")
        if effort and f"({effort.lower()})" not in model_name.lower():
            model_name = f"{model_name} ({effort})"

        CYAN = "\033[36m"
        GREEN = "\033[32m"
        YELLOW = "\033[33m"
        RED = "\033[31m"
        MAGENTA = "\033[35m"
        BLUE = "\033[34m"
        DIM = "\033[2m"
        RESET = "\033[0m"

        sep = f" {DIM}|{RESET} "
        segments = []

        git_seg = get_git_segment(cwd)
        if git_seg:
            segments.append(f"{BLUE}{git_seg}{RESET}")

        ctx_color = GREEN if used_pct < 50 else (YELLOW if used_pct < 80 else RED)
        segments.append(
            f"{ctx_color}Ctx: {format_tokens(total_tokens)}/{format_tokens(window_size)} ({used_pct:.1f}%){RESET}"
        )
        segments.append(f"{CYAN}{model_name}{RESET}")

        quota = data.get("quota") or {}
        for qkey in ("gemini-5h", "default", "claude-5h"):
            qobj = quota.get(qkey)
            if isinstance(qobj, dict) and qobj.get("remaining_fraction") is not None:
                q_pct = int(float(qobj["remaining_fraction"]) * 100)
                q_col = GREEN if q_pct > 30 else (YELLOW if q_pct > 10 else RED)
                segments.append(f"{q_col}Quota: {q_pct}%{RESET}")
                break

        try:
            import engine  # type: ignore

            badges = engine.get_statusline_badges(cwd)
            plus_items = []
            if badges.get("ralph"):
                plus_items.append(f"{MAGENTA}Ralph:{badges['ralph']}{RESET}")
            elif badges.get("active_goals", 0) > 0:
                plus_items.append(f"{MAGENTA}Goals:{badges['active_goals']}{RESET}")
            if badges.get("memories", 0) > 0:
                plus_items.append(f"{GREEN}Mem:{badges['memories']}{RESET}")
            if badges.get("checkpoints", 0) > 0:
                plus_items.append(f"{YELLOW}Undo:{badges['checkpoints']}{RESET}")
            if plus_items:
                segments.append(" ".join(plus_items))
        except Exception:
            pass

        print(sep.join(f"[{s}]" for s in segments))
    except Exception:
        pass


if __name__ == "__main__":
    main()
