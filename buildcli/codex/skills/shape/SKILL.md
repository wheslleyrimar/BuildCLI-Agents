---
name: shape
description: Turn an approved brief into a phased technical plan with milestones, risks, and quality gates.
---

# Shape

## Arguments

(optional) Blueprint directory path. Omitted → reads .buildcli/active.

## Output

blueprints/<kind>/<slug>/shape.md.
## Steps

1. Resolve the blueprint: arguments if given, otherwise `.buildcli/active`. Missing → stop and ask for `$brief`.
2. Read `brief.md`. If the relay block says `Ready for shape: no`, surface the blockers first.
3. Decide the approach and note the data model impact.
4. Break the work into phases. Each phase gets a scope, deliverables, a quality gate, and a complexity rating (S/M/L).
5. Record risks with mitigations, and every assumption the brief forced.
6. Save `shape.md` next to `brief.md`.
7. Return the path, the phase summary, and the open risks.

## Rules

- Read only inside the resolved blueprint directory.
- Never invent architecture the project context does not support.
- Keep each phase small enough to map to five or fewer units in `$worklist`.
