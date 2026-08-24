---
name: survey
description: Survey the repository and write the shared project context, split into independently loadable domain bands.
---

# Survey

## Arguments

Optional band focus (service, interface, store, verify, delivery). Omit to write all bands.

## Output

.buildcli/context.md.
## Steps

1. Detect languages, frameworks, runtimes, and package managers from the repository files.
2. Identify what this system connects to: databases, queues, third-party APIs, auth providers, cloud services.
3. Infer the architecture and the module boundaries from the code and config, not from the README alone.
4. Write `.buildcli/context.md` with the header blocks (Metadata, Stack, Architecture, Engineering Standards, Agent Instructions) plus the five bands: `[band:service]`, `[band:interface]`, `[band:store]`, `[band:verify]`, `[band:delivery]`.
5. No evidence for a band → `N/A — not detected`. Thin evidence → `NEEDS CLARIFICATION`.
6. Return findings, per-band confidence, and every open question.

## Refreshing

`survey` owns this file and rewrites it from repository evidence. To see what is already recorded
without reading it whole, use `.buildcli/runtime/bcx bands`, `.buildcli/runtime/bcx band <name>`, and `.buildcli/runtime/bcx header`.

## Rules

- Facts from files beat inference.
- Each band stays self-contained and under roughly 300 words — a skill loads one band and nothing else.
- No fact repeated across bands. Cross-reference the owner.
- Re-run when the stack changes.
