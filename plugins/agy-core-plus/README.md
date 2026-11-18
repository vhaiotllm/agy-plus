# AGY Core Plus

Brings flagship runtime features from Claude Code and OpenAI Codex into Antigravity (`agy`):
- **Persistent Auto-Memory**: SQLite FTS5 + `MEMORY.md` sync injected on `SessionStart`.
- **File-History Checkpoints**: Pre-edit snapshots & time-travel rollback (`agy undo`).
- **Ralph-Loop & Persistent Goals**: Self-continuing `Stop`-hook verification loops (`agy ralph`, `agy goals`).
- **Security Guidance & Hookify**: Catastrophic command guard, OWASP sink advisories, and declarative `.agents/hookify.*.md` rules.
- **Cross-Agent Session Search**: Search history across AGY, Claude Code, and Codex (`agy sessions`).
