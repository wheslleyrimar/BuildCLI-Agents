---
description: Check the implementation against the brief's acceptance criteria, one verdict per criterion.
arguments: (optional) Blueprint directory path. Omitted → reads .buildcli/active.
output: blueprints/<kind>/<slug>/audit.md
---

## User Input

```text
$ARGUMENTS
```

## Steps

1. Resolve the blueprint: arguments if given, otherwise `.buildcli/active`.
2. Read `brief.md` and extract every acceptance criterion.
3. Read the band tags in `worklist.md` to learn which bands the work touched. Load only those bands.
4. Collect changed files with `git diff --name-only HEAD`, or `git log --since` against the brief's created date.
5. For each criterion, find the behavior in the changed code and the test that exercises it. Rule:
   - ✅ green — implemented and tested
   - ⚠️ amber — implemented, no test found
   - ❌ red — not present
6. Compare the quality gates from `shape.md` against real test output where available.
7. Write `audit.md` in the blueprint directory and return it inline.

## Rules

- Only the bands the work touched. Never the whole context file.
- Do not run the suite here — read the tests and judge coverage of each criterion.
- Amber means the code works and the test is missing. It is a gap, not a failure.
- Always save `audit.md`, even when everything is green.
