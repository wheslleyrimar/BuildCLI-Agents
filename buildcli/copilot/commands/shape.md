---
description: Produce a phased technical plan from the active brief.
arguments: Optional blueprint directory path
output: blueprints/<kind>/<slug>/shape.md
usage: Paste this prompt into Copilot Chat
---

## Prompt

Turn the active brief into a technical plan.

Steps:
1. Read `.buildcli/active` to find the blueprint directory (or use the path I give you).
2. Read `brief.md`. If the relay block says `Ready for shape: no`, list the blockers and stop.
3. Decide the approach and note the data model impact.
4. Break the work into phases. Each gets scope, deliverables, a quality gate, and a complexity rating (S/M/L).
5. Record risks with mitigations, plus every assumption the brief forced.
6. Save `shape.md` next to `brief.md`.

Rules:
- Read only inside the resolved blueprint directory.
- Never invent architecture the project context does not support.
- Keep each phase small enough to become five or fewer units in the worklist.
