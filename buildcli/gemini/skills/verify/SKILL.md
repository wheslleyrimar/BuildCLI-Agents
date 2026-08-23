---
name: verify
description: Analyze, review, and specify unit tests, integration tests, E2E scenarios, and the coverage gaps between them. Reads only [band:verify] from .buildcli/context.md.
---

# Skill: verify

## Metadata

- Agent: Gemini
- Version: 0.1.0
- Band: `[band:verify]` in `.buildcli/context.md`

## Purpose

Reason about the test layer — unit tests, integration tests, E2E scenarios, and the coverage gaps between them — and surface the gaps, risks, and ambiguities before code is written.
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
   buildcli band verify
   ```
   Do not open `.buildcli/context.md` directly — with the harness enforced, that read is blocked
2. The source file(s) under test, and the existing tests for them

Do not open unrelated services, components, or delivery config unless the task explicitly reaches into them.

## Inputs

- A task description, or the file path(s) in scope
- Optional: the active blueprint's `worklist.md` entry for the current unit

## Workflow

1. Run `buildcli band verify` to load the band. Nothing else from the context file.
2. Locate the unit under test and the tests that already cover it.
3. Open only the source files that matter to it.
4. Make the smallest change that satisfies the task and matches the conventions already in the band.
5. Confirm isolation — no shared mutable state, no network calls outside an integration test.
6. Name the risks and the assumptions the change forces.
7. Report back: findings, recommended approach, and open questions.

## Output

- Analysis or review notes
- The list of files examined
- Risks and open questions
- Flags for downstream impact: uncovered paths, design problems that block testing

## Constraints

- A unit test never makes a real network or database call.
- Follow the framework and naming conventions recorded in `[band:verify]`.
- Never reshape source code just to make it easier to test. Flag the design problem instead.
