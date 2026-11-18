---
name: cancel-ralph
description: Cancel or pause any active Ralph autonomous completion loop for the current conversation or workspace.
---

# Cancel Ralph Loop (`/cancel-ralph`)

Immediately stop active `Stop`-hook Ralph loops so the session returns to standard single-turn completion:

1. Call the `ralph_loop_cancel` MCP tool (or run `agy-plus ralph cancel`).
2. Confirm to the user how many active loops were paused.
