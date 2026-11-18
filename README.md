# AGY Plus — Claude Code & OpenAI Codex Supercharged Edition for Antigravity (`agy`)

**AGY Plus** upgrades Google Antigravity CLI (`agy`) with the flagship runtime, subagents, workflows, safety guardrails, and developer ergonomics of **Claude Code** and **OpenAI Codex**.

---

## Quick Install (Linux & macOS)

> Prerequisite: [Antigravity CLI (`agy`)](https://antigravity.google/docs/cli/reference) and `python3` (3.9+).

```bash
git clone https://github.com/vhaiotllm/agy-plus.git
cd agy-plus
chmod +x install.sh
./install.sh
source ~/.bashrc
agy doctor
```

---

## Key Upgrades Over Stock `agy`

| Capability | Inspired By | How It Works in AGY Plus |
| :--- | :--- | :--- |
| **Persistent Auto-Memory** | Claude `MEMORY.md` + Codex `memories_1.sqlite` | SQLite FTS5 full-text memory synced two-way with `~/.gemini/antigravity-cli/memories/<workspace>/MEMORY.md` & `GLOBAL_MEMORY.md`, auto-injected on `SessionStart`. |
| **File-History Checkpoints & Undo** | Claude `file-history` + `/undo` | `PreToolUse` hook snapshots every file (compressed SHA-256 blobs) before `edit_file`/`write_file` — inspect diffs and time-travel restore even outside Git (`agy undo`). |
| **Ralph-Loop & Non-Stop Mode** | Claude `ralph-loop` + Codex `goals_1.sqlite` | `Stop` hook keeps `agy` iterating autonomously until `verify_cmd` (e.g. `npm test && npx tsc --noEmit`) passes and `<promise>DONE</promise>` is emitted (`agy ralph`, `agy nonstop`). |
| **Security Guidance & Hookify** | Claude `security-guidance` + `hookify` | Hard-blocks catastrophic shell commands (`rm -rf /`, `mkfs`, `dd of=/dev/...`, fork bombs), warns on OWASP sinks, and loads declarative `.agents/hookify.*.md` regex rules. |
| **13 Specialist Agents** | Claude Official Marketplace + Codex `pragmatic` | 2 Main Personas (`codex-pragmatic`, `claude-architect`) + 11 Subagents (`code-architect`, `code-explorer`, `code-simplifier`, `pr-code-reviewer`, `silent-failure-hunter`, `type-design-analyzer`, `pr-test-analyzer`, `security-auditor`, `legacy-modernizer`, `repo-scout`, `conversation-analyzer`). |
| **Live Docs & Native State MCPs** | Claude `context7` + Native MCP | Registers `agy-plus` (13 native stdio MCP tools) and `context7` (`https://mcp.context7.com/mcp`) for live library documentation. |
| **Cross-Agent Session Search** | Unified Transcripts | Search past prompts & transcripts across **AGY + Claude Code + OpenAI Codex** (`agy sessions search "<query>"` / `session_search` MCP tool). |
| **Power CLI & Rich Statusline HUD** | `codex review` / `codex exec` + Claude Powerline | Adds `agy review`, `agy exec`, `agy undo`, `agy memory`, `agy goals`, `agy ralph`, `agy nonstop`, `agy stats`, `agy doctor` + live Git branch/dirty/Ctx/Quota/Memory/Undo statusline. |
| **95+ Curated Skills** | Claude Code & OpenAI Codex Skills | Pre-adapted for AGY (`feature-dev`, `review-pr`, `simplify`, `modernize`, `commit-push-pr`, `playwright`, `ui-ux-pro-max`, `impeccable`, `hallmark`, `shadcn-ui`, `vercel-react-best-practices`, `pdf/docx/xlsx/pptx`, cloud deploys, etc.). |

---

## CLI Cheat Sheet

```bash
agy memory list                                        # List global & workspace memories
agy memory add --title "Build" "Run npm test first"    # Save workspace memory
agy memory add --global --title "Style" "Be concise"   # Save global memory
agy undo list                                          # List pre-edit file snapshots
agy undo diff 12                                       # View unified diff of checkpoint #12
agy undo restore latest                                # Roll back latest file edit
agy ralph start "Fix all failing tests" --max 8 --verify "npm test"
agy nonstop status                                     # Check continuous mode status
agy review                                             # Defect-first code review (uncommitted diff)
agy review main                                        # Defect-first code review vs main
agy exec "Run tests and summarize failures"            # Non-interactive single-shot execution
agy sessions search "auth"                             # Search AGY + Claude + Codex sessions
agy stats                                              # Session, step, and tool telemetry
agy doctor                                             # Validate plugins, MCPs, DB, and CLI tools
```

## TUI Slash Workflows

Inside interactive `agy`:
- `/feature-dev` — Guided discovery -> `code-explorer` -> `code-architect` -> implementation -> `pr-code-reviewer`
- `/review-pr` — Parallel multi-agent PR review (`pr-code-reviewer`, `silent-failure-hunter`, `security-auditor`, `type-design-analyzer`, `pr-test-analyzer`)
- `/simplify` — Clean & refine modified files via `code-simplifier` without changing behavior
- `/modernize` — Incremental legacy code modernization
- `/commit`, `/commit-push-pr`, `/clean-gone` — Fast Git & GitHub PR workflows
- `/memory`, `/checkpoint-undo`, `/ralph-loop`, `/cancel-ralph`, `/hookify`, `/revise-agents-md`, `/cross-session-search`

---

## Repository Structure

- `runtime/agy_plus/` — SQLite FTS5 engine (`engine.py`), lifecycle hook runner (`hooks_runner.py`), stdio MCP server (`mcp_server.py`), and CLI (`cli.py`)
- `plugins/agy-core-plus/` — Core hooks, runtime rules, and state management skills
- `plugins/agy-engineering-fleet/` — 13 specialist agents and 8 software engineering slash skills
- `skills/` — 95 curated, AGY-adapted cross-domain skills
- `statusline/` — ANSI HUD statusline (`statusline.py`, `statusline.sh`)
- `install.sh` / `uninstall.sh` — Non-destructive installer and uninstaller
