---
name: interface
description: Analyze, review, and specify components, pages, client state, routing, styling, and the layer that talks to the API. Reads only [band:interface] from .buildcli/context.md.
---

# Skill: interface

## Metadata

- Agent: Gemini
- Version: 0.1.0
- Band: `[band:interface]` in `.buildcli/context.md`

## Purpose

Reason about the client side — components, pages, client state, routing, styling, and the layer that talks to the API — and surface the gaps, risks, and ambiguities before code is written.
Reads a single band so the context cost stays flat as the project grows.

## When to use

- Building or changing a component or page
- Managing client-side state or routing
- Connecting the UI to a backend endpoint
- Applying the design system or styling conventions
- Fixing an accessibility or internationalization defect

## Context loading (minimal)

Read only:

1. The `[band:interface]` block, via the runtime:
   ```bash
   .buildcli/runtime/bcx band interface
   ```
   Do not open `.buildcli/context.md` directly — with the harness enforced, that read is blocked
2. The specific component(s) or page(s) named by the task

Do not open service logic, migrations, or the delivery band unless the task explicitly reaches into them.

## Inputs

- A task description, or the file path(s) in scope
- Optional: the active blueprint's `worklist.md` entry for the current unit

## Workflow

1. Run `.buildcli/runtime/bcx band interface` to load the band. Nothing else from the context file.
2. Locate the component, page, or state slice the task points at.
3. Open only the source files that matter to it.
4. Make the smallest change that satisfies the task and matches the conventions already in the band.
5. Check the API contract against what the server actually exposes. A mismatch is a flag, not a fix — the server is another band.
6. Name the risks and the assumptions the change forces.
7. Report back: findings, recommended approach, and open questions.

## Output

- Analysis or review notes
- The list of files examined
- Risks and open questions
- Flags for downstream impact: API contract, state shape, tests

## Constraints

- Do not touch service or migration files in this task. Flag them instead.
- Follow the component and styling conventions recorded in `[band:interface]`.
- One component concern per task. Never fold a broad refactor into a feature change.
