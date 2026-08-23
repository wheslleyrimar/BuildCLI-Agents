---
description: Pipeline snapshot — active blueprint, stage, unit counts, next step.
arguments: none
output: Inline report. No files written.
usage: Paste this prompt into Copilot Chat
---

## Prompt

Show me where the current work stands.

Steps:
1. Run `bcx active`. Missing → say "No active blueprint. Run the brief prompt to start." and stop.
2. Load whichever of `brief.md`, `shape.md`, `worklist.md`, `audit.md` exist there.
3. Infer the stage: brief → shape → worklist → build → audit.
4. Count unit states from `worklist.md`, grouped by band.
5. Show: blueprint path, kind, stage, unit counts, quality gates, last audit verdict, next step.

Rules:
- Read-only. Write nothing.
- A missing file means the stage has not started — not an error.
- Always close with a concrete next step.
