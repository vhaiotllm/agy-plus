#!/usr/bin/env python3
"""
AGY Plus Native MCP Server (stdio JSON-RPC 2.0, MCP 2025-03-26 / 2024-11-05).
Exposes Claude Code & OpenAI Codex capabilities as native first-class tools in Antigravity:
- memory_save, memory_search, memory_list, memory_forget
- goal_create, goal_list, goal_update, ralph_loop_start, ralph_loop_cancel
- checkpoint_list, checkpoint_diff, checkpoint_restore
- session_search
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine  # noqa: E402

TOOLS: List[Dict[str, Any]] = [
    {
        "name": "memory_save",
        "description": "Save a persistent cross-session memory (project convention, architecture fact, pitfall, or user preference). Syncs to SQLite FTS5 and MEMORY.md.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Concise, actionable fact or rule to remember across sessions."},
                "title": {"type": "string", "description": "Short topic label (used to deduplicate/update existing memory on the same topic)."},
                "scope": {"type": "string", "enum": ["workspace", "global"], "description": "Default 'workspace'; use 'global' for machine-wide preferences."},
                "workspace": {"type": "string", "description": "Absolute workspace path (defaults to current working directory when scope='workspace')."},
                "tags": {"type": "string", "description": "Optional comma-separated tags (e.g. 'auth,db,deploy')."},
            },
            "required": ["content"],
        },
    },
    {
        "name": "memory_search",
        "description": "Full-text search (FTS5) across persistent project and global memories.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keywords to search in saved memories."},
                "workspace": {"type": "string", "description": "Optional workspace path filter."},
                "limit": {"type": "integer", "description": "Max results (default 15)."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "memory_list",
        "description": "List saved persistent memories for the current workspace and global scope.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace": {"type": "string", "description": "Optional workspace path."},
                "include_global": {"type": "boolean", "description": "Include global memories (default true)."},
            },
        },
    },
    {
        "name": "memory_forget",
        "description": "Delete a saved persistent memory by integer ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "description": "Memory ID to remove."},
            },
            "required": ["id"],
        },
    },
    {
        "name": "goal_create",
        "description": "Create a persistent goal (Codex-style goal tracking across turns/sessions).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "objective": {"type": "string", "description": "Concrete, measurable objective."},
                "workspace": {"type": "string", "description": "Workspace directory path."},
                "verify_cmd": {"type": "string", "description": "Optional shell command to verify goal completion (e.g. 'npm test && npx tsc --noEmit')."},
            },
            "required": ["objective"],
        },
    },
    {
        "name": "goal_list",
        "description": "List persistent goals and active Ralph loops.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace": {"type": "string", "description": "Optional workspace path."},
                "status": {"type": "string", "description": "Optional status filter: active, paused, blocked, complete."},
            },
        },
    },
    {
        "name": "goal_update",
        "description": "Update a persistent goal's status ('active', 'paused', 'blocked', 'complete') or notes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "description": "Goal ID."},
                "status": {"type": "string", "enum": ["active", "paused", "blocked", "complete"]},
                "notes": {"type": "string", "description": "Progress or completion notes."},
            },
            "required": ["id"],
        },
    },
    {
        "name": "ralph_loop_start",
        "description": "Start a Claude-style Ralph autonomous completion loop backed by AGY's Stop hook. Keeps iterating until <promise>COMPLETION_PROMISE</promise> is emitted and optional verify_cmd passes, up to max_iterations.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "objective": {"type": "string", "description": "Task objective for the autonomous loop."},
                "max_iterations": {"type": "integer", "description": "Maximum Stop-hook continuations (default 8, max 30)."},
                "completion_promise": {"type": "string", "description": "Promise token inside <promise>...</promise> (default 'DONE')."},
                "verify_cmd": {"type": "string", "description": "Optional shell command run automatically before allowing completion (e.g. 'npm test')."},
                "workspace": {"type": "string", "description": "Workspace root path."},
                "conversation_id": {"type": "string", "description": "Optional current conversation ID."},
            },
            "required": ["objective"],
        },
    },
    {
        "name": "ralph_loop_cancel",
        "description": "Cancel/pause active Ralph autonomous loops for the current conversation or workspace.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "conversation_id": {"type": "string", "description": "Optional conversation ID."},
                "workspace": {"type": "string", "description": "Optional workspace path."},
            },
        },
    },
    {
        "name": "checkpoint_list",
        "description": "List automatic pre-edit file-history checkpoints (Claude /undo time-travel snapshots).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace": {"type": "string", "description": "Optional workspace path."},
                "file_path": {"type": "string", "description": "Optional specific file path."},
                "limit": {"type": "integer", "description": "Max entries to return (default 20)."},
            },
        },
    },
    {
        "name": "checkpoint_diff",
        "description": "Show unified diff between a pre-edit checkpoint snapshot and the current file on disk.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "checkpoint_id": {"type": "integer", "description": "Checkpoint ID from checkpoint_list."},
            },
            "required": ["checkpoint_id"],
        },
    },
    {
        "name": "checkpoint_restore",
        "description": "Time-travel undo: restore a file to a pre-edit checkpoint (safely snapshots current file state first so undo itself is reversible).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "checkpoint_id": {"type": "integer", "description": "Specific checkpoint ID to restore (omit to restore latest matching)."},
                "file_path": {"type": "string", "description": "Optional file path to restore latest checkpoint for."},
                "workspace": {"type": "string", "description": "Optional workspace path."},
            },
        },
    },
    {
        "name": "session_search",
        "description": "Search past conversation history and transcripts across Antigravity (agy), Claude Code, and OpenAI Codex on this machine.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keyword or phrase (empty string lists most recent sessions)."},
                "limit": {"type": "integer", "description": "Max results (default 15)."},
            },
        },
    },
]


def _call_tool(name: str, args: Dict[str, Any]) -> Any:
    default_ws = args.get("workspace") or os.getcwd()
    if name == "memory_save":
        scope = args.get("scope", "workspace")
        ws = "" if scope == "global" else default_ws
        return engine.memory_save(
            content=args["content"],
            scope=scope,
            workspace=ws,
            title=args.get("title", ""),
            tags=args.get("tags", ""),
        )
    if name == "memory_search":
        return engine.memory_search(args["query"], workspace=args.get("workspace", default_ws), limit=int(args.get("limit", 15)))
    if name == "memory_list":
        return engine.memory_list(workspace=args.get("workspace", default_ws), include_global=bool(args.get("include_global", True)))
    if name == "memory_forget":
        return {"deleted": engine.memory_forget(int(args["id"])), "id": int(args["id"])}
    if name == "goal_create":
        return engine.goal_create(
            objective=args["objective"],
            workspace=default_ws,
            verify_cmd=args.get("verify_cmd", ""),
        )
    if name == "goal_list":
        return engine.goal_list(workspace=args.get("workspace", ""), status=args.get("status", ""))
    if name == "goal_update":
        res = engine.goal_update(int(args["id"]), status=args.get("status", ""), notes=args.get("notes", ""))
        if not res:
            raise ValueError(f"Goal #{args['id']} not found")
        return res
    if name == "ralph_loop_start":
        raw_max = int(args.get("max_iterations", -1))
        max_it = -1 if raw_max <= 0 else min(100000, raw_max)
        return engine.goal_create(
            objective=args["objective"],
            workspace=default_ws,
            conversation_id=args.get("conversation_id", os.environ.get("ANTIGRAVITY_CONVERSATION_ID", "")),
            max_iterations=max_it,
            completion_promise=args.get("completion_promise", "DONE"),
            verify_cmd=args.get("verify_cmd", ""),
        )
    if name == "ralph_loop_cancel":
        cnt = engine.ralph_cancel(
            conversation_id=args.get("conversation_id", ""),
            workspace=args.get("workspace", default_ws),
        )
        return {"cancelled_loops": cnt}
    if name == "checkpoint_list":
        return engine.checkpoint_list(
            workspace=args.get("workspace", default_ws),
            file_path=args.get("file_path", ""),
            limit=int(args.get("limit", 20)),
        )
    if name == "checkpoint_diff":
        return engine.checkpoint_diff(int(args["checkpoint_id"]))
    if name == "checkpoint_restore":
        cid = int(args["checkpoint_id"]) if args.get("checkpoint_id") is not None else None
        return engine.checkpoint_restore(
            checkpoint_id=cid,
            workspace=args.get("workspace", default_ws),
            file_path=args.get("file_path", ""),
        )
    if name == "session_search":
        return engine.session_search(query=args.get("query", ""), limit=int(args.get("limit", 15)))
    raise ValueError(f"Unknown tool: {name}")


def _send(msg: Dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main() -> None:
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        s = line.strip()
        if not s:
            continue
        # Support optional Content-Length framing just in case
        if s.lower().startswith("content-length:"):
            length = int(s.split(":", 1)[1].strip())
            while sys.stdin.readline().strip():
                pass
            body = sys.stdin.read(length)
            s = body.strip()
        try:
            req = json.loads(s)
        except Exception:
            continue

        method = req.get("method", "")
        req_id = req.get("id")
        params = req.get("params") or {}

        # Notifications have no id
        if req_id is None:
            continue

        if method == "initialize":
            client_pv = params.get("protocolVersion", "2025-03-26")
            pv = client_pv if client_pv in ("2025-06-18", "2025-03-26", "2024-11-05") else "2025-03-26"
            _send(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": pv,
                        "capabilities": {"tools": {"listChanged": False}},
                        "serverInfo": {"name": "agy-plus", "version": "1.0.0"},
                    },
                }
            )
        elif method == "ping":
            _send({"jsonrpc": "2.0", "id": req_id, "result": {}})
        elif method == "tools/list":
            _send({"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}})
        elif method == "resources/list":
            _send({"jsonrpc": "2.0", "id": req_id, "result": {"resources": []}})
        elif method == "prompts/list":
            _send({"jsonrpc": "2.0", "id": req_id, "result": {"prompts": []}})
        elif method == "tools/call":
            tname = params.get("name", "")
            targs = params.get("arguments") or {}
            try:
                res = _call_tool(tname, targs)
                txt = res if isinstance(res, str) else json.dumps(res, indent=2, ensure_ascii=False)
                _send(
                    {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {"content": [{"type": "text", "text": txt}], "isError": False},
                    }
                )
            except Exception as exc:
                _send(
                    {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {"content": [{"type": "text", "text": f"Error: {exc}"}], "isError": True},
                    }
                )
        else:
            _send(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                }
            )


if __name__ == "__main__":
    main()
