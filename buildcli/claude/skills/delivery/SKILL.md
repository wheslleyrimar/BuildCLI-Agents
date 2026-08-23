---
name: delivery
description: Ship-side work — CI/CD pipelines, deploy scripts, infrastructure, environments, and monitoring. Reads only [band:delivery] from .buildcli/context.md.
---

# Skill: delivery

## Metadata

- Agent: Claude
- Version: 0.1.0
- Band: `[band:delivery]` in `.buildcli/context.md`

## Purpose

Own how the code gets out: CI/CD pipelines, deployment configuration, environment management,
and the monitoring that tells you it worked. Reads a single band to keep the context cost flat.

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

Do not open application source, interface components, or migrations unless the task explicitly requires them.

## Inputs

- A task description, or the config file path(s) to change
- Optional: the target environment (dev / staging / prod)

## Workflow

1. Run `buildcli band delivery` to load the band. Nothing else from the context file.
2. Locate the pipeline step, deploy target, or config the task points at.
3. Open only the relevant config or infrastructure files.
4. Make a minimal, targeted change that follows the delivery conventions already in place.
5. Verify no secret is hardcoded and every environment is scoped correctly.
6. Report back: what changed, which environments it affects, and how to roll back.

## Output

- The config, pipeline, or infrastructure change
- The list of files touched
- Rollback instructions
- Flags for environment-specific side effects

## Constraints

- Never commit a secret or a credential. Reference the secrets manager recorded in `[band:delivery]`.
- A change to a production pipeline needs explicit confirmation before it is applied.
- Follow the environment naming and promotion model recorded in `[band:delivery]`.
