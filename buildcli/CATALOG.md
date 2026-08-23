# Catalog

Everything BuildCLI Agents installs, and what each piece does.

## Layout

```
buildcli/
├── claude/{commands,skills}    → installed to .claude/
├── codex/{commands,skills}     → installed to .codex/
├── gemini/{commands,skills}    → installed to .gemini/
├── copilot/commands            → installed to .copilot/commands/
├── copilot/skills              → installed to .github/skills/
├── _shared/templates/
└── scripts/bootstrap.sh
```

## Pipeline

| File          | Invoke as    | Input                       | Output                                 | When |
|---------------|--------------|-----------------------------|----------------------------------------|------|
| `survey.md`   | `/survey`    | the repository              | `.buildcli/context.md`                    | once per project, and whenever the stack shifts |
| `brief.md`    | `/brief`     | a feature description       | `blueprints/<kind>/<slug>/brief.md`    | once per piece of work |
| `shape.md`    | `/shape`     | auto, from `.buildcli/active`  | `blueprints/<kind>/<slug>/shape.md`    | after brief |
| `worklist.md` | `/worklist`  | auto, from `.buildcli/active`  | `blueprints/<kind>/<slug>/worklist.md` | after shape |
| `build.md`    | `/build`     | auto, from `.buildcli/active`  | code changes + a build report          | after worklist |
| `audit.md`    | `/audit`     | auto, from `.buildcli/active`  | `blueprints/<kind>/<slug>/audit.md`    | after build |
| `patch.md`    | `/patch`     | a defect description        | a fix + root cause                     | per defect; `--trace` files a blueprint |
| `forge.md`    | `/forge`     | skill name + band           | `<agent>/skills/<name>/SKILL.md`       | when a project pattern deserves a skill |

## Navigation and ops

| File        | Invoke as  | Input                  | Output                                          | When |
|-------------|------------|------------------------|-------------------------------------------------|------|
| `pulse.md`  | `/pulse`   | none                   | inline snapshot, nothing written                | any time |
| `focus.md`  | `/focus`   | a blueprint slug       | updated `.buildcli/active`                         | switching between blueprints |
| `rig.md`    | `/rig`     | `--minimal` \| `--full` \| `--enforce` | `.claude/settings.json`, `.buildcli/bands.json`, `.buildcli/enforce.json`, `.buildcli/journal/` | once per project (Claude Code only) |

### The three rig levels

Each level adds to the one before it, so `--enforce` can be applied later on top of a `--full` base.

| Level | Adds |
|---|---|
| `--minimal` | the audit journal — every edit recorded |
| `--full` (default) | band-scoped permissions in `settings.json` |
| `--enforce` | `PreToolUse` gates that **block** a raw read of the context file, and block writes into a band other than the claimed unit's |

`--enforce` is what turns the band rule from a convention into a mechanism. It also writes
`.buildcli/bands.json` (which paths each band owns) and `.buildcli/enforce.json` (the per-gate off
switch). Claude Code only — the other three agents have no blocking hook.

## Runtime commands

Not skills — a real executable at `.buildcli/runtime/bcx`. Skills call it by that full path,
never by a bare name. For your own terminal, the installer offers a dispatcher on PATH — or
`bcx shim --install` adds one later — so the short form below works from any subdirectory.
Full contract in `RUNTIME.md`.

| Command | Returns |
|---|---|
| `bcx band <name>` | exactly one context band |
| `bcx header` | the shared header, with no band |
| `bcx bands` | every band, populated or empty |
| `bcx active [path]` | read or move the active blueprint pointer |
| `bcx blueprints` | every blueprint with its stage |
| `bcx next` | units ready now, grouped by band |
| `bcx graph` | dependency graph, critical path, cycle report |
| `bcx claim\|done\|block <id>` | unit state transitions, written back to worklist.md |
| `bcx verify` | runs the test command, reports the exit code |
| `bcx status` | pipeline snapshot |
| `bcx doctor` | every structural problem in one list |
| `bcx gate <name>` | hook handler: `pre-read`, `pre-write`, `post`, `stop` |
| `bcx shim --install` | a PATH dispatcher, so a human can type `bcx` instead of the full path |

## Band skills

Each one reads exactly one block of `.buildcli/context.md` and refuses the rest.

| Skill       | Band               | Owns |
|-------------|--------------------|------|
| `service`   | `[band:service]`   | endpoints, business logic, auth, outbound integrations |
| `interface` | `[band:interface]` | components, pages, client state, routing, styling |
| `store`     | `[band:store]`     | schemas, migrations, models, queries, caching |
| `verify`    | `[band:verify]`    | unit, integration, and E2E tests; coverage |
| `delivery`  | `[band:delivery]`  | CI/CD, deploys, environments, secrets, monitoring |

## Agent-specific commands

| File          | Agent   | Purpose |
|---------------|---------|---------|
| `mcp-add.md`  | Copilot | add an MCP server to `.vscode/mcp.json`, without hardcoding a secret |

Copilot has no `audit`, `forge`, or `rig`: the first two are covered by its chat workflow, and the
third configures Claude Code hooks that Copilot does not have.

## Agent specialties

| Skill                | Agent  | Purpose |
|----------------------|--------|---------|
| `design-review`      | Claude | architecture tradeoffs and risk, before implementation |
| `code-standard`      | Codex  | implementation quality gates and validation evidence |
| `requirement-split`  | Gemini | break a broad request into prioritized requirements |

## The active pointer

Most commands read `.buildcli/active` on their own — no path argument needed.

```
.buildcli/active        ← one line: blueprints/features/checkout-flow

blueprints/
├── features/
│   └── checkout-flow/
│       ├── brief.md
│       ├── shape.md
│       ├── worklist.md
│       └── audit.md
└── defects/
    └── payment-safari/
        ├── brief.md     (written by /patch --trace)
        └── audit.md
```

Move it with `/focus <slug>`, or run `/focus` with no argument to see everything.

## Multi-agent relay

Every `brief.md` ends with a relay block:

```
## Relay
- Brief owner: Gemini
- Shape agent: Claude
- Build agent: Codex
- Brief confidence: high
- Blocking questions: none
- Ready for shape: yes
```

Any agent can open the project, read `.buildcli/active`, and continue. Nothing needs re-explaining
in chat, because nothing important lives in chat.

## Templates

| File                        | Used by |
|-----------------------------|---------|
| `context-template.md`       | bootstrap, as the initial `.buildcli/context.md` |
| `skill-template.md`         | `/forge`, as the skeleton for a new skill |
| `command-template.md`       | authoring a new command file |
| `brief-template.md`         | `/brief`, as the output shape |
