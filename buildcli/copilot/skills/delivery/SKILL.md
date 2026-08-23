---
name: delivery
description: Implement CI/CD pipelines, deployment configuration, environment management, and monitoring following project conventions. Model-agnostic — works with any model powering Copilot. Reads only [band:delivery] from .buildcli/context.md.
---

# Skill: delivery

## Metadata

- Agent: Copilot (model-agnostic)
- Version: 0.1.0
- Band: `[band:delivery]` in `.buildcli/context.md`

## Purpose

Produce working, testable ship side code: CI/CD pipelines, deployment configuration, environment management, and monitoring.
Reads a single band so the context cost stays flat as the project grows.

## When to use

- Changing a CI/CD pipeline step
- Managing environment variables and secret references
- Reviewing or updating a deployment script
- Setting up or tuning monitoring and alerting
- Writing down a rollback or incident procedure

## Context loading (minimal)

Read only:

1. The `[band:delivery]` block, via the runtime:
   ```bash
   buildcli band delivery
   ```
   Do not open `.buildcli/context.md` directly — with the harness enforced, that read is blocked
2. The specific pipeline, infrastructure, or config file(s) named by the task

Do not open application source, interface components, or migrations unless the task explicitly reaches into them.

## Inputs

- A task description, or the file path(s) in scope
- Optional: the active blueprint's `worklist.md` entry for the current unit

## Workflow

1. Run `buildcli band delivery` to load the band. Nothing else from the context file.
2. Locate the pipeline step, deploy target, or config the task points at.
3. Open only the source files that matter to it.
4. Make the smallest change that satisfies the task and matches the conventions already in the band.
5. Verify no secret is hardcoded and every environment is scoped correctly.
6. Run lint and the unit tests when the project provides them.
7. Report back: files changed, behavioral impact, and downstream flags.

## Output

- The code change
- The list of files touched
- Lint and test results
- Flags for downstream impact: affected environments, rollback path

## Constraints

- Never commit a secret or a credential. Reference the secrets manager recorded in `[band:delivery]`.
- A change to a production pipeline needs explicit confirmation before it is applied.
- Follow the environment naming and promotion model recorded in `[band:delivery]`.
