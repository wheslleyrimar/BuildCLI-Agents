---
name: verify
description: Test work — unit, integration, and E2E coverage, plus CI gate checks. Reads only [band:verify] from .buildcli/context.md.
---

# Skill: verify

## Metadata

- Agent: Claude
- Version: 0.1.0
- Band: `[band:verify]` in `.buildcli/context.md`

## Purpose

Own the proof: unit tests, integration tests, E2E scenarios, and the coverage gaps between them.
Reads a single band plus the code under test.

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
   bcx band verify
   ```
   Do not open `.buildcli/context.md` directly — with the harness enforced, that read is blocked
2. The source file(s) under test
3. The existing test file(s) for that unit, if any

Do not open unrelated services, components, or delivery config unless the task explicitly requires them.

## Inputs

- The source file path(s) to cover
- Optional: the scenario or defect the test must pin down

## Workflow

1. Run `bcx band verify` to load the band. Nothing else from the context file.
2. Read the source file(s) to understand inputs, outputs, and where they break.
3. Read the existing tests so you extend them rather than duplicate them.
4. Write focused, deterministic tests: the happy path plus the edge cases that actually bite.
5. Confirm isolation — no shared mutable state, no network calls outside an integration test.
6. Report back: tests added, what they cover, and what is deliberately left uncovered.

## Output

- The test file(s), new or extended
- The list of files touched
- Coverage notes: what is proven, what is not

## Constraints

- A unit test never makes a real network or database call.
- Follow the framework and naming conventions recorded in `[band:verify]`.
- Never reshape source code just to make it easier to test. Flag the design problem instead.
