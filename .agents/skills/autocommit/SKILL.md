---
name: autocommit
description: >
  Stage all modified tracked files and commit with an auto-generated message.
  Use when user says "stage and commit", "auto-commit", "commit changes", or invokes /autocommit.
allowed-tools:
  - Bash
---

Generate a terse commit message, stage all modified files, and commit. One shot.

## Steps

1. Run `git diff` and `git status` to read changes
2. Generate commit message using rules below
3. Stage: `git add $(git diff --name-only)`
4. Commit: `git commit -m "<message>"`
5. Report the commit hash

## Commit message rules

**Subject:** `<type>(<scope>): <imperative summary>` — scope optional, ≤50 chars
Types: `feat`, `fix`, `refactor`, `perf`, `docs`, `test`, `chore`, `build`, `ci`, `style`, `revert`
Imperative mood: "add", "fix", "remove" — not "added/adds/adding"
No trailing period. No AI attribution. No emoji unless project uses them.

**Body:** only if "why" isn't obvious from the diff. Wrap at 72 chars.

**Never include:**
- "This commit does X", "I", "we", "now", "currently"
- "Generated with Claude Code" or any AI attribution
- Co-Authored-By lines

## CLAUDE.md overrides

Check CLAUDE.md for project-specific commit conventions and follow them exactly.
