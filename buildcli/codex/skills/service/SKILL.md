---
name: service
description: Implement endpoints, business logic, services, auth, and outbound integrations with focused code generation and minimal context overhead. Reads only [band:service] from .buildcli/context.md.
---

# Skill: service

## Metadata

- Agent: Codex
- Version: 0.1.0
- Band: `[band:service]` in `.buildcli/context.md`

## Purpose

Produce working, testable server side code: endpoints, business logic, services, auth, and outbound integrations.
Reads a single band so the context cost stays flat as the project grows.

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
   buildcli band service
   ```
   Do not open `.buildcli/context.md` directly — with the harness enforced, that read is blocked
2. The specific file(s) the task names

Do not open the interface, store, or delivery bands unless the task explicitly reaches into them.

## Inputs

- A task description, or the file path(s) in scope
- Optional: the active blueprint's `worklist.md` entry for the current unit

## Workflow

1. Run `buildcli band service` to load the band. Nothing else from the context file.
2. Locate the module, service, or endpoint the task points at.
3. Open only the source files that matter to it.
4. Make the smallest change that satisfies the task and matches the conventions already in the band.
5. Confirm error handling, input validation, and auth guards are present — not assumed.
6. Run lint and the unit tests when the project provides them.
7. Report back: files changed, behavioral impact, and downstream flags.

## Output

- The code change
- The list of files touched
- Lint and test results
- Flags for downstream impact: store layer, interface contract, tests

## Constraints

- Do not touch interface or migration files in this task. Flag them instead.
- Follow the auth strategy recorded in `[band:service]`.
- Keep the diff reviewable: one concern per task.
