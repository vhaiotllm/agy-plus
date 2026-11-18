---
name: hookify
description: Create, list, or toggle declarative regex hook rules (.agents/hookify.*.md or ~/.gemini/config/hookify/*.md) to block or warn on unwanted shell commands, file patterns, prompts, or premature stops without editing hooks.json.
---

# Hookify — Declarative Guardrail Rules (`/hookify`)

Hookify lets you turn recurring mistakes or project safety rules into live `PreToolUse` / `PreInvocation` / `Stop` guardrails using simple Markdown files.

## Rule File Locations
- **Workspace-scoped**: `<workspace>/.agents/hookify.<rule-name>.md`
- **Global (machine-wide)**: `~/.gemini/config/hookify/<rule-name>.md`

## Rule File Format

```markdown
---
name: block-prod-env-overwrite
enabled: true
event: file
action: block
pattern: \.env\.production
---

Refusing to overwrite `.env.production` automatically. Edit `.env.example` instead or ask the user explicitly.
```

### Supported Frontmatter Fields
- `name`: Unique kebab-case identifier.
- `enabled`: `true` or `false`.
- `event`:
  - `bash`: Matched against `run_command` `CommandLine`.
  - `file`: Matched against `<Path>\n<NewContent>` on `edit_file` / `write_file`.
  - `prompt`: Matched against user input on `PreInvocation`.
  - `stop`: Matched on `Stop` before ending the turn.
- `action`: `warn` (queues a non-blocking advisory for next turn) or `block` (hard denies execution immediately).
- `pattern`: Python regular expression (multiline).

## Workflow
- If the user asks to prevent a mistake from this conversation without naming a pattern, invoke the `conversation-analyzer` subagent or inspect recent steps to extract an exact, low-false-positive regex rule, write the `.md` file, and confirm it is active immediately.
