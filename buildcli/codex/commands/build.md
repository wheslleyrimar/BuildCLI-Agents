---
description: Execute units from the worklist, one band at a time.
arguments: (optional) Blueprint directory path, band filter, or unit ID. Omitted → reads .buildcli/active.
output: Code changes per unit
---

## User Input

```text
$ARGUMENTS
```

## Steps

1. Resolve the blueprint: arguments if given, otherwise `.buildcli/active`. Missing → stop and ask for `/brief`.
   - Read `worklist.md`. Missing → stop and ask for `/worklist`.
2. Read `shape.md` for the constraints and quality gates.
3. Group units by band. Then, in dependency order, for each unit:
   a. Load `.codex/skills/<band>/SKILL.md`.
   b. Read only the `[band:<band>]` block from `.buildcli/context.md`.
   c. Write the minimum change that satisfies the unit's check.
   d. Run lint and tests where the project provides them.
   e. Log anything that ripples into another band — do not fix it here.
4. Mark each unit `done` or `blocked` in `worklist.md` as you go.
5. Return per-unit: files changed, validation status, flags.

## Rules

- Resolve from `.buildcli/active` when no arguments are given.
- Load one band. Never the whole context file.
- One band per step — service and interface never share a unit.
- A blocked unit gets a reason and a move on, not a workaround.
