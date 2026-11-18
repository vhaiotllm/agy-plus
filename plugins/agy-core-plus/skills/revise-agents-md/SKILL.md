---
name: revise-agents-md
description: Capture session learnings, build/test commands, architectural gotchas, and coding conventions into AGENTS.md / GEMINI.md and persistent memory. Ported and upgraded from Claude's revise-claude-md.
---

# Revise AGENTS.md & Project Rules (`/revise-agents-md`)

Reflect on the current session and persist reusable project knowledge into the right tier so future sessions never repeat discovery work:

1. **Gather Signal**:
   - Bash/test/build/typecheck commands discovered via trial-and-error.
   - Non-obvious code conventions, architectural invariants, or environment quirks.
   - User corrections or workflow preferences.

2. **Route Each Learning to the Right Destination**:
   - **Team/Repo Rules (`<workspace>/AGENTS.md` and `<workspace>/GEMINI.md`)**: Concise, imperative project standards (`<24 KB` cap). Keep `AGENTS.md` and `GEMINI.md` synchronized if both exist in the repo.
   - **Personal/Cross-Session Memory (`memory_save` MCP tool)**: Operational notes, server ports, debugging lessons, or machine-local setup details.

3. **Surgical Edits**:
   - Read existing `AGENTS.md` / `GEMINI.md` first, avoid duplicating existing rules, show a brief summary of additions, and apply targeted edits.
