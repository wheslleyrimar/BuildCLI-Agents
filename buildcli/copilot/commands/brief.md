---
description: Define feature or defect requirements with testable acceptance criteria.
arguments: Feature description. Prefix with "defect:" to file under blueprints/defects/.
output: blueprints/<kind>/<slug>/brief.md + updated .buildcli/active
usage: Paste this prompt into Copilot Chat
---

## Prompt

Write a requirements brief for the feature or defect I describe.

Steps:
1. `defect:` prefix → `blueprints/defects/`; otherwise `blueprints/features/`.
2. Build a kebab-case slug and create the directory.
3. Read only the header blocks of `.buildcli/context.md` — Metadata, Stack, Architecture. Skip the bands.
4. Derive actors, journeys (primary, alternative, failure), and edge cases.
5. Write acceptance criteria as Given / When / Then. Each must be testable on its own.
6. Add numbered assumptions, at most three `NEEDS CLARIFICATION` questions, and an out-of-scope list.
7. Close with a relay block: brief owner, shape agent, build agent, confidence, blocking questions, ready-for-shape.
8. Save `brief.md` and write the blueprint directory path to `.buildcli/active` — one line, no trailing slash.

Rules:
- Always update `.buildcli/active`. Every downstream prompt reads it.
- Requirements only — no architecture, no implementation choices.
- Features and defects never share a directory.
