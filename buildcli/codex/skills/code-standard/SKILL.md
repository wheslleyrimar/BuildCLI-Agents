---
name: code-standard
description: Implementation workflow for Codex — predictable quality checks, validation evidence, and a short delivery note.
---

# Code Standard

## When to use

Any implementation task where the change needs to arrive with proof that it works, not just a claim.

## Context loading (minimal)

Read only:

1. The Engineering Standards block from `.buildcli/context.md`
2. The band that owns the code you are changing
3. The files in scope

## Workflow

1. Read the local conventions and the constraints that bind this change.
2. Write the minimal, testable change.
3. Run lint and the test suite.
4. Summarize the behavioral impact and attach the validation results.

## Output

- A change that matches the project's standards
- Validation evidence: lint result, test result, what was run
- A one-line note on behavioral impact

## Constraints

- No change ships without a validation attempt. If tests cannot run, say so and why.
- One concern per change. No feature bundled with a refactor.
- Never widen scope past the unit's stated check.
