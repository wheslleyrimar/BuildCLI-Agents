---
name: survey
description: Survey the repository and write .buildcli/context.md, split into independently loadable domain bands.
---

# Survey

## Arguments

Optional band focus (service, interface, store, verify, delivery). Omit to write all bands.

## Output

.buildcli/context.md — with every [band:<name>] block populated.

## Goal

Produce an evidence-based project context whose domain bands can each be read on their own.
A band is only useful if a skill can load it in isolation and still act correctly — so each
band must be self-contained, and none may depend on having read the others.

## Steps

1. Walk the repository surface: directory layout, package manifests, config files, CI definitions, README.
2. Gather evidence per band:
   - **service**: language, runtime, framework, entry points, business logic modules, auth, outbound APIs, error handling, logging.
   - **interface**: framework, state management, routing, component library, API client layer, styling, build tooling.
   - **store**: databases, ORM or query layer, migration files, core entities, caching, validation.
   - **verify**: test frameworks, test file patterns, coverage configuration, CI pass/fail gates.
   - **delivery**: cloud provider, CI/CD platform, deploy scripts, environment names, secret references, monitoring.
3. Fill the shared header blocks: Metadata, Stack, Architecture, Engineering Standards, Agent Instructions.
4. Fill each `[band:<name>]` block with only the fields that belong to it.
   - No evidence for a band → write `N/A — not detected` on every field.
   - Evidence is thin or contradictory → mark the field `NEEDS CLARIFICATION`.
5. Write the result to `.buildcli/context.md`.
6. Record any project-specific constraint you discovered in `CLAUDE.md`.
7. Report back:
   - Confidence per band (high / medium / low)
   - Assumptions made
   - Every field left as `NEEDS CLARIFICATION`

## Band ownership

After this command runs, each skill reads exactly one band:

| Skill       | Reads              |
|-------------|--------------------|
| `service`   | `[band:service]`   |
| `interface` | `[band:interface]` |
| `store`     | `[band:store]`     |
| `verify`    | `[band:verify]`    |
| `delivery`  | `[band:delivery]`  |

## Rules

- Evidence beats inference — read the file before claiming the fact.
- Cap each band at roughly 300 words. A band that grows past that is doing another band's job.
- Never repeat a fact across bands. Cross-reference the owning band instead.
- State every assumption in the open.
- Re-run this command — for all bands or one — whenever the stack shifts.
