---
description: <what this command does>
arguments: <expected arguments>
output: <artifact or response>
---

## User Input

```text
$ARGUMENTS
```

## Goal

State the single outcome this command must produce.

## Steps

1. Validate input and resolve context.
2. Read only the files required.
3. Produce the output artifact.
4. Return a concise completion summary.

## Rules

- Keep outputs deterministic.
- Fail fast when a required input is missing.
- Never widen scope beyond the stated goal.
