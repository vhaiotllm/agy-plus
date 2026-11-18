---
name: code-review
description: Fast, high-confidence (score >=80) defect-first review of uncommitted git changes, a branch comparison, or a pull request.
---

# Fast Defect-First Code Review (`/code-review`)

1. Gather context (`git diff HEAD` or `git diff <base>...HEAD`, plus `AGENTS.md` / `GEMINI.md`).
2. Evaluate every candidate defect on a `0–100` confidence scale:
   - Discard stylistic preferences, hypothetical nitpicks, and untouched legacy lines (`<80`).
   - Report only concrete bugs, security flaws, broken edge cases, race conditions, silent failures, and explicit project-rule violations (`>=80`).
3. Present each finding concisely with severity, `file:line` link, trigger condition, and minimal fix.
