---
name: build
description: Execute a worklist band by band, scheduled by the runtime, with live progress and sub-agent fan-out.
---

# Build

## Arguments

(optional) Path to a blueprint directory. Omitted → the runtime reads the active pointer.

## Output

Code changes + a build report.
## Resolving the blueprint

The runtime resolves it. Do not read the pointer file yourself.

```bash
.buildcli/runtime/bcx active          # the active blueprint, or an error telling you to run /brief
.buildcli/runtime/bcx graph           # units, critical path, and any structural problem
```

`.buildcli/runtime/bcx graph` exits non-zero when the worklist is not schedulable — a dependency cycle, an
unknown band tag, a unit with no check. Fix those before building anything; a cycle means the
plan is wrong, not the code.

## Steps

1. Run `.buildcli/runtime/bcx graph`. Non-zero exit → report the problems and stop.
2. Register every unit in TodoWrite as `pending` before touching a file.
3. Ask the runtime what can start:
   ```bash
   .buildcli/runtime/bcx next --json
   ```
   It returns the ready units grouped by band — unblocked, dependencies satisfied. That grouping
   is the fan-out plan; you do not compute the order yourself.
4. For each unit:
   ```bash
   .buildcli/runtime/bcx claim W03            # marks it in progress; the write gate now scopes to its band
   .buildcli/runtime/bcx band service         # load exactly the band that unit belongs to
   ```
   a. Flip the unit to `in_progress` in TodoWrite.
   b. Load `.claude/skills/<band>/SKILL.md`.
   c. Write the smallest change that satisfies the unit's check.
   d. Close it out:
      ```bash
      .buildcli/runtime/bcx done W03                            # or:
      .buildcli/runtime/bcx block W03 --reason "<what stopped it>"
      ```
   e. Anything that ripples into another band becomes a follow-up unit, never an in-place fix.
      With the harness enforced, the write gate will block you from touching another band's
      files while this unit is claimed. That block is the design working, not an obstacle.
5. Repeat from step 3 until `.buildcli/runtime/bcx next` reports nothing ready.
6. Run the suite and record the result:
   ```bash
   .buildcli/runtime/bcx verify
   ```
7. Emit the report.

## Sub-agent fan-out

`.buildcli/runtime/bcx next --json` returns more than one band → those groups are independent and can run
concurrently. Spawn one sub-agent per band and hand each:

- its unit list, from the runtime's output
- **its own identity**, and the instruction to pass `--agent <id>` on every runtime command
- the path to its band skill, `.claude/skills/<band>/SKILL.md`
- the instruction to load context with `.buildcli/runtime/bcx band <band>` and nothing else
- `brief.md`, for reference

Enforcement survives the fan-out **only if each worker is distinguishable**. The gate resolves the
caller's own claim and holds it to that band, so named workers each stay inside their own. Give every
worker a distinct `--agent`, and export a matching `BCX_AGENT_ID` in its environment — the gate runs
as a hook subprocess and reads the environment, since a hook event carries no agent field.

Where the host cannot give each worker its own environment, they all look like one caller, the band
is ambiguous again, and the gate allows everything. That is not a new failure — it is how the gate
behaved before identities existed — but it is invisible unless you look. `.buildcli/runtime/bcx doctor`
names it: two live claims sharing one owner is reported precisely because enforcement does not error
in that state, it silently stops. Check it once at the start of a fan-out.

Bands ready in parallel are not the same as files that do not collide. Two bands can own edits to the
same file; `.buildcli/bands.json` is what makes the separation real, and a project without one gets no
path enforcement at all. Fan out on disjoint files, not just disjoint bands.

Merge the sub-agent results before reporting.

## Output

```
## Build Report — <feature>

### Landed
- [band] W01: what it does → files changed

### Blocked
- W05: reason

### Cross-band follow-ups
- [service → interface] what needs attention

### Verification
- command: npm test
- result: PASS (exit 0)

### Quality gates
- Gate name: Pass | Fail
```

## Rules

- Let the runtime schedule. Never hand-derive the dependency order from the markdown.
- Never read `.buildcli/context.md`. One band, through `.buildcli/runtime/bcx band`.
- Never resolve a cross-band ripple inside the unit that found it.
- Update TodoWrite and the runtime together — a unit marked done in one and not the other is a lie.
- One concern per unit — no feature, fix, and refactor bundled into a single step.
