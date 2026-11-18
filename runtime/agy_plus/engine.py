#!/usr/bin/env python3
"""
AGY Plus Core Engine — Portable Edition (Linux & macOS).
Brings Claude Code & OpenAI Codex flagship capabilities to Antigravity (agy):
1. Persistent Auto-Memory (SQLite FTS5 + bi-directional MEMORY.md sync)
2. Persistent Goals, Ralph-Loop & Non-Stop Continuous Mode (Stop-hook verified continuation)
3. Automatic File-History Checkpoints & Time-Travel Undo (SHA-256 compressed blobs)
4. Shell Environment Snapshots
5. Security Guidance + Catastrophic Command Guard + Declarative Hookify Rules
6. Cross-Agent Session Search & Usage Analytics (AGY + Claude Code + Codex)
"""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import time
import zlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

HOME = Path.home()
AGY_DIR = Path(os.environ.get("ANTIGRAVITY_APP_DATA_DIR", str(HOME / ".gemini" / "antigravity-cli")))
CONFIG_DIR = HOME / ".gemini" / "config"
PLUS_DIR = AGY_DIR / "agy_plus"
DB_PATH = PLUS_DIR / "agy_plus.db"
PROJECTS_CONFIG_PATH = PLUS_DIR / "projects.json"
MEMORIES_DIR = AGY_DIR / "memories"
CHECKPOINTS_DIR = AGY_DIR / "file-history"
BLOBS_DIR = CHECKPOINTS_DIR / "blobs"
SHELL_SNAPSHOTS_DIR = AGY_DIR / "shell-snapshots"
HOOKIFY_GLOBAL_DIR = CONFIG_DIR / "hookify"

MAX_CHECKPOINTS_RETAINED = 600
MAX_FILE_CHECKPOINT_BYTES = 8 * 1024 * 1024


def _now_ms() -> int:
    return int(time.time() * 1000)


def workspace_slug(workspace: str) -> str:
    if not workspace:
        return "global"
    clean = os.path.abspath(os.path.expanduser(workspace)).strip("/")
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "_", clean)
    return slug[-96:] if len(slug) > 96 else (slug or "root")


def get_db() -> sqlite3.Connection:
    PLUS_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=3.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=3000")
    _init_schema(conn)
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS kv_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at_ms INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scope TEXT NOT NULL DEFAULT 'workspace',
            workspace TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL DEFAULT '',
            content TEXT NOT NULL,
            tags TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT 'agent',
            created_at_ms INTEGER NOT NULL,
            updated_at_ms INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_memories_ws ON memories(scope, workspace);

        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace TEXT NOT NULL DEFAULT '',
            conversation_id TEXT NOT NULL DEFAULT '',
            objective TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            iteration INTEGER NOT NULL DEFAULT 0,
            max_iterations INTEGER NOT NULL DEFAULT 0,
            completion_promise TEXT NOT NULL DEFAULT 'DONE',
            verify_cmd TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            created_at_ms INTEGER NOT NULL,
            updated_at_ms INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_goals_ws_status ON goals(workspace, status);
        CREATE INDEX IF NOT EXISTS idx_goals_conv ON goals(conversation_id, status);

        CREATE TABLE IF NOT EXISTS checkpoints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL DEFAULT '',
            workspace TEXT NOT NULL DEFAULT '',
            step_idx INTEGER NOT NULL DEFAULT 0,
            tool_name TEXT NOT NULL DEFAULT '',
            file_path TEXT NOT NULL,
            existed_before INTEGER NOT NULL DEFAULT 1,
            sha256 TEXT NOT NULL DEFAULT '',
            byte_size INTEGER NOT NULL DEFAULT 0,
            created_at_ms INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_checkpoints_path ON checkpoints(file_path, created_at_ms DESC);
        CREATE INDEX IF NOT EXISTS idx_checkpoints_ws ON checkpoints(workspace, created_at_ms DESC);

        CREATE TABLE IF NOT EXISTS advisories_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            dedup_key TEXT NOT NULL,
            message TEXT NOT NULL,
            delivered INTEGER NOT NULL DEFAULT 0,
            created_at_ms INTEGER NOT NULL,
            UNIQUE(conversation_id, dedup_key)
        );
        """
    )
    try:
        conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                title, content, tags, workspace, content='memories', content_rowid='id'
            )
            """
        )
    except sqlite3.OperationalError:
        pass
    conn.commit()


def _rebuild_fts(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("INSERT INTO memories_fts(memories_fts) VALUES('rebuild')")
    except sqlite3.OperationalError:
        pass


def kv_get(key: str, default: str = "") -> str:
    try:
        with get_db() as conn:
            row = conn.execute("SELECT value FROM kv_state WHERE key=?", (key,)).fetchone()
            return str(row["value"]) if row else default
    except Exception:
        return default


def kv_set(key: str, value: str) -> None:
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO kv_state(key, value, updated_at_ms) VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at_ms=excluded.updated_at_ms
            """,
            (key, str(value), _now_ms()),
        )
        conn.commit()


def load_projects_config() -> List[Dict[str, Any]]:
    if not PROJECTS_CONFIG_PATH.is_file():
        return []
    try:
        data = json.loads(PROJECTS_CONFIG_PATH.read_text(encoding="utf-8", errors="ignore"))
        return list(data.get("projects") or [])
    except Exception:
        return []


# ============================================================================
# 1. PERSISTENT AUTO-MEMORY (Claude MEMORY.md + Codex SQLite FTS5)
# ============================================================================

def memory_md_path(workspace: str = "") -> Path:
    MEMORIES_DIR.mkdir(parents=True, exist_ok=True)
    if not workspace:
        return MEMORIES_DIR / "GLOBAL_MEMORY.md"
    d = MEMORIES_DIR / workspace_slug(workspace)
    d.mkdir(parents=True, exist_ok=True)
    return d / "MEMORY.md"


def _export_memories_to_markdown(conn: sqlite3.Connection, workspace: str = "") -> Path:
    scope = "global" if not workspace else "workspace"
    ws_norm = "" if not workspace else os.path.abspath(os.path.expanduser(workspace))
    rows = conn.execute(
        "SELECT id, title, content, tags, updated_at_ms FROM memories WHERE scope=? AND workspace=? ORDER BY id ASC",
        (scope, ws_norm),
    ).fetchall()
    md_file = memory_md_path(ws_norm)
    header = "# AGY Global Memory\n" if scope == "global" else f"# AGY Workspace Memory (`{ws_norm}`)\n"
    lines = [
        header,
        "<!-- Synced automatically by AGY Plus. You may also add `- Fact` bullets manually. -->\n",
    ]
    for r in rows:
        tag_str = f" `[{r['tags']}]`" if r["tags"] else ""
        title_str = f"**{r['title']}**: " if r["title"] else ""
        lines.append(f"- <!-- id:{r['id']} --> {title_str}{r['content'].strip()}{tag_str}")
    md_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_file


def import_manual_markdown_memories(workspace: str = "") -> int:
    ws_norm = "" if not workspace else os.path.abspath(os.path.expanduser(workspace))
    md_file = memory_md_path(ws_norm)
    if not md_file.is_file():
        return 0
    text = md_file.read_text(encoding="utf-8", errors="ignore")
    added = 0
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("- ") or "<!-- id:" in s:
            continue
        body = s[2:].strip()
        if not body:
            continue
        memory_save(content=body, scope="global" if not ws_norm else "workspace", workspace=ws_norm, source="manual_md")
        added += 1
    return added


def memory_save(
    content: str,
    scope: str = "workspace",
    workspace: str = "",
    title: str = "",
    tags: str = "",
    source: str = "agent",
) -> Dict[str, Any]:
    content = content.strip()
    if not content:
        raise ValueError("Memory content cannot be empty")
    if scope == "global" or not workspace:
        scope = "global"
        ws_norm = ""
    else:
        scope = "workspace"
        ws_norm = os.path.abspath(os.path.expanduser(workspace))

    now = _now_ms()
    with get_db() as conn:
        if title:
            existing = conn.execute(
                "SELECT id FROM memories WHERE scope=? AND workspace=? AND title=?",
                (scope, ws_norm, title.strip()),
            ).fetchone()
        else:
            existing = conn.execute(
                "SELECT id FROM memories WHERE scope=? AND workspace=? AND content=?",
                (scope, ws_norm, content),
            ).fetchone()

        if existing:
            mem_id = existing["id"]
            conn.execute(
                "UPDATE memories SET content=?, tags=?, updated_at_ms=? WHERE id=?",
                (content, tags.strip(), now, mem_id),
            )
            action = "updated"
        else:
            cur = conn.execute(
                """
                INSERT INTO memories(scope, workspace, title, content, tags, source, created_at_ms, updated_at_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (scope, ws_norm, title.strip(), content, tags.strip(), source, now, now),
            )
            mem_id = cur.lastrowid
            action = "created"

        _rebuild_fts(conn)
        conn.commit()
        md_path = _export_memories_to_markdown(conn, ws_norm)

    return {"id": mem_id, "action": action, "scope": scope, "workspace": ws_norm, "markdown_path": str(md_path)}


def memory_list(workspace: str = "", include_global: bool = True, limit: int = 50) -> List[Dict[str, Any]]:
    ws_norm = os.path.abspath(os.path.expanduser(workspace)) if workspace else ""
    import_manual_markdown_memories("")
    if ws_norm:
        import_manual_markdown_memories(ws_norm)

    with get_db() as conn:
        if ws_norm and include_global:
            rows = conn.execute(
                """
                SELECT * FROM memories
                WHERE scope='global' OR (scope='workspace' AND workspace=?)
                ORDER BY scope DESC, updated_at_ms DESC LIMIT ?
                """,
                (ws_norm, limit),
            ).fetchall()
        elif ws_norm:
            rows = conn.execute(
                "SELECT * FROM memories WHERE scope='workspace' AND workspace=? ORDER BY updated_at_ms DESC LIMIT ?",
                (ws_norm, limit),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM memories ORDER BY updated_at_ms DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def memory_search(query: str, workspace: str = "", limit: int = 20) -> List[Dict[str, Any]]:
    q = query.strip()
    if not q:
        return memory_list(workspace=workspace, limit=limit)
    ws_norm = os.path.abspath(os.path.expanduser(workspace)) if workspace else ""
    with get_db() as conn:
        rows = []
        try:
            fts_q = " OR ".join(f'"{tok}"' for tok in re.findall(r"\w+", q) if tok)
            if fts_q:
                if ws_norm:
                    rows = conn.execute(
                        """
                        SELECT m.* FROM memories_fts f
                        JOIN memories m ON m.id = f.rowid
                        WHERE memories_fts MATCH ? AND (m.scope='global' OR m.workspace=?)
                        ORDER BY rank LIMIT ?
                        """,
                        (fts_q, ws_norm, limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT m.* FROM memories_fts f
                        JOIN memories m ON m.id = f.rowid
                        WHERE memories_fts MATCH ?
                        ORDER BY rank LIMIT ?
                        """,
                        (fts_q, limit),
                    ).fetchall()
        except sqlite3.OperationalError:
            rows = []

        if not rows:
            like = f"%{q}%"
            if ws_norm:
                rows = conn.execute(
                    """
                    SELECT * FROM memories
                    WHERE (title LIKE ? OR content LIKE ? OR tags LIKE ?)
                      AND (scope='global' OR workspace=?)
                    ORDER BY updated_at_ms DESC LIMIT ?
                    """,
                    (like, like, like, ws_norm, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM memories
                    WHERE title LIKE ? OR content LIKE ? OR tags LIKE ?
                    ORDER BY updated_at_ms DESC LIMIT ?
                    """,
                    (like, like, like, limit),
                ).fetchall()
    return [dict(r) for r in rows]


def memory_forget(mem_id: int) -> bool:
    with get_db() as conn:
        row = conn.execute("SELECT workspace, scope FROM memories WHERE id=?", (mem_id,)).fetchone()
        if not row:
            return False
        conn.execute("DELETE FROM memories WHERE id=?", (mem_id,))
        _rebuild_fts(conn)
        conn.commit()
        _export_memories_to_markdown(conn, row["workspace"] if row["scope"] == "workspace" else "")
        return True


# ============================================================================
# 2. PERSISTENT GOALS, RALPH-LOOP & NON-STOP ENGINE
# ============================================================================

def goal_create(
    objective: str,
    workspace: str = "",
    conversation_id: str = "",
    max_iterations: int = 0,
    completion_promise: str = "DONE",
    verify_cmd: str = "",
) -> Dict[str, Any]:
    ws_norm = os.path.abspath(os.path.expanduser(workspace)) if workspace else ""
    now = _now_ms()
    with get_db() as conn:
        cur = conn.execute(
            """
            INSERT INTO goals(workspace, conversation_id, objective, status, iteration, max_iterations,
                              completion_promise, verify_cmd, created_at_ms, updated_at_ms)
            VALUES (?, ?, ?, 'active', 0, ?, ?, ?, ?, ?)
            """,
            (ws_norm, conversation_id, objective.strip(), max_iterations, completion_promise.strip(), verify_cmd.strip(), now, now),
        )
        conn.commit()
        return dict(conn.execute("SELECT * FROM goals WHERE id=?", (cur.lastrowid,)).fetchone())


def goal_list(workspace: str = "", status: str = "") -> List[Dict[str, Any]]:
    ws_norm = os.path.abspath(os.path.expanduser(workspace)) if workspace else ""
    sql = "SELECT * FROM goals WHERE 1=1"
    params: List[Any] = []
    if ws_norm:
        sql += " AND (workspace=? OR workspace='')"
        params.append(ws_norm)
    if status:
        sql += " AND status=?"
        params.append(status)
    sql += " ORDER BY updated_at_ms DESC LIMIT 50"
    with get_db() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def goal_update(goal_id: int, status: str = "", notes: str = "") -> Optional[Dict[str, Any]]:
    now = _now_ms()
    with get_db() as conn:
        row = conn.execute("SELECT * FROM goals WHERE id=?", (goal_id,)).fetchone()
        if not row:
            return None
        conn.execute(
            "UPDATE goals SET status=?, notes=?, updated_at_ms=? WHERE id=?",
            (status or row["status"], notes if notes != "" else row["notes"], now, goal_id),
        )
        conn.commit()
        return dict(conn.execute("SELECT * FROM goals WHERE id=?", (goal_id,)).fetchone())


def ralph_cancel(conversation_id: str = "", workspace: str = "") -> int:
    now = _now_ms()
    ws_norm = os.path.abspath(os.path.expanduser(workspace)) if workspace else ""
    with get_db() as conn:
        if conversation_id:
            cur = conn.execute(
                "UPDATE goals SET status='paused', updated_at_ms=? WHERE status='active' AND max_iterations > 0 AND conversation_id=?",
                (now, conversation_id),
            )
        elif ws_norm:
            cur = conn.execute(
                "UPDATE goals SET status='paused', updated_at_ms=? WHERE status='active' AND max_iterations > 0 AND workspace=?",
                (now, ws_norm),
            )
        else:
            cur = conn.execute(
                "UPDATE goals SET status='paused', updated_at_ms=? WHERE status='active' AND max_iterations > 0",
                (now,),
            )
        conn.commit()
        return cur.rowcount


def nonstop_status() -> Dict[str, Any]:
    enabled = kv_get("nonstop_mode", "off") == "on"
    cycle = int(kv_get("nonstop_cycle", "0") or "0")
    mission = kv_get(
        "nonstop_mission",
        "Continuously inspect, test, fix bugs, improve UX/performance, and verify configured projects until zero defects.",
    )
    return {"enabled": enabled, "cycle": cycle, "mission": mission}


def nonstop_configure(enabled: bool, mission: str = "") -> Dict[str, Any]:
    kv_set("nonstop_mode", "on" if enabled else "off")
    if mission.strip():
        kv_set("nonstop_mission", mission.strip())
    return nonstop_status()


def is_root_user_conversation(conversation_id: str, transcript_path: str = "") -> bool:
    candidates: List[str] = []
    if transcript_path:
        candidates.append(transcript_path)
    if conversation_id:
        candidates.append(str(AGY_DIR / "brain" / conversation_id / ".system_generated" / "logs" / "transcript.jsonl"))
    for tp in candidates:
        if tp and os.path.isfile(tp):
            try:
                with open(tp, "r", encoding="utf-8", errors="ignore") as f:
                    first_line = f.readline().strip()
                if first_line:
                    obj = json.loads(first_line)
                    src = str(obj.get("source") or "")
                    content = str(obj.get("content") or "")
                    if src and src != "USER_EXPLICIT" and "<USER_REQUEST>" not in content:
                        return False
                    return True
            except Exception:
                return True
    return True


def _last_assistant_text(transcript_path: str) -> str:
    if not transcript_path or not os.path.isfile(transcript_path):
        return ""
    try:
        with open(transcript_path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - 65536))
            tail = f.read().decode("utf-8", errors="ignore")
        for ln in reversed([l for l in tail.splitlines() if l.strip()]):
            try:
                obj = json.loads(ln)
            except Exception:
                continue
            if obj.get("type") == "PLANNER_RESPONSE" or obj.get("source") == "MODEL":
                content = obj.get("content") or ""
                if isinstance(content, str) and content.strip():
                    return content
    except Exception:
        pass
    return ""


def ralph_evaluate_stop(payload: Dict[str, Any]) -> Dict[str, Any]:
    term_reason = payload.get("terminationReason", "")
    if term_reason and term_reason != "NO_TOOL_CALL":
        return {"decision": "stop"}
    if not payload.get("fullyIdle", True):
        return {"decision": "stop"}

    conv_id = payload.get("conversationId", "")
    transcript_path = payload.get("transcriptPath", "")
    if not is_root_user_conversation(conv_id, transcript_path):
        return {"decision": "stop"}

    cwd = payload.get("cwd") or ((payload.get("workspacePaths") or [""])[0])
    ws_norm = os.path.abspath(os.path.expanduser(cwd)) if cwd else ""

    ns = nonstop_status()
    if ns["enabled"] and not payload.get("continuationActive", False):
        cyc = int(ns["cycle"]) + 1
        kv_set("nonstop_cycle", str(cyc))
        return {
            "decision": "continue",
            "reason": f"[Non-Stop Cycle #{cyc}] Active mission: {ns['mission']}",
        }

    with get_db() as conn:
        row = None
        if conv_id:
            row = conn.execute(
                "SELECT * FROM goals WHERE status='active' AND max_iterations > 0 AND conversation_id=? ORDER BY id DESC LIMIT 1",
                (conv_id,),
            ).fetchone()
        if not row and ws_norm:
            row = conn.execute(
                "SELECT * FROM goals WHERE status='active' AND max_iterations > 0 AND conversation_id='' AND workspace=? ORDER BY id DESC LIMIT 1",
                (ws_norm,),
            ).fetchone()
        if not row:
            return {"decision": "stop"}

        goal = dict(row)
        gid = goal["id"]
        iteration = int(goal["iteration"])
        max_iter = int(goal["max_iterations"])
        promise = goal["completion_promise"] or "DONE"
        verify_cmd = goal["verify_cmd"]
        promise_tag = f"<promise>{promise}</promise>"
        promise_met = promise_tag in _last_assistant_text(transcript_path)

        if promise_met:
            if verify_cmd:
                try:
                    proc = subprocess.run(
                        verify_cmd,
                        shell=True,
                        cwd=ws_norm or None,
                        capture_output=True,
                        text=True,
                        timeout=25,
                    )
                    if proc.returncode == 0:
                        conn.execute("UPDATE goals SET status='complete', updated_at_ms=? WHERE id=?", (_now_ms(), gid))
                        conn.commit()
                        return {"decision": "stop"}
                    if iteration >= max_iter:
                        conn.execute(
                            "UPDATE goals SET status='blocked', notes='Max iterations reached with failing verify_cmd', updated_at_ms=? WHERE id=?",
                            (_now_ms(), gid),
                        )
                        conn.commit()
                        return {"decision": "stop"}
                    next_it = iteration + 1
                    conn.execute(
                        "UPDATE goals SET iteration=?, conversation_id=?, updated_at_ms=? WHERE id=?",
                        (next_it, conv_id or goal["conversation_id"], _now_ms(), gid),
                    )
                    conn.commit()
                    err_tail = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()[-1200:]
                    return {
                        "decision": "continue",
                        "reason": (
                            f"[Ralph-Loop {next_it}/{max_iter}] Verification `{verify_cmd}` failed (exit {proc.returncode}):\n"
                            f"```\n{err_tail}\n```\nFix the failures, re-verify, and emit `{promise_tag}`."
                        ),
                    }
                except subprocess.TimeoutExpired:
                    pass
            else:
                conn.execute("UPDATE goals SET status='complete', updated_at_ms=? WHERE id=?", (_now_ms(), gid))
                conn.commit()
                return {"decision": "stop"}

        if iteration >= max_iter:
            conn.execute("UPDATE goals SET status='paused', notes='Reached max_iterations', updated_at_ms=? WHERE id=?", (_now_ms(), gid))
            conn.commit()
            return {"decision": "stop"}

        next_it = iteration + 1
        conn.execute(
            "UPDATE goals SET iteration=?, conversation_id=?, updated_at_ms=? WHERE id=?",
            (next_it, conv_id or goal["conversation_id"], _now_ms(), gid),
        )
        conn.commit()
        verify_hint = f" Run `{verify_cmd}` to verify." if verify_cmd else ""
        return {
            "decision": "continue",
            "reason": (
                f"[Ralph-Loop Iteration {next_it}/{max_iter}] Objective: {goal['objective']}.{verify_hint} "
                f"Continue autonomously until 100% complete, then include `{promise_tag}`."
            ),
        }


# ============================================================================
# 3. AUTOMATIC FILE-HISTORY CHECKPOINTS & TIME-TRAVEL UNDO
# ============================================================================

def checkpoint_capture(
    conversation_id: str,
    workspace: str,
    step_idx: int,
    tool_name: str,
    file_path: str,
) -> Optional[int]:
    if not file_path:
        return None
    abs_path = os.path.abspath(os.path.expanduser(file_path))
    if str(PLUS_DIR) in abs_path or str(CHECKPOINTS_DIR) in abs_path:
        return None

    ws_norm = os.path.abspath(os.path.expanduser(workspace)) if workspace else ""
    existed = os.path.isfile(abs_path)
    sha = ""
    bsize = 0

    if existed:
        try:
            st = os.stat(abs_path)
            bsize = st.st_size
            if bsize > MAX_FILE_CHECKPOINT_BYTES:
                return None
            raw = Path(abs_path).read_bytes()
            sha = hashlib.sha256(raw).hexdigest()
            blob_sub = BLOBS_DIR / sha[:2]
            blob_sub.mkdir(parents=True, exist_ok=True)
            blob_file = blob_sub / sha
            if not blob_file.exists():
                blob_file.write_bytes(zlib.compress(raw, level=6))
        except Exception:
            return None

    now = _now_ms()
    with get_db() as conn:
        last = conn.execute(
            "SELECT sha256, existed_before FROM checkpoints WHERE file_path=? AND conversation_id=? ORDER BY id DESC LIMIT 1",
            (abs_path, conversation_id),
        ).fetchone()
        if last and last["sha256"] == sha and int(last["existed_before"]) == (1 if existed else 0):
            return None

        cur = conn.execute(
            """
            INSERT INTO checkpoints(conversation_id, workspace, step_idx, tool_name, file_path,
                                    existed_before, sha256, byte_size, created_at_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (conversation_id, ws_norm, step_idx, tool_name, abs_path, 1 if existed else 0, sha, bsize, now),
        )
        cid = cur.lastrowid

        old_rows = conn.execute(
            "SELECT id, sha256 FROM checkpoints ORDER BY id DESC LIMIT -1 OFFSET ?",
            (MAX_CHECKPOINTS_RETAINED,),
        ).fetchall()
        if old_rows:
            conn.executemany("DELETE FROM checkpoints WHERE id=?", [(r["id"],) for r in old_rows])
            for r in old_rows:
                s = r["sha256"]
                if s and not conn.execute("SELECT 1 FROM checkpoints WHERE sha256=? LIMIT 1", (s,)).fetchone():
                    (BLOBS_DIR / s[:2] / s).unlink(missing_ok=True)
        conn.commit()
        return cid


def _read_blob(sha: str) -> bytes:
    if not sha:
        return b""
    bf = BLOBS_DIR / sha[:2] / sha
    if not bf.is_file():
        raise FileNotFoundError(f"Checkpoint blob missing for {sha[:12]}")
    return zlib.decompress(bf.read_bytes())


def checkpoint_list(workspace: str = "", conversation_id: str = "", file_path: str = "", limit: int = 25) -> List[Dict[str, Any]]:
    sql = "SELECT * FROM checkpoints WHERE 1=1"
    params: List[Any] = []
    if conversation_id:
        sql += " AND conversation_id=?"
        params.append(conversation_id)
    if workspace:
        ws_norm = os.path.abspath(os.path.expanduser(workspace))
        sql += " AND (workspace=? OR file_path LIKE ?)"
        params.extend([ws_norm, ws_norm + "/%"])
    if file_path:
        sql += " AND file_path=?"
        params.append(os.path.abspath(os.path.expanduser(file_path)))
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with get_db() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def checkpoint_diff(checkpoint_id: int) -> str:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM checkpoints WHERE id=?", (checkpoint_id,)).fetchone()
    if not row:
        return f"Checkpoint #{checkpoint_id} not found."
    fp = row["file_path"]
    old_text = _read_blob(row["sha256"]).decode("utf-8", errors="replace") if row["existed_before"] else ""
    new_text = Path(fp).read_text(encoding="utf-8", errors="replace") if os.path.isfile(fp) else ""
    diff = list(
        difflib.unified_diff(
            old_text.splitlines(keepends=True),
            new_text.splitlines(keepends=True),
            fromfile=f"{fp} (checkpoint #{checkpoint_id})",
            tofile=f"{fp} (current)",
        )
    )
    return "".join(diff) if diff else "No differences (current file matches checkpoint)."


def checkpoint_restore(checkpoint_id: Optional[int] = None, workspace: str = "", file_path: str = "") -> Dict[str, Any]:
    with get_db() as conn:
        if checkpoint_id is not None:
            row = conn.execute("SELECT * FROM checkpoints WHERE id=?", (checkpoint_id,)).fetchone()
        elif file_path:
            abs_fp = os.path.abspath(os.path.expanduser(file_path))
            row = conn.execute("SELECT * FROM checkpoints WHERE file_path=? ORDER BY id DESC LIMIT 1", (abs_fp,)).fetchone()
        elif workspace:
            ws_norm = os.path.abspath(os.path.expanduser(workspace))
            row = conn.execute(
                "SELECT * FROM checkpoints WHERE workspace=? OR file_path LIKE ? ORDER BY id DESC LIMIT 1",
                (ws_norm, ws_norm + "/%"),
            ).fetchone()
        else:
            row = conn.execute("SELECT * FROM checkpoints ORDER BY id DESC LIMIT 1").fetchone()

    if not row:
        raise ValueError("No matching checkpoint found to restore.")

    cp = dict(row)
    fp = cp["file_path"]
    checkpoint_capture(
        conversation_id=cp["conversation_id"] or "manual-undo",
        workspace=cp["workspace"],
        step_idx=0,
        tool_name="undo_backup",
        file_path=fp,
    )

    if cp["existed_before"]:
        Path(fp).parent.mkdir(parents=True, exist_ok=True)
        Path(fp).write_bytes(_read_blob(cp["sha256"]))
        action = "restored_content"
    else:
        if os.path.isfile(fp):
            os.remove(fp)
        action = "removed_newly_created_file"

    return {"restored_checkpoint_id": cp["id"], "file_path": fp, "action": action}


# ============================================================================
# 4. SHELL SNAPSHOTS + STARTUP INJECTION CONTEXT
# ============================================================================

def capture_shell_snapshot(conversation_id: str, cwd: str) -> None:
    if not conversation_id:
        return
    try:
        SHELL_SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        snap_file = SHELL_SNAPSHOTS_DIR / f"{conversation_id}.json"
        if snap_file.exists():
            return
        git_branch = ""
        git_head = ""
        if cwd and os.path.isdir(cwd):
            try:
                git_branch = subprocess.check_output(
                    ["git", "-C", cwd, "rev-parse", "--abbrev-ref", "HEAD"],
                    stderr=subprocess.DEVNULL, text=True, timeout=1.5
                ).strip()
                git_head = subprocess.check_output(
                    ["git", "-C", cwd, "rev-parse", "--short", "HEAD"],
                    stderr=subprocess.DEVNULL, text=True, timeout=1.5
                ).strip()
            except Exception:
                pass
        snap_file.write_text(
            json.dumps(
                {
                    "conversationId": conversation_id,
                    "cwd": cwd,
                    "timestamp": int(time.time()),
                    "gitBranch": git_branch,
                    "gitHead": git_head,
                    "PATH": os.environ.get("PATH", ""),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        snaps = sorted(SHELL_SNAPSHOTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in snaps[100:]:
            old.unlink(missing_ok=True)
    except Exception:
        pass


def get_session_startup_context(workspace: str = "") -> str:
    ws_norm = os.path.abspath(os.path.expanduser(workspace)) if workspace else ""
    memories = memory_list(workspace=ws_norm, include_global=True, limit=25)
    goals = goal_list(workspace=ws_norm, status="active")
    if not memories and not goals:
        return ""

    parts: List[str] = ["<AGY_PERSISTENT_CONTEXT>"]
    if goals:
        parts.append("## Active Persistent Goals")
        for g in goals[:5]:
            ralph_tag = f" (Ralph-Loop {g['iteration']}/{g['max_iterations']})" if g["max_iterations"] > 0 else ""
            parts.append(f"- [Goal #{g['id']}{ralph_tag}] {g['objective']}")
    if memories:
        parts.append("## Saved Cross-Session Memories")
        for m in memories[:20]:
            scope_badge = "[Global]" if m["scope"] == "global" else "[Project]"
            title = f" **{m['title']}**:" if m["title"] else ""
            parts.append(f"- {scope_badge}{title} {m['content']}")
    parts.append("</AGY_PERSISTENT_CONTEXT>")
    return "\n".join(parts)[:4000]


# ============================================================================
# 5. SECURITY GUIDANCE + CATASTROPHIC COMMAND BLOCKER + HOOKIFY
# ============================================================================

_CATASTROPHIC_CMD_PATTERNS = [
    (re.compile(r"(?:^|[;&|]\s*)(?:sudo\s+)?rm\s+-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\s+(?:/|/\*|\$HOME|~)(?:\s|$|;|&)"),
     "Blocked catastrophic root/home recursive deletion (`rm -rf /` or `rm -rf ~`). Scope deletion to a specific target path."),
    (re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:"),
     "Blocked shell fork bomb."),
    (re.compile(r"(?:^|[;&|]\s*)(?:sudo\s+)?mkfs(?:\.[a-z0-9]+)?\s+/dev/"),
     "Blocked filesystem format command (`mkfs`) on block device."),
    (re.compile(r"(?:^|[;&|]\s*)(?:sudo\s+)?dd\s+[^;|&]*of=/dev/(?:sd|vd|nvme|xvd|mmcblk)"),
     "Blocked raw block device overwrite (`dd of=/dev/...`)."),
]

_SECURITY_FILE_RULES = [
    (
        "gh_actions_injection",
        lambda p: ".github/workflows/" in p and p.endswith((".yml", ".yaml")),
        re.compile(r"run:\s*\|?[\s\S]{0,400}\$\{\{\s*github\.event\.(?:issue|pull_request|comment|review|commits|head_commit)\."),
        "Security Advisory (GitHub Actions): Untrusted `${{ github.event.* }}` interpolated inside `run:`. Pass untrusted event fields via `env:` variables and quote `\"$VAR\"`.",
    ),
    (
        "unsafe_python_deserialization",
        lambda p: p.endswith((".py", ".pyi")),
        re.compile(r"\b(?:pickle\.loads?|cPickle\.loads?|yaml\.unsafe_load|marshal\.loads)\s*\("),
        "Security Advisory (Python Deserialization): `pickle.load`/`yaml.unsafe_load`/`marshal.loads` can execute arbitrary code on untrusted input. Prefer `json`, `pydantic`, or `yaml.safe_load`.",
    ),
    (
        "hardcoded_private_key",
        lambda p: not p.endswith((".md", ".test.ts", ".test.js", ".spec.ts")),
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----|AKIA[0-9A-Z]{16}"),
        "Security Advisory (Secret Exposure): Detected a hardcoded private key or AWS access key literal in source file. Move secrets to `.env` (gitignored).",
    ),
    (
        "dom_xss_sink",
        lambda p: p.endswith((".tsx", ".jsx", ".ts", ".js", ".vue", ".svelte")),
        re.compile(r"dangerouslySetInnerHTML\s*="),
        "Security Advisory (XSS Sink): `dangerouslySetInnerHTML` detected. Verify HTML is sanitized or static before rendering.",
    ),
]


def check_catastrophic_command(command_line: str) -> Optional[str]:
    if not command_line:
        return None
    for rx, reason in _CATASTROPHIC_CMD_PATTERNS:
        if rx.search(command_line):
            return reason
    return None


def queue_advisory(conversation_id: str, dedup_key: str, message: str) -> None:
    if not conversation_id or not message:
        return
    with get_db() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO advisories_queue(conversation_id, dedup_key, message, delivered, created_at_ms)
            VALUES (?, ?, ?, 0, ?)
            """,
            (conversation_id, dedup_key, message, _now_ms()),
        )
        conn.commit()


def pop_pending_advisories(conversation_id: str) -> List[str]:
    if not conversation_id:
        return []
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, message FROM advisories_queue WHERE conversation_id=? AND delivered=0 ORDER BY id ASC",
            (conversation_id,),
        ).fetchall()
        if not rows:
            return []
        conn.executemany("UPDATE advisories_queue SET delivered=1 WHERE id=?", [(r["id"],) for r in rows])
        conn.commit()
        return [r["message"] for r in rows]


def scan_file_security(conversation_id: str, file_path: str, content_snippet: str) -> None:
    if not content_snippet or not file_path:
        return
    for rule_name, path_fn, rx, msg in _SECURITY_FILE_RULES:
        try:
            if path_fn(file_path) and rx.search(content_snippet):
                queue_advisory(conversation_id, f"{rule_name}:{file_path}", f"{msg} (File: `{file_path}`)")
        except Exception:
            continue


def _load_hookify_rules(workspace: str = "") -> List[Dict[str, Any]]:
    dirs: List[Tuple[Path, str]] = []
    if workspace:
        ws = Path(workspace)
        dirs.append((ws / ".agents", "hookify.*.md"))
        dirs.append((ws / ".claude", "hookify.*.local.md"))
    dirs.append((HOOKIFY_GLOBAL_DIR, "*.md"))

    rules: List[Dict[str, Any]] = []
    for base, pat in dirs:
        if not base.is_dir():
            continue
        for fp in sorted(base.glob(pat)):
            try:
                raw = fp.read_text(encoding="utf-8", errors="ignore")
                if not raw.startswith("---"):
                    continue
                parts = raw.split("---", 2)
                if len(parts) < 3:
                    continue
                fm_text, body = parts[1], parts[2].strip()
                meta: Dict[str, str] = {}
                for ln in fm_text.splitlines():
                    if ":" in ln:
                        k, v = ln.split(":", 1)
                        meta[k.strip()] = v.strip().strip('"').strip("'")
                if meta.get("enabled", "true").lower() == "false":
                    continue
                pattern = meta.get("pattern", "")
                if not pattern:
                    continue
                rules.append(
                    {
                        "name": meta.get("name", fp.stem),
                        "event": meta.get("event", "bash").lower(),
                        "action": meta.get("action", "warn").lower(),
                        "pattern": pattern,
                        "message": body or f"Hookify rule `{meta.get('name', fp.stem)}` matched `{pattern}`.",
                        "file": str(fp),
                    }
                )
            except Exception:
                continue
    return rules


def evaluate_hookify(event_kind: str, target_text: str, workspace: str, conversation_id: str) -> Optional[str]:
    if not target_text:
        return None
    for rule in _load_hookify_rules(workspace):
        if rule["event"] not in (event_kind, "all"):
            continue
        try:
            if re.search(rule["pattern"], target_text, flags=re.MULTILINE):
                if rule["action"] in ("block", "deny"):
                    return f"[Hookify `{rule['name']}`] {rule['message']}"
                queue_advisory(
                    conversation_id,
                    f"hookify:{rule['name']}:{hashlib.md5(target_text[:200].encode()).hexdigest()[:8]}",
                    f"[Hookify Warning `{rule['name']}`] {rule['message']}",
                )
        except re.error:
            continue
    return None


# ============================================================================
# 6. CROSS-AGENT UNIFIED SESSION SEARCH & ANALYTICS (AGY + Claude + Codex)
# ============================================================================

def session_search(query: str = "", limit: int = 20) -> List[Dict[str, Any]]:
    q = query.strip().lower()
    results: List[Dict[str, Any]] = []

    agy_hist = AGY_DIR / "history.jsonl"
    if agy_hist.is_file():
        for ln in reversed(agy_hist.read_text(encoding="utf-8", errors="ignore").splitlines()):
            try:
                item = json.loads(ln)
                disp = str(item.get("display", ""))
                if disp.startswith("/") and q:
                    continue
                if not q or q in disp.lower() or q in str(item.get("workspace", "")).lower():
                    results.append(
                        {
                            "agent": "agy",
                            "conversation_id": item.get("conversationId", ""),
                            "workspace": item.get("workspace", ""),
                            "snippet": disp[:240],
                            "timestamp_ms": item.get("timestamp", 0),
                        }
                    )
                    if len(results) >= limit * 2:
                        break
            except Exception:
                continue

    brain_dir = AGY_DIR / "brain"
    if q and brain_dir.is_dir() and len(results) < limit:
        for tfile in sorted(brain_dir.glob("*/.system_generated/logs/transcript.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)[:30]:
            conv_id = tfile.parents[2].name
            try:
                txt = tfile.read_text(encoding="utf-8", errors="ignore")
                if q in txt.lower():
                    for ln in txt.splitlines():
                        if q in ln.lower():
                            obj = json.loads(ln)
                            results.append(
                                {
                                    "agent": "agy-transcript",
                                    "conversation_id": conv_id,
                                    "workspace": "",
                                    "snippet": str(obj.get("content", ""))[:240],
                                    "timestamp_ms": int(tfile.stat().st_mtime * 1000),
                                }
                            )
                            break
            except Exception:
                continue

    claude_hist = HOME / ".claude" / "history.jsonl"
    if claude_hist.is_file():
        for ln in reversed(claude_hist.read_text(encoding="utf-8", errors="ignore").splitlines()):
            try:
                item = json.loads(ln)
                disp = str(item.get("display", ""))
                if not q or q in disp.lower() or q in str(item.get("project", "")).lower():
                    results.append(
                        {
                            "agent": "claude",
                            "conversation_id": item.get("sessionId", ""),
                            "workspace": item.get("project", ""),
                            "snippet": disp[:240],
                            "timestamp_ms": item.get("timestamp", 0),
                        }
                    )
                    if len(results) >= limit * 3:
                        break
            except Exception:
                continue

    codex_idx = HOME / ".codex" / "session_index.jsonl"
    if codex_idx.is_file():
        for ln in reversed(codex_idx.read_text(encoding="utf-8", errors="ignore").splitlines()):
            try:
                item = json.loads(ln)
                title = str(item.get("thread_name") or item.get("summary") or ln)
                if not q or q in title.lower():
                    results.append(
                        {
                            "agent": "codex",
                            "conversation_id": item.get("id", ""),
                            "workspace": item.get("cwd", ""),
                            "snippet": title[:240],
                            "timestamp_ms": int(codex_idx.stat().st_mtime * 1000),
                        }
                    )
                    if len(results) >= limit * 4:
                        break
            except Exception:
                continue

    results.sort(key=lambda r: int(r.get("timestamp_ms") or 0), reverse=True)
    return results[:limit]


def get_statusline_badges(workspace: str = "") -> Dict[str, Any]:
    ws_norm = os.path.abspath(os.path.expanduser(workspace)) if workspace else ""
    try:
        with get_db() as conn:
            if ws_norm:
                mem_cnt = conn.execute("SELECT COUNT(*) FROM memories WHERE scope='global' OR workspace=?", (ws_norm,)).fetchone()[0]
                active_goals = conn.execute(
                    "SELECT iteration, max_iterations FROM goals WHERE status='active' AND (workspace=? OR workspace='') ORDER BY id DESC",
                    (ws_norm,),
                ).fetchall()
                undo_cnt = conn.execute(
                    "SELECT COUNT(*) FROM checkpoints WHERE workspace=? OR file_path LIKE ?",
                    (ws_norm, ws_norm + "/%"),
                ).fetchone()[0]
            else:
                mem_cnt = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
                active_goals = conn.execute("SELECT iteration, max_iterations FROM goals WHERE status='active' ORDER BY id DESC").fetchall()
                undo_cnt = conn.execute("SELECT COUNT(*) FROM checkpoints").fetchone()[0]

            ralph_info = None
            for g in active_goals:
                if int(g["max_iterations"]) > 0:
                    ralph_info = f"{g['iteration']}/{g['max_iterations']}"
                    break
            return {
                "memories": int(mem_cnt),
                "active_goals": len(active_goals),
                "ralph": ralph_info,
                "checkpoints": int(undo_cnt),
            }
    except Exception:
        return {"memories": 0, "active_goals": 0, "ralph": None, "checkpoints": 0}
