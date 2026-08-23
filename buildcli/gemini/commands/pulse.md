---
description: Read-only pipeline snapshot — active blueprint, stage, unit counts, next step.
arguments: none
output: Inline report. No files written.
---

## Steps

1. Run `buildcli active`. Missing → report "No active blueprint. Run `/brief` to start." and stop.
2. Load whichever of `brief.md`, `shape.md`, `worklist.md`, `audit.md` exist in that directory.
3. Infer the stage: brief → shape → worklist → build → audit.
4. Count unit states from `worklist.md`.
5. If `.buildcli/journal/session.log` exists, show the last 5 entries.
6. Render: blueprint, kind, stage, pipeline line, unit counts by band, quality gates, last audit verdict, next step.

## Rules

- Read-only. Write nothing.
- A missing file means the stage has not started — not an error.
- Always close with a concrete next step.
