---
name: commit-push-pr
description: Create a feature branch (if on main/master), commit changes, push to origin, and open a GitHub Pull Request with gh pr create.
---

# Commit, Push & Open PR (`/commit-push-pr`)

1. Inspect `git status`, `git diff HEAD`, and `git branch --show-current`.
2. If currently on `main` or `master`, create and switch to a descriptive `feat/...` or `fix/...` branch.
3. Stage relevant files and commit with a clear message.
4. Push upstream (`git push -u origin HEAD`) and create a PR via `gh pr create --fill` (or explicit `--title` and structured `--body` summary + test plan), returning the PR URL.
