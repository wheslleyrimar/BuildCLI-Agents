---
description: Convert a shape into atomic, dependency-ordered execution units, each tagged with the band that owns it.
arguments: (optional) Path to a blueprint directory. Omitted → reads .buildcli/active.
output: blueprints/features/<slug>/worklist.md  (or blueprints/defects/<slug>/worklist.md)
---

## User Input

```text
$ARGUMENTS
```

## Resolving the blueprint

1. Arguments given → treat them as the blueprint directory.
2. No arguments → read `.buildcli/active`.
3. `.buildcli/active` missing → stop, ask the user to run `/brief` first.
4. Read `shape.md` from the resolved directory. Missing → stop, ask the user to run `/shape` first.

## Steps

1. Resolve the blueprint directory as above.
2. Read `shape.md` and break every phase milestone into atomic units of work.
3. Tag each unit with:
   - **Band** — one of `service`, `interface`, `store`, `verify`, `delivery`
   - **Blocked by** — the unit IDs that must land first (empty means it can start now)
   - **Check** — the concrete observation that proves the unit is done
   - **Parallel** — yes or no: can it run beside units from other bands?
4. Save `worklist.md` next to `brief.md` and `shape.md`.
5. Return: the critical path, the units grouped by band, and the batches that can run in parallel.

## Output format (worklist.md)

```markdown
# Worklist: <Feature or Defect Name>
<!-- brief: <path> -->
<!-- shape: <path> -->
<!-- created: <YYYY-MM-DD> -->

## Critical path
W01 → W03 → W05 → W07

## Units

### W01 — <unit name>
- Band: service
- Blocked by: —
- Parallel: yes
- Check: <concrete observation>

### W02 — <unit name>
- Band: store
- Blocked by: —
- Parallel: yes
- Check: <concrete observation>

### W03 — <unit name>
- Band: service
- Blocked by: W01, W02
- Parallel: no
- Check: <concrete observation>
```

## Rules

- Resolve from `.buildcli/active` when no arguments are given.
- One band per unit. Work that straddles two bands is two units, not one.
- A check that cannot be verified independently is not a check. Rewrite it.
- Unblocked units in different bands are the parallel sub-agent candidates for `/build`.
