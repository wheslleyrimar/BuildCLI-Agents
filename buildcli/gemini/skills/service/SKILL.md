---
name: service
description: Analyze, review, and specify endpoints, business logic, services, auth, and outbound integrations. Reads only [band:service] from .buildcli/context.md.
---

# Skill: service

## Metadata

- Agent: Gemini
- Version: 0.1.0
- Band: `[band:service]` in `.buildcli/context.md`

## Purpose

Reason about the server side — endpoints, business logic, services, auth, and outbound integrations — and surface the gaps, risks, and ambiguities before code is written.
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
   bcx band service
   ```
   Do not open `.buildcli/context.md` directly — with the harness enforced, that read is blocked
2. The specific file(s) the task names

Do not open the interface, store, or delivery bands unless the task explicitly reaches into them.

## Inputs

- A task description, or the file path(s) in scope
- Optional: the active blueprint's `worklist.md` entry for the current unit

## Workflow

1. Run `bcx band service` to load the band. Nothing else from the context file.
2. Locate the module, service, or endpoint the task points at.
3. Open only the source files that matter to it.
4. Make the smallest change that satisfies the task and matches the conventions already in the band.
5. Confirm error handling, input validation, and auth guards are present — not assumed.
6. Name the risks and the assumptions the change forces.
7. Report back: findings, recommended approach, and open questions.

## Output

- Analysis or review notes
- The list of files examined
- Risks and open questions
- Flags for downstream impact: store layer, interface contract, tests

## Constraints

- Do not touch interface or migration files in this task. Flag them instead.
- Follow the auth strategy recorded in `[band:service]`.
- Keep the diff reviewable: one concern per task.
