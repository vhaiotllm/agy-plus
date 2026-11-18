#!/usr/bin/env python3
"""
AGY Plus Lifecycle Hooks Runner.
Strictly implements Antigravity's camelCase hooks.json stdin/stdout contract:
- SessionStart   -> {"injectSteps": [...]} or {}
- PreToolUse     -> {"decision": "allow"|"deny", "reason": "..."}
- PostToolUse    -> {}
- PreInvocation  -> {"injectSteps": [...]} or {}
- Stop           -> {"decision": "continue"|"stop", "reason": "..."}
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine  # noqa: E402


def _primary_workspace(payload: dict) -> str:
    cwd = payload.get("cwd") or ""
    if cwd:
        return cwd
    wps = payload.get("workspacePaths") or []
    return wps[0] if wps else ""


def handle_session_start(payload: dict) -> dict:
    conv_id = payload.get("conversationId", "")
    ws = _primary_workspace(payload)
    engine.capture_shell_snapshot(conv_id, ws)
    ctx = engine.get_session_startup_context(ws)
    if not ctx:
        return {}
    return {
        "injectSteps": [
            {
                "systemMessage": {
                    "systemMessage": ctx
                }
            }
        ]
    }


def handle_pre_tool_use(payload: dict) -> dict:
    conv_id = payload.get("conversationId", "")
    ws = _primary_workspace(payload)
    step_idx = int(payload.get("stepIdx") or 0)
    tc = payload.get("toolCall") or {}
    tname = (tc.get("name") or "").lower()
    args = tc.get("args") or {}

    if tname in ("run_command",):
        cmd = str(args.get("CommandLine") or "")
        cat_block = engine.check_catastrophic_command(cmd)
        if cat_block:
            return {"decision": "deny", "reason": cat_block}
        hk_block = engine.evaluate_hookify("bash", cmd, ws, conv_id)
        if hk_block:
            return {"decision": "deny", "reason": hk_block}
        return {"decision": "allow"}

    if tname in ("edit_file", "write_file", "replace_file_content", "multi_replace_file_content", "write_to_file"):
        fpath = str(args.get("Path") or args.get("TargetFile") or "")
        new_body = str(args.get("Replacement") or args.get("Content") or args.get("CodeContent") or "")
        if fpath:
            engine.checkpoint_capture(conv_id, ws, step_idx, tname, fpath)
        hk_block = engine.evaluate_hookify("file", f"{fpath}\n{new_body}", ws, conv_id)
        if hk_block:
            return {"decision": "deny", "reason": hk_block}
        if fpath and new_body:
            engine.scan_file_security(conv_id, fpath, new_body)
        return {"decision": "allow"}

    return {"decision": "allow"}


def handle_pre_invocation(payload: dict) -> dict:
    conv_id = payload.get("conversationId", "")
    ws = _primary_workspace(payload)
    last_input = str(payload.get("lastUserInput") or "")
    if last_input:
        hk_block = engine.evaluate_hookify("prompt", last_input, ws, conv_id)
        if hk_block:
            return {
                "injectSteps": [{"errorMessage": {"userMessage": hk_block}}],
                "terminationBehavior": "terminate",
            }

    advisories = engine.pop_pending_advisories(conv_id)
    if not advisories:
        return {}
    joined = "\n\n".join(advisories)
    return {
        "injectSteps": [
            {
                "systemMessage": {
                    "systemMessage": f"<AGY_SECURITY_AND_HOOKIFY_ADVISORY>\n{joined}\n</AGY_SECURITY_AND_HOOKIFY_ADVISORY>"
                }
            }
        ]
    }


def handle_stop(payload: dict) -> dict:
    term_reason = payload.get("terminationReason", "")
    if term_reason and term_reason != "NO_TOOL_CALL":
        return {"decision": "stop"}
    if not payload.get("fullyIdle", True):
        return {"decision": "stop"}
    conv_id = payload.get("conversationId", "")
    ws = _primary_workspace(payload)
    # Evaluate nonstop + Ralph-Loop first (handles root vs subagent + real-user verification gate)
    ralph_or_nonstop = engine.ralph_evaluate_stop(payload)
    if ralph_or_nonstop.get("decision") == "continue":
        return ralph_or_nonstop
    if engine.is_root_user_conversation(conv_id, payload.get("transcriptPath", "")):
        hk_stop = engine.evaluate_hookify("stop", "stop", ws, conv_id)
        if hk_stop:
            return {"decision": "continue", "reason": hk_stop}
    return ralph_or_nonstop


def main() -> None:
    event_arg = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        payload = {}

    event = event_arg or payload.get("hookEventName", "")
    try:
        if event == "SessionStart":
            out = handle_session_start(payload)
        elif event == "PreToolUse":
            out = handle_pre_tool_use(payload)
        elif event == "PostToolUse":
            out = {}
        elif event == "PreInvocation":
            out = handle_pre_invocation(payload)
        elif event == "Stop":
            out = handle_stop(payload)
        else:
            out = {}
    except Exception:
        # Fail-open safely so hooks never break an agent turn
        out = {"decision": "allow"} if event == "PreToolUse" else ({"decision": "stop"} if event == "Stop" else {})

    sys.stdout.write(json.dumps(out) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
