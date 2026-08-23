---
description: Deep gap analysis between what the brief asked for and what the code does — behavioral drift, missing edge cases, untested criteria.
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
3. Read the band tags in `worklist.md` to learn which bands the work touched. Load each with `.buildcli/runtime/bcx band <name>` — only those.
4. Collect changed files with `git diff --name-only HEAD`, or `git log --since` against the brief's created date.
5. For each criterion, find the behavior in the changed code and the test that exercises it. Rule:
   - ✅ green — implemented and tested
   - ⚠️ amber — implemented, no test found
   - ❌ red — not present
6. Run the suite with `.buildcli/runtime/bcx verify --json` and compare the quality gates from `shape.md` against the real result. A gate asserted without a run is not a gate.
7. Beyond the criteria, name what the brief did not ask for but should have: edge cases the code silently handles, behavior that drifted from intent, criteria that are technically green but practically hollow.
8. Write `audit.md` in the blueprint directory and return it inline.

## Rules

- Only the bands the work touched, via `.buildcli/runtime/bcx band`. Never the whole context file.
- Judge each criterion by reading the code and its tests; use `.buildcli/runtime/bcx verify` for the gate results.
- Amber means the code works and the test is missing. It is a gap, not a failure.
- Always save `audit.md`, even when everything is green.
