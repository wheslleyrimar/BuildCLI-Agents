---
description: Fix a defect on the smallest context footprint — one band, the affected files.
arguments: Defect description and/or file path(s). Add --trace to file a defect blueprint.
output: Code fix + root cause. With --trace: blueprints/defects/<slug>/brief.md and a moved .buildcli/active.
---

## User Input

```text
$ARGUMENTS
```

## Steps

1. Check for `--trace`. If present, file the defect blueprint first (see Trace mode).
2. Identify the affected file(s) from the description.
3. Route to a band:
   - API / service / auth / middleware → `[band:service]`
   - component / page / client state → `[band:interface]`
   - migration / model / query → `[band:store]`
   - test file → `[band:verify]`
   - pipeline / infra / env config → `[band:delivery]`
4. Load only that band: `.buildcli/runtime/bcx band <name>`. Never the whole file.
5. Read the affected file(s) and no more.
6. State the root cause in one sentence before changing anything.
7. Apply the minimal fix. Run the relevant tests.
8. Flag any cross-band follow-up.

## Trace mode (--trace)

1. Slug the description, create `blueprints/defects/<slug>/`.
2. Write `brief.md`: summary, root cause hypothesis, affected files, acceptance criterion (does not reproduce), owning band.
3. Write the path to `.buildcli/active`.
4. Fix, then update `brief.md` with the confirmed cause and the change.

## Rules

- One band. Never the whole context file.
- Do not refactor around the defect.
- Root cause unclear after reading the file → ask, do not guess in code.
- `--trace` is opt-in; skip it for trivial fixes.
