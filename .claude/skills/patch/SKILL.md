---
name: patch
description: Fix a defect on the smallest context footprint — one band, the affected files. Add --trace to file a defect blueprint.
---

# Patch

## Arguments

Defect description and/or file path(s). Add --trace to file a defect blueprint alongside the fix.

## Output

Code fix + root cause. With --trace: also blueprints/defects/<slug>/brief.md and a moved .buildcli/active.

## Goal

Diagnose and repair with the least context that can do the job. Load the one band that owns the
broken code. Nothing beyond it.

## Steps

1. Read the arguments:
   - `--trace` present → file a defect blueprint before fixing (see Trace mode).
   - Otherwise → fix directly, no blueprint artifacts.
2. Read the description and pin down the affected file(s).
3. Route to a band by file path or symptom:
   - API, service, auth, middleware → `[band:service]`
   - component, page, client state, routing → `[band:interface]`
   - migration, model, query, schema → `[band:store]`
   - test file → `[band:verify]`
   - pipeline, infra, environment config → `[band:delivery]`
4. Load **only** that band: `.buildcli/runtime/bcx band <name>`. Never the whole file — with the
   harness enforced, that read is blocked.
5. Read the affected file(s), and no more of them than the defect requires.
6. Name the root cause. If you are not sure, state the hypothesis before changing anything.
7. Apply the minimal fix that resolves it without side effects.
8. Flag any risk or follow-up that lands in another band.

## Trace mode (--trace)

When `--trace` is passed:

1. Build a kebab-case slug from the description.
2. Create `blueprints/defects/<slug>/`.
3. Write a short `brief.md`: summary, root cause hypothesis, affected files, acceptance criterion (the defect no longer reproduces), owning band.
4. Run `bcx active blueprints/defects/<slug>`.
5. Fix as normal.
6. Once fixed, update `brief.md` with the confirmed root cause and what changed.

Reach for `--trace` when:

- The defect spans several files or resisted a first diagnosis.
- You want it tracked next to features for the release notes.
- The root cause is surprising and worth writing down.

## Output

- The fixed file(s)
- Root cause: one sentence
- Fix summary: what changed and why
- Cross-band flags, if the fix ripples
- With `--trace`: the path to `blueprints/defects/<slug>/brief.md`

## Rules

- Never read `context.md` whole. One band.
- Do not tidy the surrounding code unless the untidiness is the defect.
- Root cause still unclear after reading the file? Ask. Do not guess in code.
- A fix that spans bands is not one fix. Flag it and split it.
- `--trace` is opt-in. A one-line typo fix does not need a blueprint.
