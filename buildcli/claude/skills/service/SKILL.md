---
name: service
description: Server-side work — endpoints, business logic, services, auth, and outbound integrations. Reads only [band:service] from .buildcli/context.md.
---

# Skill: service

## Metadata

- Agent: Claude
- Version: 0.1.0
- Band: `[band:service]` in `.buildcli/context.md`

## Purpose

Own the server side: endpoints, business logic, services, auth, and the calls this system makes
outward. Reads a single band so the context cost stays flat as the project grows.

## When to use

- Adding or changing an API endpoint
- Writing or reorganizing business logic and service modules
- Wiring up a third-party API
- Reviewing or repairing an auth or authorization path
- Adding middleware, input validation, or error handling

## Context loading (minimal)

Read only:

1. The `[band:service]` block, via the runtime:
   ```bash
   .buildcli/runtime/bcx band service
   ```
   Do not open `.buildcli/context.md` directly — with the harness enforced, that read is blocked
2. The specific file(s) the task names

Do not open the interface, store, or delivery bands unless the task explicitly reaches into them.

## Inputs

- A task description, or the file path(s) to change
- Optional: the related `brief.md` from the active blueprint

## Workflow

1. Run `.buildcli/runtime/bcx band service` to load the band. Nothing else from the context file.
2. Locate the module, service, or endpoint the task points at.
3. Open only the source files that matter to it.
4. Make the smallest change that satisfies the task and matches the conventions already in the band.
5. Confirm error handling, input validation, and auth guards are present — not assumed.
6. Report back: what changed, why, and what still needs attention.

## Output

- The code change, with a short explanation
- The list of files touched
- Flags for downstream impact: store layer, interface contract, tests

## Constraints

- Do not touch interface or migration files in this task. Flag them instead.
- Follow the auth strategy recorded in `[band:service]`.
- Keep the diff reviewable: one concern per task.
