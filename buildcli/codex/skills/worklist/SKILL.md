---
name: worklist
description: Break a shape into atomic, dependency-ordered units, each tagged with the band that owns it.
---

# Worklist

## Arguments

(optional) Blueprint directory path. Omitted → reads .buildcli/active.

## Output

blueprints/<kind>/<slug>/worklist.md.
## Steps

1. Resolve the blueprint: arguments if given, otherwise `.buildcli/active`. Missing → stop and ask for `$brief`.
2. Read `shape.md`. Missing → stop and ask for `$shape`.
3. Convert every phase milestone into atomic units. Tag each with:
   - **Band**: service | interface | store | verify | delivery
   - **Blocked by**: unit IDs that must land first (empty = ready now)
   - **Parallel**: yes | no
   - **Check**: the concrete observation that proves it is done
4. Save `worklist.md` beside `brief.md` and `shape.md`.
5. Return the critical path, the units grouped by band, and the parallel-safe batches.

## Rules

- One band per unit. Cross-band work splits into separate units.
- A check that cannot be verified on its own is not a check.
- Unblocked units in different bands are the parallel candidates for `$build`.
