---
name: cross-session-search
description: Search past prompts, conversation summaries, and full transcripts across Antigravity (agy), Claude Code, and OpenAI Codex on this machine.
---

# Cross-Agent Session Search (`/cross-session-search`)

When the user refers to prior work ("như lần trước", "what we did earlier in Claude/Codex/AGY", "find the session where we configured X"):

1. Call the `session_search` MCP tool with relevant keywords (or run `agy-plus sessions search "<query>"`).
2. For deeper inspection of a matched Antigravity conversation ID, read `~/.gemini/antigravity-cli/brain/<conversation-id>/.system_generated/logs/transcript.jsonl` using targeted grep/line slices.
3. Summarize findings concisely and link Antigravity conversations as `[<label>](conversation://<conversation-id>)`.
