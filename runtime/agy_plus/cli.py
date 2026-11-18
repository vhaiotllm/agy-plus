#!/usr/bin/env python3
"""
AGY Plus Power CLI (`agy-plus` & subcommands injected into `agy` shell wrapper):
  agy memory   [list | add <text> [--global] [--title T] | search <q> | rm <id>]
  agy undo     [list | diff <id> | restore [id|latest]]
  agy goals    [list | add <objective> | done <id> | pause <id>]
  agy ralph    [start <objective> [--max N] [--verify CMD] | status | cancel]
  agy nonstop  [status | on [mission] | off | run]
  agy sessions [list | search <query>]
  agy stats
  agy review   [uncommitted | <base-ref>]
  agy exec     <prompt...>
  agy doctor
"""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine  # noqa: E402


def _resolve_agy_bin() -> str:
    env_bin = os.environ.get("AGY_REAL_BIN")
    if env_bin and os.path.isfile(env_bin):
        return env_bin
    for candidate in (
        Path.home() / ".local" / "bin" / "agy",
        Path.home() / ".gemini" / "bin" / "agy",
    ):
        if candidate.is_file():
            return str(candidate)
    return shutil.which("agy") or "agy"


AGY_BIN = _resolve_agy_bin()
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def _fmt_ts(ms: int) -> str:
    if not ms:
        return "-"
    return dt.datetime.fromtimestamp(ms / 1000.0).strftime("%Y-%m-%d %H:%M")


def cmd_memory(args: List[str]) -> int:
    cwd = os.getcwd()
    sub = args[0] if args else "list"
    if sub == "list":
        items = engine.memory_list(workspace=cwd, include_global=True)
        if not items:
            print(f"{DIM}No saved memories yet. Use `agy memory add \"...\"` or `/memory` in TUI.{RESET}")
            return 0
        print(f"{BOLD}Saved Persistent Memories ({len(items)}):{RESET}")
        for m in items:
            badge = f"{CYAN}[global]{RESET}" if m["scope"] == "global" else f"{GREEN}[project]{RESET}"
            title = f" {BOLD}{m['title']}{RESET}:" if m["title"] else ""
            print(f"  #{m['id']:<3} {badge}{title} {m['content']} {DIM}({_fmt_ts(m['updated_at_ms'])}){RESET}")
        return 0

    if sub == "add":
        rest = args[1:]
        scope = "workspace"
        title = ""
        parts: List[str] = []
        i = 0
        while i < len(rest):
            if rest[i] in ("--global", "-g"):
                scope = "global"
            elif rest[i] in ("--title", "-t") and i + 1 < len(rest):
                title = rest[i + 1]
                i += 1
            else:
                parts.append(rest[i])
            i += 1
        text = " ".join(parts).strip()
        if not text:
            print("Usage: agy memory add [--global] [--title TITLE] <fact>")
            return 1
        res = engine.memory_save(content=text, scope=scope, workspace="" if scope == "global" else cwd, title=title, source="cli")
        print(f"{GREEN}✓ Memory #{res['id']} ({res['action']}) synced to {res['markdown_path']}{RESET}")
        return 0

    if sub == "search":
        items = engine.memory_search(" ".join(args[1:]).strip(), workspace=cwd)
        for m in items:
            print(f"  #{m['id']:<3} [{m['scope']}] {m['title'] + ': ' if m['title'] else ''}{m['content']}")
        if not items:
            print("No matching memories.")
        return 0

    if sub in ("rm", "del", "delete", "forget") and len(args) > 1:
        ok = engine.memory_forget(int(args[1]))
        print(f"{GREEN}✓ Deleted memory #{args[1]}{RESET}" if ok else f"{RED}Memory #{args[1]} not found{RESET}")
        return 0 if ok else 1

    print("Usage: agy memory [list | add [--global] [--title T] <text> | search <query> | rm <id>]")
    return 1


def cmd_undo(args: List[str]) -> int:
    cwd = os.getcwd()
    sub = args[0] if args else "list"
    if sub == "list":
        items = engine.checkpoint_list(workspace=cwd, limit=20) or engine.checkpoint_list(limit=20)
        if not items:
            print(f"{DIM}No file-history checkpoints recorded yet.{RESET}")
            return 0
        print(f"{BOLD}File-History Checkpoints (most recent first):{RESET}")
        for c in items:
            state = "edit" if c["existed_before"] else "new-file"
            print(f"  #{c['id']:<4} {_fmt_ts(c['created_at_ms'])}  [{state:<8}] {c['file_path']} ({c['byte_size']} B)")
        print(f"{DIM}Tip: `agy undo diff <id>` or `agy undo restore [id|latest]`{RESET}")
        return 0

    if sub == "diff" and len(args) > 1:
        print(engine.checkpoint_diff(int(args[1])))
        return 0

    if sub == "restore":
        target = args[1] if len(args) > 1 else "latest"
        cid = None if target == "latest" else int(target)
        res = engine.checkpoint_restore(checkpoint_id=cid, workspace=cwd if cid is None else "")
        print(f"{GREEN}✓ Restored checkpoint #{res['restored_checkpoint_id']} -> {res['file_path']} ({res['action']}){RESET}")
        return 0

    print("Usage: agy undo [list | diff <id> | restore [id|latest]]")
    return 1


def cmd_goals(args: List[str]) -> int:
    cwd = os.getcwd()
    sub = args[0] if args else "list"
    if sub == "list":
        items = engine.goal_list(workspace=cwd)
        if not items:
            print(f"{DIM}No persistent goals found.{RESET}")
            return 0
        print(f"{BOLD}Persistent Goals:{RESET}")
        for g in items:
            r = f" [Ralph {g['iteration']}/{g['max_iterations']}]" if g["max_iterations"] > 0 else ""
            print(f"  #{g['id']:<3} [{g['status']:<8}]{r} {g['objective']} {DIM}({_fmt_ts(g['updated_at_ms'])}){RESET}")
        return 0

    if sub == "add" and len(args) > 1:
        g = engine.goal_create(objective=" ".join(args[1:]).strip(), workspace=cwd)
        print(f"{GREEN}✓ Created persistent goal #{g['id']}: {g['objective']}{RESET}")
        return 0

    if sub in ("done", "complete") and len(args) > 1:
        engine.goal_update(int(args[1]), status="complete")
        print(f"{GREEN}✓ Marked goal #{args[1]} complete{RESET}")
        return 0

    if sub == "pause" and len(args) > 1:
        engine.goal_update(int(args[1]), status="paused")
        print(f"{YELLOW}⏸ Paused goal #{args[1]}{RESET}")
        return 0

    print("Usage: agy goals [list | add <objective> | done <id> | pause <id>]")
    return 1


def cmd_ralph(args: List[str]) -> int:
    cwd = os.getcwd()
    sub = args[0] if args else "status"
    if sub == "status":
        items = [g for g in engine.goal_list(workspace=cwd) if g["max_iterations"] > 0]
        if not items:
            print(f"{DIM}No Ralph autonomous loops configured.{RESET}")
            return 0
        for g in items:
            print(f"  #{g['id']} [{g['status']}] iter={g['iteration']}/{g['max_iterations']} verify=`{g['verify_cmd']}` :: {g['objective']}")
        return 0

    if sub == "cancel":
        cnt = engine.ralph_cancel(workspace=cwd)
        print(f"{YELLOW}✓ Cancelled {cnt} active Ralph loop(s).{RESET}")
        return 0

    if sub == "start" and len(args) > 1:
        rest = args[1:]
        max_it = 8
        verify_cmd = ""
        promise = "DONE"
        obj_parts: List[str] = []
        i = 0
        while i < len(rest):
            if rest[i] == "--max" and i + 1 < len(rest):
                max_it = int(rest[i + 1])
                i += 2
            elif rest[i] == "--verify" and i + 1 < len(rest):
                verify_cmd = rest[i + 1]
                i += 2
            elif rest[i] == "--promise" and i + 1 < len(rest):
                promise = rest[i + 1]
                i += 2
            else:
                obj_parts.append(rest[i])
                i += 1
        obj = " ".join(obj_parts).strip()
        g = engine.goal_create(objective=obj, workspace=cwd, max_iterations=max_it, completion_promise=promise, verify_cmd=verify_cmd)
        print(f"{GREEN}✓ Armed Ralph-Loop #{g['id']} (max={max_it}, promise=<promise>{promise}</promise>). Launching AGY...{RESET}")
        return subprocess.call([AGY_BIN, "--dangerously-skip-permissions", "-i", f"{obj}\n\n(Ralph-Loop active: output <promise>{promise}</promise> only when 100% complete and verified.)"])

    print("Usage: agy ralph [start <objective> [--max N] [--verify CMD] | status | cancel]")
    return 1


def cmd_nonstop(args: List[str]) -> int:
    sub = args[0] if args else "status"
    if sub == "status":
        st = engine.nonstop_status()
        badge = f"{GREEN}ACTIVE{RESET}" if st["enabled"] else f"{YELLOW}PAUSED{RESET}"
        print(f"{BOLD}=== AGY Non-Stop Continuous Mode ==={RESET}")
        print(f"  Status  : {badge}")
        print(f"  Cycle   : {CYAN}#{st['cycle']}{RESET}")
        print(f"  Mission : {st['mission']}")
        return 0

    if sub in ("on", "enable", "start"):
        st = engine.nonstop_configure(True, mission=" ".join(args[1:]).strip())
        print(f"{GREEN}✓ Non-Stop Mode ENABLED (Cycle #{st['cycle']}).{RESET}")
        return 0

    if sub in ("off", "disable", "stop"):
        engine.nonstop_configure(False)
        print(f"{YELLOW}⏸ Non-Stop Mode PAUSED.{RESET}")
        return 0

    if sub == "run":
        engine.nonstop_configure(True)
        projects = engine.load_projects_config()
        add_dirs: List[str] = []
        for p in projects:
            pp = os.path.expanduser(str(p.get("path") or ""))
            if pp and os.path.isdir(pp):
                add_dirs.extend(["--add-dir", pp])
        print(f"{GREEN}∞ Starting Foreground AGY Continuous Loop... (Ctrl+C to stop){RESET}")
        while True:
            st = engine.nonstop_status()
            if not st["enabled"]:
                return 0
            cycle = int(st["cycle"]) + 1
            engine.kv_set("nonstop_cycle", str(cycle))
            rc = subprocess.call([AGY_BIN, "--dangerously-skip-permissions", *add_dirs, "-p", f"[NON-STOP CYCLE #{cycle}] {st['mission']}"])
            time.sleep(3 if rc == 0 else 10)

    print("Usage: agy nonstop [status | on [mission] | off | run]")
    return 1


def cmd_sessions(args: List[str]) -> int:
    sub = args[0] if args else "list"
    q = " ".join(args[1:]) if sub == "search" else ("" if sub == "list" else " ".join(args))
    rows = engine.session_search(q, limit=25)
    print(f"{BOLD}Cross-Agent Sessions (AGY + Claude + Codex) [{len(rows)}]:{RESET}")
    for r in rows:
        cid = (r["conversation_id"] or "-")[:12]
        print(f"  [{r['agent']:<14}] {_fmt_ts(int(r['timestamp_ms'] or 0))}  id={cid:<12}  {r['snippet'][:90]}")
    return 0


def cmd_stats(_args: List[str]) -> int:
    brain = engine.AGY_DIR / "brain"
    convs = list(brain.glob("*/.system_generated/logs/transcript.jsonl")) if brain.is_dir() else []
    total_steps = user_prompts = tool_calls = subagents = 0
    tool_freq: dict[str, int] = {}

    for tf in convs:
        for ln in tf.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                o = json.loads(ln)
            except Exception:
                continue
            total_steps += 1
            if o.get("type") == "USER_INPUT":
                user_prompts += 1
            for tc in o.get("tool_calls") or []:
                tool_calls += 1
                tn = tc.get("name") or tc.get("tool_name") or "tool"
                tool_freq[tn] = tool_freq.get(tn, 0) + 1
                if tn == "invoke_subagent":
                    subagents += 1

    badges = engine.get_statusline_badges(os.getcwd())
    print(f"{BOLD}=== AGY Plus Telemetry & Session Report ==={RESET}")
    print(f"  Conversations analyzed : {CYAN}{len(convs)}{RESET}")
    print(f"  User prompts           : {CYAN}{user_prompts}{RESET}")
    print(f"  Total trajectory steps : {CYAN}{total_steps}{RESET}")
    print(f"  Tool invocations       : {CYAN}{tool_calls}{RESET} (Subagents spawned: {subagents})")
    print(f"  Persistent memories    : {GREEN}{badges['memories']}{RESET}")
    print(f"  Undo file checkpoints  : {GREEN}{badges['checkpoints']}{RESET}")
    if tool_freq:
        top = sorted(tool_freq.items(), key=lambda kv: kv[1], reverse=True)[:8]
        print("  Top tools              : " + ", ".join(f"{k}({v})" for k, v in top))
    return 0


def cmd_review(args: List[str]) -> int:
    target = args[0] if args else "uncommitted"
    if target == "uncommitted":
        prompt = (
            "Perform a defect-first code review (Codex/Claude style) of all uncommitted changes (`git status` and `git diff HEAD`). "
            "Report only concrete bugs, security issues, silent failures, race conditions, or type/logic regressions with file:line citations and severity."
        )
    else:
        prompt = (
            f"Perform a defect-first code review comparing HEAD against `{target}` (`git diff {target}...HEAD`). "
            "Report concrete bugs, security vulnerabilities, silent failures, and regressions with file:line citations."
        )
    return subprocess.call([AGY_BIN, "--dangerously-skip-permissions", "-p", prompt])


def cmd_exec(args: List[str]) -> int:
    if not args:
        print("Usage: agy exec <prompt...>")
        return 1
    return subprocess.call([AGY_BIN, "--dangerously-skip-permissions", "-p", " ".join(args)])


def cmd_doctor() -> int:
    print(f"{BOLD}=== AGY Plus System Doctor ==={RESET}")
    checks = [
        ("AGY Binary", shutil.which(AGY_BIN) is not None or os.path.isfile(AGY_BIN)),
        ("SQLite FTS5 DB", engine.get_db() is not None),
        ("ripgrep (rg)", shutil.which("rg") is not None),
        ("fd-find (fd)", shutil.which("fd") is not None or shutil.which("fdfind") is not None),
        ("GitHub CLI (gh)", shutil.which("gh") is not None),
        ("Core Plugin (agy-core-plus)", (engine.CONFIG_DIR / "plugins" / "agy-core-plus" / "plugin.json").is_file()),
        ("Engineering Fleet Plugin", (engine.CONFIG_DIR / "plugins" / "agy-engineering-fleet" / "plugin.json").is_file()),
        ("MCP Config (mcp_config.json)", (engine.CONFIG_DIR / "mcp_config.json").is_file()),
    ]
    for label, ok in checks:
        mark = f"{GREEN}✓ OK{RESET}" if ok else f"{RED}✗ MISSING{RESET}"
        print(f"  {label:<32} : {mark}")

    if shutil.which(AGY_BIN) or os.path.isfile(AGY_BIN):
        for pdir in sorted((engine.CONFIG_DIR / "plugins").glob("*")) if (engine.CONFIG_DIR / "plugins").is_dir() else []:
            if (pdir / "plugin.json").is_file():
                rc = subprocess.call([AGY_BIN, "plugin", "validate", str(pdir), "--strict"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                mark = f"{GREEN}✓ VALID (--strict){RESET}" if rc == 0 else f"{RED}✗ INVALID{RESET}"
                print(f"  Plugin validate `{pdir.name}` : {mark}")
    return 0


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print(__doc__.strip())
        return 0
    cmd = sys.argv[1]
    rest = sys.argv[2:]
    dispatch = {
        "memory": cmd_memory,
        "undo": cmd_undo,
        "goals": cmd_goals,
        "ralph": cmd_ralph,
        "nonstop": cmd_nonstop,
        "sessions": cmd_sessions,
        "stats": cmd_stats,
        "report": cmd_stats,
        "review": cmd_review,
        "exec": cmd_exec,
    }
    if cmd == "doctor":
        return cmd_doctor()
    if cmd in dispatch:
        return dispatch[cmd](rest)
    print(f"Unknown agy-plus command: {cmd}\n" + __doc__.strip())
    return 1


if __name__ == "__main__":
    sys.exit(main())
