---
name: brief
description: Write a requirements brief with testable acceptance criteria and a relay block. Creates blueprints/<kind>/<slug>/brief.md and moves .prism/active.
---

# Brief

## Arguments

Feature description. Prefix with "defect:" to file it under blueprints/defects/ instead of blueprints/features/.

## Output

blueprints/features/<slug>/brief.md  (or blueprints/defects/<slug>/brief.md).

## Goal

Produce a brief complete enough that any agent — Claude, Codex, Gemini, or a sub-agent — can
open the file, read nothing else, and proceed straight to `shape`.

## Steps

1. Read the arguments:
   - Starts with `defect:` → kind = `defect`; strip the prefix and continue.
   - Otherwise → kind = `feature`.
2. Derive a slug from the description: 2–4 words, kebab-case.
3. Choose the blueprint directory:
   - Feature: `blueprints/features/<slug>/`
   - Defect:  `blueprints/defects/<slug>/`
4. Create the directory if it does not exist.
5. Load the shared header with `.buildcli/runtime/bcx header` — Metadata, Stack, Architecture. It contains no
   band, by construction.
6. Work out:
   - **Actors** — who triggers this, who is affected
   - **Journeys** — the primary path, the alternatives, the failures
   - **Edge cases** — boundaries, concurrency, empty states, partial failures
   - **Acceptance criteria** — Given / When / Then, each one independently testable
7. Close the brief with:
   - **Assumptions** — numbered and explicit
   - **Open questions** — at most 3, each marked `NEEDS CLARIFICATION`
   - **Out of scope** — what this brief deliberately leaves alone
   - **Relay block** — agent assignments plus a readiness signal
8. Save `brief.md` inside the blueprint directory.
9. Point the runtime at it: `bcx active blueprints/features/<slug>` — it validates the directory and writes the pointer.
10. Return: brief path, confirmation that `.buildcli/active` moved, readiness for `shape`.

## The active pointer

`.buildcli/active` is rewritten every time `brief` runs. Downstream commands — `shape`, `worklist`,
`build`, `audit` — read it automatically when called with no arguments, so paths never need to be
passed by hand.

To work on something else: pass a path explicitly, or run `focus` to move the pointer.

## Output format (brief.md)

```markdown
# Brief: <Feature or Defect Name>
<!-- kind: feature | defect -->
<!-- slug: <slug> -->
<!-- created: <YYYY-MM-DD> -->

## Summary
One paragraph. What this is and why it matters.

## Actors
- Actor: role and permissions

## Journeys

### Primary flow
1. Step

### Alternative flows
- Condition → outcome

### Failure flows
- Condition → outcome

## Acceptance Criteria
- Given <context> When <action> Then <outcome>

## Edge Cases
- Case: expected behavior

## Out of Scope
- Item

## Assumptions
1. Assumption

## Open Questions (NEEDS CLARIFICATION)
1. Question

---
## Relay
- Brief owner: <agent>
- Shape agent: <recommended agent>
- Build agent: <recommended agent>
- Brief confidence: high | medium | low
- Blocking questions: <list or "none">
- Ready for shape: yes | no — <reason if no>
```

## Rules

- Features live in `blueprints/features/`, defects in `blueprints/defects/`. Never mix the two.
- Always move `.buildcli/active`. That pointer is the contract with every downstream command.
- Requirements only. No code, no schema decisions, no framework picks — those belong to `shape`.
- An acceptance criterion that cannot be tested on its own is not finished. Rewrite it.
- Never assume silently. An unstated assumption becomes someone else's bug.
- An incomplete relay block stalls the next agent. Fill in every line.
