---
name: audit
description: Check the implementation against the brief's acceptance criteria. Green/amber/red per criterion. Reads .prism/active automatically.
---

# Audit

## Arguments

(optional) Path to a blueprint directory. Omitted → reads .buildcli/active.

## Output

Audit report — green / amber / red per criterion, saved as audit.md.

## Goal

Close the loop between what was asked for and what was written. Every acceptance criterion in
`brief.md` gets a verdict backed by a file and a line — using the same narrow-context discipline
as the rest of the pipeline.

## Steps

1. Resolve the blueprint directory: arguments if given, otherwise `.buildcli/active`.
   - `.buildcli/active` missing → stop, ask the user to run `brief` first.
2. Read `brief.md` and extract the complete **Acceptance Criteria** list.
3. Read the band tags in `worklist.md` to learn which bands this work touched.
4. For each of those bands — and only those — load it with `.buildcli/runtime/bcx band <name>`.
5. Collect the changed files:
   - `git diff --name-only HEAD` for uncommitted work.
   - Or, if `brief.md` carries a `<!-- created: YYYY-MM-DD -->` header, `git log --since` to find the relevant commits.
6. Read only the changed files that fall inside the blueprint's bands.
7. Rule on each criterion:
   - Find the behavior in the changed code.
   - Look for a test that exercises it.
   - Assign ✅ green (implemented and tested), ⚠️ amber (implemented, untested), ❌ red (not found).
8. Run the suite and compare the quality gates from `shape.md` against the real result:
   ```bash
   .buildcli/runtime/bcx verify --json
   ```
   Report what it returns. A gate asserted without a run is not a gate.
9. Write the report to `blueprints/<kind>/<slug>/audit.md`.
10. Return the report inline plus the saved path.

## Output format (audit.md)

```markdown
# Audit: <Feature Name>
<!-- brief: <path> -->
<!-- audited: <YYYY-MM-DD> -->
<!-- verdict: green | amber | red -->

## Verdict: <overall>

## Acceptance Criteria

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| 1 | Given X When Y Then Z | ✅ green | src/api/checkout.ts:42, checkout.test.ts:18 |
| 2 | Given X When Y Then Z | ⚠️ amber | implemented in checkout.ts, no test found |
| 3 | Given X When Y Then Z | ❌ red   | not present in the changed files |

## Quality Gates

| Gate | Status | Detail |
|------|--------|--------|
| All tests pass | ✅ | 48/48 |
| Coverage ≥ 80% | ⚠️ | 74% — 6 points short |

## Gaps

- Criterion 3: what is missing, and where it belongs
- Coverage: which paths are untouched

## Next steps

- [ ] specific action that moves this to green
```

## Rules

- Never load `context.md` whole. Only the bands this blueprint actually touched.
- Judge each criterion by reading the code and its tests; use `.buildcli/runtime/bcx verify` for the gate
  results, not to decide whether an individual criterion is satisfied.
- Amber is not failure. It means the behavior works and the test is missing.
- If the git history is ambiguous, ask which files to audit rather than guessing.
- Always save `audit.md`. An all-green record is still worth keeping.
