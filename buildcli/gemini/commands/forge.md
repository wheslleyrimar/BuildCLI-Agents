---
description: Create or refresh a project-specific analysis or review skill from this repository's real patterns.
arguments: Skill name, optionally followed by a band (service|interface|store|verify|delivery|custom).
output: .gemini/skills/<name>/SKILL.md
---

## User Input

```text
$ARGUMENTS
```

## Steps

1. Parse the skill name and band. Band omitted → infer from the name, or ask.
2. Existing `.gemini/skills/<name>/SKILL.md` → read it and refresh what went stale. New → start from `_shared/templates/skill-template.md`.
3. Load the band: `.buildcli/runtime/bcx band <band>`.
4. Open two or three representative source files in that band and extract the patterns actually in use: naming, error handling, auth guards, test layout.
5. Write purpose, concrete triggers, the exact band to load, a workflow that names real paths, constraints, and one realistic example.
6. Save the file. Register it in `GEMINI.md` if it is not already listed.

## Rules

- Every line must be specific to this project. Delete anything that would survive a copy-paste elsewhere.
- Band empty or full of `NEEDS CLARIFICATION` → run `/survey` first and say so.
- Under roughly 400 words. One concern per skill.
