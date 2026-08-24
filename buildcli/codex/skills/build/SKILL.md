---
name: build
description: Execute units from the worklist, one band at a time.
---

# Build

## Arguments

(optional) Blueprint directory path, band filter, or unit ID. Omitted → reads .buildcli/active.

## Output

Code changes per unit.
## Steps

1. Resolve the blueprint: arguments if given, otherwise `.buildcli/active`. Missing → stop and ask for `$brief`.
   - Read `worklist.md`. Missing → stop and ask for `$worklist`.
2. Read `shape.md` for the constraints and quality gates.
3. Ask the runtime what can start — do not derive the order yourself:
   ```bash
   .buildcli/runtime/bcx next --json
   ```
   It returns the ready units grouped by band. For each one:
   a. `.buildcli/runtime/bcx claim <id>` — marks it in progress.
   b. Load `.codex/skills/<band>/SKILL.md`.
   c. Load the band with `.buildcli/runtime/bcx band <band>` — never the whole context file.
   c. Write the minimum change that satisfies the unit's check.
   d. Run lint and tests where the project provides them.
   e. Log anything that ripples into another band — do not fix it here.
4. Repeat from step 3 until `.buildcli/runtime/bcx next` reports nothing ready.
5. Run the suite: `.buildcli/runtime/bcx verify`.
6. Return per-unit: files changed, validation status, flags, plus the verify result.

## Rules

- Resolve from `.buildcli/active` when no arguments are given.
- Load one band, via `.buildcli/runtime/bcx band`. Never the whole context file.
- One band per step — service and interface never share a unit.
- A blocked unit gets a reason and a move on, not a workaround.
