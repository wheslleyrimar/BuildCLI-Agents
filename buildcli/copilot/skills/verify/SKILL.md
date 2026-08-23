---
name: verify
description: Implement unit tests, integration tests, E2E scenarios, and the coverage gaps between them following project conventions. Model-agnostic — works with any model powering Copilot. Reads only [band:verify] from .buildcli/context.md.
---

# Skill: verify

## Metadata

- Agent: Copilot (model-agnostic)
- Version: 0.1.0
- Band: `[band:verify]` in `.buildcli/context.md`

## Purpose

Produce working, testable test layer code: unit tests, integration tests, E2E scenarios, and the coverage gaps between them.
Reads a single band so the context cost stays flat as the project grows.

## When to use

- Writing unit tests for new or changed functions
- Adding integration tests for an endpoint or service
- Building or extending an E2E scenario
- Reviewing coverage and naming what is missing
- Repairing a broken or flaky test

## Context loading (minimal)

Read only:

1. The `[band:verify]` block, via the runtime:
   ```bash
   .buildcli/runtime/bcx band verify
   ```
   Do not open `.buildcli/context.md` directly — with the harness enforced, that read is blocked
2. The source file(s) under test, and the existing tests for them

Do not open unrelated services, components, or delivery config unless the task explicitly reaches into them.

## Inputs

- A task description, or the file path(s) in scope
- Optional: the active blueprint's `worklist.md` entry for the current unit

## Workflow

1. Run `.buildcli/runtime/bcx band verify` to load the band. Nothing else from the context file.
2. Locate the unit under test and the tests that already cover it.
3. Open only the source files that matter to it.
4. Make the smallest change that satisfies the task and matches the conventions already in the band.
5. Confirm isolation — no shared mutable state, no network calls outside an integration test.
6. Run lint and the unit tests when the project provides them.
7. Report back: files changed, behavioral impact, and downstream flags.

## Output

- The code change
- The list of files touched
- Lint and test results
- Flags for downstream impact: uncovered paths, design problems that block testing

## Constraints

- A unit test never makes a real network or database call.
- Follow the framework and naming conventions recorded in `[band:verify]`.
- Never reshape source code just to make it easier to test. Flag the design problem instead.
