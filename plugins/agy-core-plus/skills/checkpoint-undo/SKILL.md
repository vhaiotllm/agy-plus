---
name: checkpoint-undo
description: Inspect pre-edit file-history checkpoints, view unified diffs, and roll back file modifications to any prior snapshot (even outside Git). Use when the user asks to undo, revert a recent edit, inspect file history, or run /checkpoint-undo.
---

# File-History Checkpoints & Time-Travel Undo

Every `edit_file` and `write_file` action automatically captures a compressed SHA-256 pre-edit snapshot in `~/.gemini/antigravity-cli/file-history/`.

## Workflow

1. **List Recent Checkpoints**:
   - Call `checkpoint_list` (with `workspace` or `file_path`), or run `agy-plus undo list`.

2. **Preview Diff Before Restoring**:
   - Call `checkpoint_diff` with `checkpoint_id` (or `agy-plus undo diff <id>`) to verify the exact lines being reverted.

3. **Restore Snapshot**:
   - Call `checkpoint_restore` (`checkpoint_id` or `file_path`), or run `agy-plus undo restore <id>`.
   - Restoring automatically captures a backup checkpoint of the current file first, so even an undo is 100% reversible.
