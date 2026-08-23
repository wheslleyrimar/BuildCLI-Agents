---
description: Execute units from the worklist, one band at a time.
arguments: Optional band filter (service|interface|store|verify|delivery) or unit ID
output: Code changes + updated unit statuses in worklist.md
usage: Paste this prompt into Copilot Chat. In Agent Mode the matching band skill activates automatically.
---

## Prompt

Execute the next pending unit or units from the active worklist.

Steps:
1. Read `.buildcli/active` to find the blueprint directory.
2. Run `.buildcli/runtime/bcx next` — it returns the units that are ready, grouped by band. Pick one.
3. Load the band skill for that unit from `.github/skills/<band>/SKILL.md`.
4. Load the band with `.buildcli/runtime/bcx band <band>` — never the whole context file.
5. Implement the unit following the skill's workflow.
6. Mark the unit `done` in `worklist.md`.
7. Run the suite: `.buildcli/runtime/bcx verify`.
8. Return: unit completed, files changed, the verify result, and flags for downstream units.

Rules:
- One band at a time — never mix service and interface in the same step.
- Load only the skill and the band matching the current unit.
- A blocked unit gets marked `blocked` with a reason; move to the next one.
