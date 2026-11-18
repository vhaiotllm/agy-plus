---
name: modernize
description: Structured codebase modernization workflow (assess -> extract business rules -> characterization tests -> incremental uplift -> verify) ported from Claude code-modernization.
---

# Codebase Modernization (`/modernize`)

Execute safe, zero-regression upgrades and refactors on legacy or high-debt modules:

1. **Assess & Map**: Use `repo-scout` / `code-explorer` to inventory dependencies, coupling hotspots, and deprecated patterns.
2. **Extract Invariants**: Document non-obvious business rules and edge cases before modifying code.
3. **Characterization Tests**: Ensure automated tests cover existing behavior prior to structural edits.
4. **Incremental Uplift**: Delegate slices to `legacy-modernizer` or apply targeted edits one module at a time, verifying tests, types, and runtime health after each slice.
