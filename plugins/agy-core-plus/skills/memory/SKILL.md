---
name: memory
description: Manage persistent cross-session memories (save, search, list, consolidate, or delete project and global facts synced to SQLite FTS5 and MEMORY.md). Use when the user asks to remember something across sessions, inspect saved memories, or run /memory.
---

# Persistent Memory Management (`/memory`)

Antigravity Plus maintains a persistent SQLite FTS5 memory store (`~/.gemini/antigravity-cli/agy_plus/agy_plus.db`) bi-directionally synced with human-readable Markdown files:
- Global: `~/.gemini/antigravity-cli/memories/GLOBAL_MEMORY.md`
- Workspace: `~/.gemini/antigravity-cli/memories/<workspace-slug>/MEMORY.md`

## Workflow

1. **Save or Update a Memory**:
   - Prefer the `memory_save` MCP tool (`content`, `title`, `scope`: `"workspace"` or `"global"`, `tags`), or CLI `agy-plus memory add [--global] [--title "Topic"] "Fact..."`.
   - Keep entries concise, factual, and high-signal (build/test commands, architectural invariants, root causes, deployment paths, user preferences). Never store raw secret tokens.

2. **Search or List Memories**:
   - Call `memory_search` or `memory_list` (or `agy-plus memory list`).

3. **Consolidate / Prune**:
   - Deduplicate overlapping entries by updating the existing `title` or removing obsolete IDs via `memory_forget` (`agy-plus memory rm <id>`).
