---
name: clean-gone
description: Clean up stale local git branches marked as [gone] on the remote, safely removing any associated git worktrees first.
---

# Clean Gone Branches (`/clean-gone`)

1. Run `git fetch --prune` followed by `git branch -vv` and `git worktree list`.
2. Identify local branches marked `: gone]`.
3. For any `[gone]` branch attached to a linked worktree (`+`), remove that worktree first (`git worktree remove <path>`), then delete the stale local branch (`git branch -D <branch>`) and report what was cleaned.
