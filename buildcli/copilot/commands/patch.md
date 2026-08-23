---
description: Fix a defect using only the band that owns the broken code.
arguments: Defect description and/or file path(s). Add --trace to file a defect blueprint.
output: Code fix + root cause
usage: Paste this prompt into Copilot Chat
---

## Prompt

Fix the defect I describe, on the smallest context footprint that can do it.

Steps:
1. If I passed `--trace`, first create `blueprints/defects/<slug>/brief.md` (summary, root cause hypothesis, affected files, acceptance criterion) and write the path to `.buildcli/active`.
2. Identify the affected file(s).
3. Route to a band:
   - API / service / auth / middleware → `[band:service]`
   - component / page / client state → `[band:interface]`
   - migration / model / query → `[band:store]`
   - test file → `[band:verify]`
   - pipeline / infra / env config → `[band:delivery]`
4. Read only that band from `.buildcli/context.md`, then only the affected files.
5. State the root cause in one sentence before changing anything.
6. Apply the minimal fix and flag any cross-band follow-up.
7. With `--trace`: update the defect brief with the confirmed cause and the change.

Rules:
- One band. Never the whole context file.
- Do not refactor around the defect.
- Root cause unclear after reading the file → ask, do not guess in code.
