---
name: shape
description: Turn an approved brief into a phased technical plan. Reads .buildcli/active automatically. Outputs blueprints/<kind>/<slug>/shape.md.
---

# Shape

## Arguments

(optional) Path to a blueprint directory or brief.md. Omitted → reads .buildcli/active.

## Output

blueprints/features/<slug>/shape.md  (or blueprints/defects/<slug>/shape.md).
## Resolving the blueprint

1. Arguments given → treat them as the blueprint directory (or the brief file inside it).
2. No arguments → run `.buildcli/runtime/bcx active` for the active blueprint directory.
3. `.buildcli/active` missing or empty → stop and ask the user to run `brief` first.
4. Read `brief.md` from the resolved directory.
5. Check the `## Relay` block for `Ready for shape: yes`. If it says no, surface the blocking questions before writing anything.

## Steps

1. Resolve the blueprint as above.
2. Pull the requirements and constraints out of `brief.md`.
3. Decide the architectural approach and note the data model consequences.
4. Break the work into phases, each with a milestone you can point at and say "done".
5. Record the risks, the assumptions, and a quality gate per phase.
6. Save `shape.md` alongside `brief.md`.
7. Return: file path, phase summary, open risks.

## Output format (shape.md)

```markdown
# Shape: <Feature or Defect Name>
<!-- brief: <path to brief.md> -->
<!-- created: <YYYY-MM-DD> -->

## Approach
Short description of the approach and the decisions that drove it.

## Data model impact
Entities added or changed: fields, relationships, constraints.

## Phases

### Phase 1 — <name>
- Scope:
- Deliverables:
- Quality gate:
- Complexity: S | M | L

### Phase 2 — <name>
...

## Risks
- Risk → mitigation

## Assumptions
1. Assumption

## Quality gates
- Gate: pass/fail criteria
```

## Rules

- Read only inside the resolved blueprint directory. Nothing speculative.
- Brief confidence `low` → say so at the top and flag every assumption it forced.
- Do not invent architecture the project context does not support.
- Keep phases small: one phase should map to no more than five entries in `worklist`.
