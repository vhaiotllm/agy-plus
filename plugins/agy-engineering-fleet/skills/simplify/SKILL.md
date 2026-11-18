---
name: simplify
description: Refine and simplify recently modified code using the code-simplifier specialist while strictly preserving behavior and passing all tests.
---

# Simplify Modified Code (`/simplify`)

1. Inspect `git status` and `git diff --name-only HEAD` to identify recently modified files.
2. Delegate to `code-simplifier` (or apply directly for small diffs) to remove redundant nesting, dead code, duplicated helpers, and overly clever constructs without altering external behavior.
3. Run the repository's typecheck and test suite (`npx tsc --noEmit`, `npm test`, etc.) to confirm zero behavioral regressions.
