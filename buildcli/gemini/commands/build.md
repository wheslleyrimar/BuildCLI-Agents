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
3. Get the schedule and the structural picture from the runtime — never derive it by hand:
   ```bash
   .buildcli/runtime/bcx graph      # cycles, unknown bands, units with no check
   .buildcli/runtime/bcx next --json  # what is actually ready, grouped by band
   ```
4. Before writing anything, assess readiness per unit:
   - Is the check concrete enough to prove the unit done?
   - Are the declared blockers real, and is anything blocking that was not declared?
   - Does the owning band carry enough context to act, or is it full of `NEEDS CLARIFICATION`?
5. Report units that are not ready and why. Do not implement past a genuine blocker.
6. For each ready unit that the runtime listed:
   a. `.buildcli/runtime/bcx claim <id>` — marks it in progress.
   b. Load `.gemini/skills/<band>/SKILL.md`.
   c. Load the band with `.buildcli/runtime/bcx band <band>` — never the whole context file.
   c. Write the minimum change that satisfies the unit's check, or hand the unit to Claude or Codex with the band and check attached.
   d. Log anything that ripples into another band — do not fix it here.
7. Close each unit through the runtime: `.buildcli/runtime/bcx done <id>` or
   `.buildcli/runtime/bcx block <id> --reason "..."`.
8. Run the suite: `.buildcli/runtime/bcx verify`.
9. Return: readiness summary, units completed, units handed off, cross-band flags,
   and the verify result.

## Rules

- Resolve from `.buildcli/active` when no arguments are given.
- Load one band, via `.buildcli/runtime/bcx band`. Never the whole context file.
- One band per step.
- Readiness assessment comes before implementation, not after it fails.
- Let the runtime schedule. `graph` refusing to run means the plan is wrong, not the tooling.
