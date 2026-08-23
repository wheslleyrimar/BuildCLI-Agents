---
description: Break the plan into atomic units with dependencies and band tags.
arguments: Optional blueprint directory path
output: blueprints/<kind>/<slug>/worklist.md
usage: Paste this prompt into Copilot Chat
---

## Prompt

Convert the active plan into an execution worklist.

Steps:
1. Read `.buildcli/active` to find the blueprint directory. Read `shape.md`.
2. Turn every phase milestone into atomic units. Tag each with:
   - Band: service | interface | store | verify | delivery
   - Blocked by: unit IDs that must land first (empty = ready now)
   - Parallel: yes | no
   - Check: the concrete observation that proves it done
3. Save `worklist.md` beside `brief.md` and `shape.md`.
4. Return the critical path and the units grouped by band.

Rules:
- One band per unit. Cross-band work splits into separate units.
- A check that cannot be verified independently is not a check.
