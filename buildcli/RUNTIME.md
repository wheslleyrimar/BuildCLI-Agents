# Runtime

`bcx` is the executable half of the framework. It exists so three things stop being requests
the model may ignore and start being mechanisms:

| Concern | Without the runtime | With it |
|---|---|---|
| Band scoping | a skill asks the model to read one block | `bcx band <name>` returns exactly one block, and a hook blocks the raw read |
| Scheduling | the model infers order from markdown | `bcx next` computes it from the graph, and refuses to schedule a cycle |
| Verification | `audit` reads test files and judges | `bcx verify` runs the suite and reports the exit code |

Python 3, standard library only. No build, no install, no dependencies. Bootstrap copies it to
`.buildcli/runtime/bcx` in the target project.

## Two ways to invoke it

The runtime is project-local: it lives at `.buildcli/runtime/bcx` and never enters your PATH.

**Agents call it by that path.** Every command and skill file in this framework spells it out in
full, because a bare name could be shadowed by another program or missing entirely on the machine
of whoever cloned the repository. Determinism beats brevity for something a model executes.

**You can install a shim for typing at a prompt:**

```bash
.buildcli/runtime/bcx shim --install          # writes ~/bin/bcx
.buildcli/runtime/bcx shim --install --dir /usr/local/bin
.buildcli/runtime/bcx shim                    # print it without installing
```

The shim walks up from your working directory and execs the runtime of whichever project you are
standing in, so one `bcx` on PATH serves every bootstrapped project — each on its own version. It
refuses to overwrite a file that is not itself, warns when another `bcx` would win on PATH, and
warns when the target directory is not on PATH.

After that, `bcx next` works from any subdirectory. Examples below use the short form; the long
form always works too.

## Commands

### Context

```bash
bcx band service          # print exactly that band
bcx band service --check  # exit 1 if the band is unpopulated
bcx header                # the shared header, with no band in it
bcx bands [--json]        # every band, populated or empty, with word counts
```

`band` is the only supported way to read project context. There is no path through the runtime
that returns the whole file.

### State

```bash
bcx active                                  # print the active blueprint
bcx active blueprints/features/checkout     # move the pointer (validates brief.md exists)
bcx active checkout                         # bare slug also resolves
bcx blueprints [--json]                     # every blueprint with its stage
```

### Scheduling

```bash
bcx graph [--json]        # units, critical path, cycles, structural problems
bcx next [--json]         # units ready now, grouped by band
bcx claim W03             # mark in progress — this is what scopes the write gate
bcx done W03
bcx block W03 --reason "waiting on credentials"
```

`graph` and `next` exit non-zero when the worklist is not schedulable. `claim` refuses a unit whose
dependencies are unmet, and refuses a second concurrent claim, because the write gate keys off there
being exactly one. `--force` overrides both.

### Verification

```bash
bcx verify                # run the test command from [band:verify]
bcx verify --command "npm test -- --run"
bcx verify --json --lines 60
```

The command is discovered from `[band:verify]`, preferring a value written in backticks. Exit code
mirrors the suite.

### Diagnostics

```bash
bcx status [--json]       # stage, unit counts, ready units, band population
bcx doctor [--json]       # everything that is structurally wrong, in one list
```

`doctor` checks: all five bands declared and populated, bands within the ~300 word budget, an active
blueprint, a schedulable worklist with valid band tags and real checks, and a discoverable test
command.

### Gates

```bash
bcx gate pre-read | pre-write | post | stop
```

Hook handlers. They read the event JSON on stdin and communicate by exit code: `0` allows, `2`
blocks and shows stderr to the model. Wired up by `rig --enforce`.

## Configuration

### `.buildcli/bands.json`

Maps a band to the paths it owns. The write gate reads this. A band with no entry is not enforced.

```json
{
  "service":   ["src/api/**", "src/services/**"],
  "interface": ["src/components/**", "src/pages/**"],
  "store":     ["migrations/**", "src/models/**"],
  "verify":    ["tests/**", "**/*.test.*"],
  "delivery":  [".github/workflows/**", "Dockerfile", "infra/**"]
}
```

Globs support `*`, `?`, and `**` across separators.

### `.buildcli/enforce.json`

The switch, so the gates can be tuned without touching `settings.json`.

```json
{
  "enabled": true,
  "context_gate": true,
  "write_gate": true,
  "verify_on_stop": false
}
```

## Design rules

**Every gate fails open.** Malformed stdin, a missing config, an unknown project root, an internal
exception — the tool call is allowed. A harness that bricks the session on its own bug is worse
than no harness.

**The write gate only blocks cross-band writes.** A path that no band claims — documentation, root
config, scratch files — always passes. Enforcement targets the specific failure of drifting into
another band mid-unit, not all editing.

**Enforcement needs a single claimed unit.** With zero or several units in progress the current band
is ambiguous, and the gate allows everything. Parallel sub-agents therefore run with the gate
effectively advisory; sequential bands keep it tight.

**Markdown stays the source of truth.** The runtime reads and rewrites individual fields in
`worklist.md` in place. Nothing is stored in a database the human cannot see or edit.

## Portability

| Agent | Runtime | Blocking gates |
|---|---|---|
| Claude Code | yes | **yes** — PreToolUse hooks |
| Codex | yes, via shell | no equivalent hook |
| Gemini | yes, via shell | no equivalent hook |
| Copilot | yes, via shell | no equivalent hook |

All four benefit from deterministic band extraction, real scheduling, and executable verification.
Only Claude Code can enforce.
