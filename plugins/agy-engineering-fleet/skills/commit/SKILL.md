---
name: commit
description: Stage and create a clean, Conventional Commit git commit matching the repository's commit history style. Use when the user asks to /commit.
---

# Smart Git Commit (`/commit`)

1. Run `git status`, `git diff HEAD`, `git branch --show-current`, and `git log --oneline -10` in a single non-interactive command.
2. Verify no `.env`, credentials, or unintended build artifacts are staged.
3. Stage intended files (`git add <paths>` or `git add -A` when all tracked/new files belong to the change) and create a concise commit message matching repo conventions.
