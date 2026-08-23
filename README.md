```
  ___      _ _    _  ___ _    ___
 | _ )_  _(_) |__| |/ __| |  |_ _|
 | _ \ || | | / _` | (__| |__ | |
 |___/\_,_|_|_\__,_|\___|____|___|
            A G E N T S
```

**A spec-driven agent harness you bootstrap into any project.**

BuildCLI Agents splits your project context into five independent **bands** and hands each task exactly one.
A backend change loads the service band. Nothing else. The pipeline on top of that — brief, shape,
worklist, build, audit — keeps the work in versioned files instead of chat scrollback, so Claude,
Codex, Gemini, and Copilot can hand off to each other without re-explaining anything.

---

## Requirements

`python3` on PATH — that is the whole list. The runtime uses the standard library only: no pip
install, no build step, no lockfile. Without python3 the markdown pipeline still works; the
runtime and its gates do not.

## Install

Run this from inside the project you want to set up:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/wheslleyrimar/buildcli-agents/main/install.sh)
```

With options:

```bash
# Claude only
bash <(curl -fsSL .../install.sh) --agent claude

# A specific target
bash <(curl -fsSL .../install.sh) --target /path/to/project

# Symlink mode — a pull in the source updates every linked project at once
bash <(curl -fsSL .../install.sh) --agent all --mode link
```

Then open the project in your agent and run `survey`.

---

## The problem

Most agent setups load the whole project context on every call. The project grows; the context
grows with it; every task pays for knowledge it will never use.

```
Without bands:            With bands:
──────────────────────    ──────────────────────────────
Every task loads:         A service task loads:
  full stack profile        [band:service] only
  frontend config           ~300 words, not ~3000
  database schemas
  CI/CD pipelines
  every standard
  (~3000 words)
```

The saving is not a convention you hope the model honours. A runtime returns exactly one band,
and a `PreToolUse` hook blocks any attempt to read the context file whole.

---

## How it works

### 1. One context file, five bands

`survey` writes `.buildcli/context.md`: a shared header plus five blocks that load independently.

```
.buildcli/context.md
├── Metadata / Stack / Architecture / Standards   ← shared header
├── [band:service]     ← read only by the service skill
├── [band:interface]   ← read only by the interface skill
├── [band:store]       ← read only by the store skill
├── [band:verify]      ← read only by the verify skill
└── [band:delivery]    ← read only by the delivery skill
```

Each band is capped at roughly 300 words and must stand on its own. A band that needs another band
to make sense is a band that was written wrong.

### 2. An active pointer, so paths never get passed by hand

```
.buildcli/
├── context.md            ← written by survey
├── active                ← one line: "blueprints/features/checkout-flow"
├── journal/session.log   ← audit trail, written by rig's hooks
└── hooks/session-end.sh  ← runs at the end of every Claude Code session

blueprints/
├── features/
│   ├── checkout-flow/
│   │   ├── brief.md      ← written by brief
│   │   ├── shape.md      ← written by shape
│   │   ├── worklist.md   ← written by worklist
│   │   └── audit.md      ← written by audit
│   └── user-auth/
│       └── brief.md
└── defects/
    └── payment-safari/
        └── brief.md      ← written by patch --trace
```

`shape`, `worklist`, `build`, and `audit` all read `.buildcli/active` themselves. Move it with `focus`.
Ask where you are with `pulse`.

The point is not convenience. It is that the work lives in files, so closing the session costs nothing.

### 3. Band skills, for all four agents

Every skill states which band to load and which to refuse.

| Skill       | Owns                                        | Claude    | Codex     | Gemini    | Copilot   |
|-------------|---------------------------------------------|-----------|-----------|-----------|-----------|
| `service`   | endpoints, business logic, auth             | implement | implement | review    | implement |
| `interface` | components, state, routing                  | implement | implement | review    | implement |
| `store`     | schemas, migrations, queries                | implement | implement | review    | implement |
| `verify`    | tests, coverage, CI gates                   | implement | implement | gaps      | implement |
| `delivery`  | CI/CD, environments, monitoring             | implement | implement | review    | implement |

Add your own at any time with `forge <name> <band>`.

### 4. The pipeline

| Stage      | Invoke      | Input                | Output                        |
|------------|-------------|----------------------|-------------------------------|
| Survey     | `/survey`   | the repository       | `.buildcli/context.md`           |
| Brief      | `/brief`    | a description        | `brief.md` + moves `active`   |
| Shape      | `/shape`    | auto, from `active`  | `shape.md`                    |
| Worklist   | `/worklist` | auto, from `active`  | `worklist.md`                 |
| Build      | `/build`    | auto, from `active`  | code + a build report         |
| Audit      | `/audit`    | auto, from `active`  | `audit.md`                    |

Plus, at any point:

| Command   | Does                                                            |
|-----------|-----------------------------------------------------------------|
| `/pulse`  | read-only snapshot: stage, unit counts, gates, next step         |
| `/focus`  | list blueprints, or move the active pointer to one               |
| `/patch`  | minimal defect fix; `--trace` files a defect blueprint           |
| `/forge`  | write a project-specific skill from real source patterns         |
| `/rig`    | Claude Code hooks, permissions, audit journal                    |

### 5. The runtime — what makes it a harness, not a convention

A framework of markdown files can only ask. `bcx`, installed to
`.buildcli/runtime/bcx`, can answer and refuse. Python 3, stdlib only, no dependencies.

```bash
bcx band service     # exactly that band — there is no call that returns the whole file
bcx next             # units ready now, grouped by band, computed from the graph
bcx graph            # critical path, and a hard error on a dependency cycle
bcx claim W03        # scopes the write gate to that unit's band
bcx verify           # runs the real test command and reports the real exit code
bcx doctor           # every structural problem, in one list
```

Three things stop being advisory:

| | Before | Now |
|---|---|---|
| Band scoping | the skill asks | `bcx band` returns one block; a hook blocks the raw read |
| Scheduling | the model infers order | the runtime computes it, and refuses to schedule a cycle |
| Verification | `audit` reads test files | `bcx verify` runs the suite |

### 6. Enforcement (Claude Code)

`rig --enforce` writes hooks that can say no:

| Hook | Effect |
|---|---|
| `PreToolUse` on `Read` | **blocks** a raw read of `.buildcli/context.md` |
| `PreToolUse` on `Write\|Edit` | **blocks** writes into a band other than the claimed unit's |
| `PostToolUse` | journals every edit and every test/lint/build command |
| `Stop` | journals the session end, optionally runs the suite |

```
.claude/settings.json          hooks + scoped permissions
.buildcli/bands.json           which paths each band owns
.buildcli/enforce.json         the off switch, per gate
.buildcli/journal/session.log  2026-08-22 14:32:01 | EDIT | src/api/checkout.ts
```

Two design rules worth knowing before you rely on it:

- **Every gate fails open.** Malformed input, missing config, internal error — the call is allowed.
  A harness that breaks the session on its own bug is worse than no harness.
- **Only cross-band writes are blocked.** Paths no band claims — docs, root config — always pass.

Blocking gates are Claude Code only; Codex, Gemini, and Copilot get the runtime but not the
enforcement. See `buildcli/RUNTIME.md` for the full contract.

---

## Workflows

### New project

```
1. install            copy commands and skills into the project
2. survey             write .buildcli/context.md
3. rig                hooks, permissions, journal (Claude Code)
```

### A feature, one agent

```
4. brief <describe>   blueprints/features/<slug>/ + active pointer set
5. shape              reads active
6. worklist           reads active
7. build              executes with live progress and sub-agent fan-out
8. audit              ✅ green / ⚠️ amber / ❌ red per acceptance criterion
```

### A feature, several agents

```
4. Gemini:  brief      requirements analysis; writes the relay block
5. Claude:  shape      architecture, reached through .buildcli/active
6. Claude:  worklist   dependency graph, parallel-safe batches
7. Codex:   build      focused generation, one band per unit
8. Gemini:  audit      gap analysis between intent and implementation
```

Everyone shares `.buildcli/context.md` and `blueprints/<kind>/<slug>/`. The relay block at the end of
every `brief.md` names who picks up next and how confident the handoff is.

### A defect

```
patch <describe> <file>            minimal fix, band detected automatically
patch <describe> <file> --trace    the same fix, plus a tracked defect blueprint
```

---

## Agent roles

| Agent       | Strength                       | Best at                                     | Commands |
|-------------|--------------------------------|---------------------------------------------|----------|
| **Claude**  | Reasoning, orchestration, harness | the full pipeline, multi-band features, sub-agent fan-out | all |
| **Codex**   | Focused code generation        | band-scoped implementation, tests, migrations | all but `rig` |
| **Gemini**  | Requirements and gap analysis  | briefs, readiness review, audits              | all but `rig` |
| **Copilot** | In-editor, model-agnostic      | implementation and fixes inside the IDE       | prompt templates |

### The relay block

```
## Relay
- Brief owner: Gemini
- Shape agent: Claude
- Build agent: Codex
- Brief confidence: high
- Blocking questions: none
- Ready for shape: yes
```

---

## Where things land

| Agent   | Commands                  | Skills                        | Startup file                      |
|---------|---------------------------|-------------------------------|-----------------------------------|
| Claude  | `.claude/commands/`       | `.claude/skills/`             | `CLAUDE.md`                       |
| Codex   | `.codex/commands/`        | `.codex/skills/`              | `AGENTS.md`                       |
| Gemini  | `.gemini/commands/`       | `.gemini/skills/`             | `GEMINI.md`                       |
| Copilot | `.copilot/commands/` ¹    | `.github/skills/` ²           | `.github/copilot-instructions.md` |

¹ Prompt templates — Copilot has no native slash commands.
² Auto-discovered by Copilot Agent Mode in VS Code.

Shared by all of them: `.buildcli/context.md`, `.buildcli/active`, `blueprints/`.

---

## Getting started

### Option 1 — curl

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/wheslleyrimar/buildcli-agents/main/install.sh)
```

### Option 2 — from a clone

```bash
./buildcli/scripts/bootstrap.sh --repo /path/to/your/project
```

### Options

```
--agent AGENT   claude | codex | gemini | copilot | all   (default: all)
--mode  MODE    copy | link                               (default: copy)
--target PATH   target project                            (install.sh)
--repo   PATH   target project                            (bootstrap.sh)
```

`copy` writes standalone files. `link` symlinks them, so pulling the BuildCLI Agents source updates every
linked project at once.

Bootstrap is safe to re-run. It rewrites only the block between the `buildcli:autoload` markers in
each startup file, and leaves everything you wrote around it untouched.

### What gets installed

```
<your-project>/
├── .claude/
│   ├── commands/   survey brief shape worklist build audit patch pulse focus forge rig
│   └── skills/     service interface store verify delivery design-review + the pipeline skills
├── .codex/
│   ├── commands/   survey brief shape worklist build audit patch pulse focus forge
│   └── skills/     service interface store verify delivery code-standard
├── .gemini/
│   ├── commands/   survey brief shape worklist build audit patch pulse focus forge
│   └── skills/     service interface store verify delivery requirement-split
├── .copilot/commands/   survey brief shape worklist build patch pulse focus mcp-add
├── .github/
│   ├── skills/     service interface store verify delivery
│   └── copilot-instructions.md
├── .buildcli/
│   ├── context.md
│   ├── runtime/buildcli     the executable
│   └── journal/
├── blueprints/
│   ├── features/
│   └── defects/
├── CLAUDE.md
├── AGENTS.md
└── GEMINI.md
```

---

## Repository layout

```
buildcli/         the kit — source for everything that gets installed
  runtime/        the buildcli executable (Python 3, stdlib only)
install.sh        curl entry point
SYSTEM-PROMPT.md  a system prompt for greenfield projects, for any agent
```

See `buildcli/RUNTIME.md` for the runtime contract, `buildcli/CATALOG.md` for every command and
skill, and `buildcli/ROUTING.md` for how each agent
finds its files.
