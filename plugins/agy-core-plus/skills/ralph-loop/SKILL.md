---
name: ralph-loop
description: Start an autonomous self-referential completion loop (ported from Claude ralph-loop + Codex persistent goals) backed by AGY's Stop hook. Iterates automatically until tests/verification pass and the completion promise is emitted.
---

# Ralph Autonomous Completion Loop (`/ralph-loop`)

Keeps Antigravity iterating across turns via the `Stop` lifecycle hook until the objective is 100% verified complete or `max_iterations` is reached.

## How to Activate

1. Identify:
   - **`objective`**: Clear, concrete target outcome.
   - **`verify_cmd`**: Deterministic verification command when applicable (e.g. `npm test && npx tsc --noEmit`).
   - **`max_iterations`**: Default `8` (cap at `30`).
   - **`completion_promise`**: Default `DONE`.

2. Start the loop using the `ralph_loop_start` MCP tool (or `agy-plus ralph start ...`).

3. Execute the task iteratively:
   - Inspect, implement, and run verification commands.
   - Do **NOT** emit `<promise>DONE</promise>` until every requirement and verification check genuinely passes.
   - Once 100% complete and verified, include `<promise>DONE</promise>` in your final summary so the `Stop` hook marks the goal `complete` and exits cleanly.
