---
name: compact
description: Compact and summarize conversation context, discarding verbose historical logs and keeping only essential project state and active goals.
---

# Context Compaction

When the user types `/compact` or asks to compact context:
1. Summarize key technical decisions, modified files, and active goals concisely.
2. Discard obsolete debugging logs and verbose tool responses from active focus.
3. Present a clean, high-density status summary and await the user's next directive.
