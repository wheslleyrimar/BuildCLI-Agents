---
name: interface
description: Client-side work — components, pages, state, routing, and API wiring. Reads only [band:interface] from .buildcli/context.md.
---

# Skill: interface

## Metadata

- Agent: Claude
- Version: 0.1.0
- Band: `[band:interface]` in `.buildcli/context.md`

## Purpose

Own what the user sees and touches: components, views, client state, routing, styling, and the
layer that talks to the API. Reads a single band to keep the context cost flat.

## When to use

- Building or changing a component or page
- Managing client-side state or routing
- Connecting the UI to a backend endpoint
- Applying the design system or styling conventions
- Fixing an accessibility or internationalization defect

## Context loading (minimal)

Read only:

1. The `[band:interface]` block from `.buildcli/context.md`
2. The specific component(s) or page(s) named by the task

Do not open service logic, migrations, or the delivery band unless the task explicitly reaches into them.

## Inputs

- A task description, or the component/page path(s) to change
- Optional: the related `brief.md` from the active blueprint

## Workflow

1. Read `[band:interface]` from `.buildcli/context.md`.
2. Locate the component, page, or state slice the task points at.
3. Open only the source files that matter to it.
4. Make the smallest change that satisfies the task and matches the framework and design-system conventions.
5. Check the API contract against what the server actually exposes. A mismatch is a flag, not a fix — the server is another band.
6. Report back: what changed, why, and what still needs attention.

## Output

- The code change, with a short explanation
- The list of files touched
- Flags for downstream impact: API contract, state shape, tests

## Constraints

- Do not touch service or migration files in this task. Flag them instead.
- Follow the component and styling conventions recorded in `[band:interface]`.
- One component concern per task. Never fold a broad refactor into a feature change.
