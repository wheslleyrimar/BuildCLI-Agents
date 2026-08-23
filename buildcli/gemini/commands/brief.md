---
description: Build a requirements brief optimized for analysis — surfaces hidden requirements, ambiguities, and risk before anything is planned.
arguments: Feature description. Prefix with "defect:" to file it under blueprints/defects/.
output: blueprints/features/<slug>/brief.md  (or blueprints/defects/<slug>/brief.md)
agent_role: brief-writer (Gemini preferred — requirements analysis)
---

## User Input

```text
$ARGUMENTS
```

## Steps

1. Read the kind: `defect:` prefix → `blueprints/defects/`; otherwise `blueprints/features/`.
2. Build a kebab-case slug and create the directory.
3. Read only the header blocks of `.buildcli/context.md` — Metadata, Stack, Architecture. Skip the bands.
4. Analyze the request first: actors, the value at stake, the constraints nobody stated. Then derive journeys (primary, alternative, failure) and edge cases.
5. Write acceptance criteria in Given / When / Then form. Each one must be testable on its own.
6. Add numbered assumptions, at most three open questions marked `NEEDS CLARIFICATION`, and an out-of-scope list.
7. Close with the relay block:
   ```
   ## Relay
   - Brief owner: Gemini
   - Shape agent: Claude (recommended)
   - Build agent: Claude or Codex
   - Brief confidence: <level>
   - Blocking questions: <list or "none">
   - Ready for shape: yes | no
   ```
8. Save `brief.md` and write the blueprint directory path to `.buildcli/active` — one line, no trailing slash.
9. Return the path, the confidence level, and anything still unresolved.

## Rules

- Always move `.buildcli/active`. Downstream commands read it with no arguments.
- Requirements only — no architecture, no implementation decisions.
- Features and defects never share a directory.
- Every open question must ship with a suggested resolution path.
