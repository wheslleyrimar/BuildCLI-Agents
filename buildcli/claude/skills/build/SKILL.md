---
name: build
description: Execute a worklist band by band with live progress tracking and optional sub-agent fan-out.
---

# Build

## Arguments

(optional) Path to a blueprint directory. Omitted → reads .buildcli/active.

## Output

Code changes + a build report.

## Resolving the blueprint

1. Arguments given → treat them as the blueprint directory.
2. No arguments → read `.buildcli/active`.
3. `.buildcli/active` missing → stop, ask the user to run `brief` first.
4. Read `worklist.md` from the resolved directory. Missing → stop, ask the user to run `worklist` first.
5. Read `shape.md` for the quality gates and architectural constraints.

## Steps

1. Resolve the blueprint directory as above.
2. Read `worklist.md` and group the units by band: `service`, `interface`, `store`, `verify`, `delivery`.
3. Register every unit in TodoWrite as `pending` before touching a single file.
4. Derive the execution order from the dependency graph:
   - Unblocked units in different bands → candidates to run in parallel sub-agents.
   - Units with declared blockers → strict dependency order.
5. For each unit, or each band batch:
   a. Flip the unit to `in_progress` in TodoWrite.
   b. Load `.claude/skills/<band>/SKILL.md`.
   c. Read only the `[band:<band>]` block from `.buildcli/context.md`.
   d. Write the smallest change that satisfies the unit's check.
   e. Flip the unit to `done` the moment it lands — not later.
   f. Anything that ripples into another band becomes a logged follow-up, never an in-place fix.
6. When every unit is resolved, emit the report.

## Sub-agent fan-out

When units in different bands share no dependencies:

- Spawn one sub-agent per band group.
- Hand each sub-agent exactly four things:
  - the unit list for its band
  - the path to its band skill, `.claude/skills/<band>/SKILL.md`
  - the matching `[band:<band>]` block from `.buildcli/context.md`
  - `brief.md` from the resolved directory, for reference
- Merge the sub-agent results before reporting.

## Output

```
## Build Report — <feature>

### Landed
- [band] W01: what it does → files changed

### Blocked
- W05: reason

### Cross-band follow-ups
- [service → interface] what needs attention

### Quality gates
- Gate name: Pass | Fail
```

## Rules

- Resolve from `.buildcli/active` when no arguments are given.
- Never read `context.md` whole. One band, the one you are working in.
- Never resolve a cross-band ripple inside the unit that found it. Flag it.
- Update TodoWrite in real time. A batch update at the end tells the user nothing while it matters.
- One concern per unit — no feature, fix, and refactor bundled into a single step.
