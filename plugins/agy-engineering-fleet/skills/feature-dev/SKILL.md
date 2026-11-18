---
name: feature-dev
description: Guided 6-stage feature engineering workflow orchestrating code-explorer, code-architect, implementation, code-simplifier, and pr-code-reviewer subagents.
---

# End-to-End Feature Development (`/feature-dev`)

Execute complex features systematically using Antigravity's specialist subagents:

1. **Codebase Exploration**: Invoke `code-explorer` subagent(s) (`invoke_subagent`) to trace relevant entry points, data flow, and existing abstractions.
2. **Clarify Ambiguities**: If critical product/API decisions remain underspecified, ask once via `ask_question`; otherwise proceed directly.
3. **Architecture Blueprint**: Invoke `code-architect` to produce a decisive file-by-file design and build sequence.
4. **Surgical Implementation**: Implement the blueprint cleanly following `AGENTS.md` / `GEMINI.md`.
5. **Simplify & Verify**: Run project tests/typechecks (`npm test`, `npx tsc --noEmit`, etc.) and optionally invoke `code-simplifier` on modified files.
6. **Defect Review**: Invoke `pr-code-reviewer` on `git diff HEAD` and resolve any high-confidence (`>=80`) findings before finishing.
