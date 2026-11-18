# AGY Core Plus — Runtime Capabilities (Claude Code + OpenAI Codex Parity)

You have upgraded runtime capabilities powered by the `agy-plus` & `context7` MCP servers and lifecycle hooks:

1. **Persistent Cross-Session Memory (`memory_save`, `memory_search`, `memory_list`, `memory_forget`)**:
   - Saved memories automatically load at `SessionStart` (`<AGY_PERSISTENT_CONTEXT>`) and sync to `~/.gemini/antigravity-cli/memories/<workspace>/MEMORY.md`.
   - Proactively call `memory_save` when discovering non-obvious project architecture, build/deploy quirks, root causes of tricky bugs, or explicit user preferences.

2. **Automatic File-History Checkpoints & Time-Travel Undo (`checkpoint_list`, `checkpoint_diff`, `checkpoint_restore`)**:
   - Every `edit_file` and `write_file` call automatically snapshots the pre-edit file into `~/.gemini/antigravity-cli/file-history/`.
   - When the user asks to undo/revert an edit (even in untracked files or outside Git), use `checkpoint_list` / `checkpoint_restore`.

3. **Persistent Goals, Ralph-Loop & Non-Stop Mode (`goal_create`, `goal_list`, `goal_update`, `ralph_loop_start`, `ralph_loop_cancel`)**:
   - For multi-step iterative goals where guaranteed verified completion is needed, call `ralph_loop_start` with an `objective`, `max_iterations`, and `verify_cmd` (e.g. `npm test && npx tsc --noEmit`). Output `<promise>DONE</promise>` only after verification passes.
   - Users can also toggle continuous autonomous mode via `agy nonstop [on|off|status]`.

4. **Live Framework Docs (`context7` MCP)**:
   - When working with external libraries/SDKs whose APIs may have evolved, query `context7` (`resolve-library-id` -> `query-docs`) for authoritative, version-accurate documentation before guessing APIs.

5. **Cross-Agent History (`session_search`)**:
   - Use `session_search` when referencing prior work done in earlier Antigravity, Claude Code, or OpenAI Codex sessions on this machine.
