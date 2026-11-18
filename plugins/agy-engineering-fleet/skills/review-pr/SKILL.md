---
name: review-pr
description: Comprehensive multi-agent code & PR review launching pr-code-reviewer, silent-failure-hunter, type-design-analyzer, pr-test-analyzer, and security-auditor in parallel.
---

# Parallel Multi-Agent PR Review (`/review-pr`)

Orchestrate a rigorous, high-signal review of local uncommitted diffs, branch diffs, or a GitHub PR:

1. **Determine Scope**: Run `git status` and `git diff --stat` (or `gh pr diff <PR>` if a PR number/URL is given).
2. **Parallel Subagent Fan-Out**: Launch the relevant specialist subagents in parallel via `invoke_subagent`:
   - `pr-code-reviewer` (always — logic bugs & `AGENTS.md` compliance, confidence `>=80`)
   - `silent-failure-hunter` (when error handling, async IO, or fallbacks changed)
   - `security-auditor` (when auth, routes, DB queries, shell calls, or workflows changed)
   - `type-design-analyzer` (when schemas, interfaces, or models changed)
   - `pr-test-analyzer` (to spot high-impact untested edge cases)
3. **Aggregate & Deduplicate**: Synthesize findings into **Critical Blockers**, **Important Fixes**, and **Recommended Improvements** with clickable `file:///...#L...` links.
