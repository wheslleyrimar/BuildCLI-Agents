---
name: requirement-split
description: Break a broad or ambiguous product request into prioritized functional and non-functional requirements with IDs.
---

# Requirement Split

## When to use

The request is too broad, too vague, or too tangled to implement directly — and forcing it into a
brief right now would bury the ambiguity instead of resolving it.

## Context loading (minimal)

Read only:

1. The shared header — Metadata, Stack, Architecture — via `.buildcli/runtime/bcx header`
2. Any existing `brief.md` in the active blueprint

## Workflow

1. Extract the goals and the constraints the request implies but does not state.
2. Split them into functional requirements (FR-nnn) and non-functional requirements (NFR-nnn).
3. Name every assumption, and every question that must be answered before work starts.
4. Order the result into a backlog: priority, dependencies, and what unblocks what.

## Output

- A structured requirements list with stable IDs
- A priority and dependency map
- Open questions, each paired with a suggested way to resolve it

## Constraints

- Requirements only. No architecture, no implementation choices.
- Every requirement must be independently verifiable — otherwise it is a goal, not a requirement.
- An open question without a suggested resolution path is not finished.
