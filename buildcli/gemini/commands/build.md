---
description: Review build readiness unit by unit, then execute or hand off to a code-generation agent.
arguments: (optional) Blueprint directory path, band filter, or unit ID. Omitted → reads .buildcli/active.
output: Readiness assessment + code changes for the units taken on
---

## User Input

```text
$ARGUMENTS
```

## Steps

1. Resolve the blueprint: arguments if given, otherwise `.buildcli/active`. Missing → stop and ask for `/brief`.
   - Read `worklist.md`. Missing → stop and ask for `/worklist`.
2. Read `shape.md` for the constraints and quality gates.
3. Before writing anything, assess readiness per unit:
   - Is the check concrete enough to prove the unit done?
   - Are the declared blockers real, and is anything blocking that was not declared?
   - Does the owning band carry enough context to act, or is it full of `NEEDS CLARIFICATION`?
4. Report units that are not ready and why. Do not implement past a genuine blocker.
5. For each ready unit, in dependency order:
   a. Load `.gemini/skills/<band>/SKILL.md`.
   b. Read only the `[band:<band>]` block from `.buildcli/context.md`.
   c. Write the minimum change that satisfies the unit's check, or hand the unit to Claude or Codex with the band and check attached.
   d. Log anything that ripples into another band — do not fix it here.
6. Mark each unit `done`, `blocked`, or `handed off` in `worklist.md`.
7. Return: readiness summary, units completed, units handed off, cross-band flags.

## Rules

- Resolve from `.buildcli/active` when no arguments are given.
- Load one band. Never the whole context file.
- One band per step.
- Readiness assessment comes before implementation, not after it fails.
