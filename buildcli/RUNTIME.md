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

**You can install a shim for typing at a prompt.** The installer offers it at the end of a run
(`--shim` accepts up front, `--no-shim` declines), and it is always available afterwards:

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

`.buildcli/active` is gitignored, because it is per-machine and per-branch and committing it would
make every merge fight over it. A fresh clone therefore has the blueprints but no pointer, so when
the file is missing the value is derived from git: the blueprint whose most recent commit is newest
wins. A blueprint that exists only in the working tree has no commit and is never a candidate, and
no git, no commits, or no candidate leaves you at `(none)` exactly as before.

Derivation resolves, it never persists. Every command that prints the value labels it — `bcx active`
says so on stderr and keeps stdout the bare path, `status`, `doctor`, and `resume` say so inline,
and `--json` carries it as `active_source`. Writing the pointer is still `bcx active <path>` alone.

### Scheduling

```bash
bcx graph [--json]        # units, critical path, cycles, structural problems
bcx next [--json]         # units ready now, grouped by band
bcx claim W03             # mark in progress — this is what scopes the write gate
bcx claim W03 --agent ui  # …on behalf of one named worker
bcx done W03
bcx block W03 --reason "waiting on credentials"
```

`graph` and `next` exit non-zero when the worklist is not schedulable. `claim` refuses a unit whose
dependencies are unmet. `--force` overrides that, and every refusal below.

`graph` reports who holds each unit — an `owner` field per unit in `--json`, an `active` block in the
plain output. `next` recommends an agent per band when `routing` is configured, and is byte-identical
to a run without one when it is not.

#### Identity

`--agent <id>` names the calling worker; `$BCX_AGENT_ID` is the fallback, and the flag wins over it.
The id is opaque and is never inferred — the runtime does not inspect its parent process.

Without an identity nothing changes from how the runtime has always behaved: one claim at a time,
and a second is refused with the same message and the same exit code.

With one, a claim is refused only by *that agent's* own other claims. A sibling worker holding a unit
in another band is not a conflict — it is the point of fanning out. Claiming a unit somebody else
holds needs `--force`, and the takeover is journaled as `STEAL`, apart from an ordinary `CLAIM`.
Reaching `done` or `blocked` releases the claim; closing a unit you do not own is allowed, because
someone has to be able to clear a unit whose worker is gone, and is journaled as `FREED`.

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
bcx resume [--json]       # where the project left off, in one screen
bcx doctor [--json]       # everything that is structurally wrong, in one list
```

`resume` is the memory half. It reports the active blueprint and its stage, unit counts by status,
what is claimed, what is ready, and the tail of the journal — capped at 30 lines, `--entries N` to
change the tail. It is what the `session-start` gate prints, so it is bound by one rule: **pointers
only, never band content.** A digest carrying band text would defeat `pre-read` from the inside.

Two mechanisms hold that, and one of them is not obvious. `resume` never reads `context.md` — but
that alone was not enough, because `verify` records the command it discovered in `[band:verify]`,
which put a fragment of a band into the journal the digest prints from. So VERIFY details are
trimmed at the ` :: ` before the command. The outcome survives, the command does not, and the log on
disk keeps both — that file is for the human and is never injected. Tests cover each half.

`doctor` checks: all five bands declared and populated, bands within the ~300 word budget, an active
blueprint, a schedulable worklist with valid band tags and real checks, and a discoverable test
command.

### Gates

```bash
bcx gate pre-read | pre-write | post | stop | session-start
```

Hook handlers. They read the event JSON on stdin and communicate by exit code: `0` allows, `2`
blocks and shows stderr to the model. Wired up by `rig --enforce` for Claude Code and Codex.

`stop` writes the checkpoint the next session reads: active blueprint, claimed units, how many units
completed since the previous `STOP`, and the verify outcome. `session-start` prints the `resume`
digest on stdout, which Claude Code and Codex add as model-visible context — so a session opens
knowing where the pipeline stands instead of having to ask. Neither can block; `session-start` is
not a tool call, and there is nothing there worth refusing.

The journal rotates in place. Past `journal_max_kb` the log becomes `session.1.log` and a fresh one
starts. One generation is kept on purpose — this is a resume aid, not an archive.

## Configuration

### Host hook files

`rig --enforce` writes the native hook file for the agent that runs it:

- Claude Code: `.claude/settings.json`
- Codex: `.codex/hooks.json`

Both call the same `.buildcli/runtime/bcx gate <name>` handlers and share
`.buildcli/bands.json`, `.buildcli/enforce.json`, and `.buildcli/journal/`.

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
  "verify_on_stop": false,
  "session_start": true,
  "journal_max_kb": 256,
  "routing": { "service": "codex", "interface": "claude" },
  "lock_timeout_s": 10
}
```

Every key is defaulted in the runtime, so a file written before a key existed keeps working.
`session_start: false` silences the digest; `journal_max_kb: 0` turns rotation off. `routing` maps a
band to the agent best suited to it and is read only by `bcx next` — an empty table means no
recommendation, never a recommendation of nobody. `lock_timeout_s` is how long a transition waits for
the worklist mutex before giving up.

### `.buildcli/claims/`

Who is holding what. Gitignored, like `active`: it describes what one machine is doing right now,
not what the project is. One file per claimed unit — owner, band, blueprint, and the pid, host, and
timestamp that let a refusal say something specific.

Two locks live here, and they are deliberately not the same thing:

| Lock | Guards | Held for | When the holder goes away |
|---|---|---|---|
| `<UNIT>.claim` | ownership of one unit | minutes to hours | never expires — `--force` only |
| `.worklist.lock` | any rewrite of `worklist.md` | milliseconds | broken on age |

Different lifetimes, so different staleness policies. A lease that outlived its worker should stop
that unit until a human looks: taking work away from an agent that is merely slow is worse than
waiting for it. A mutex that outlived its process must break, or one crash freezes every transition
in the project forever. Collapsing the two into one number is a bug, not a simplification — a waiter
would then break the lock at the exact moment it should have given up, stealing it from a live
holder.

Both are built on `os.open(..., O_CREAT | O_EXCL)`, the one atomic create-if-absent in the standard
library. The mutex exists because `worklist.set_status` reads the whole file, parses it, and rewrites
it: two agents transitioning *different* units hold perfectly valid claims and still lose one of the
two writes without it.

## Design rules

**Every gate fails open.** Malformed stdin, a missing config, an unknown project root, an internal
exception — the tool call is allowed. A harness that bricks the session on its own bug is worse
than no harness.

**The write gate only blocks cross-band writes.** A path that no band claims — documentation, root
config, scratch files — always passes. Enforcement targets the specific failure of drifting into
another band mid-unit, not all editing.

**Enforcement needs a single claimed unit *per caller*.** With an identity, the gate resolves that
agent's own claim and holds it to that band, so parallel workers each stay inside their own. Without
one — or when the host hands every worker the same `$BCX_AGENT_ID` — several claims look like one
caller, the band is ambiguous again, and the gate allows everything. That is the old behaviour, not
a new failure, and `bcx doctor` names it: two live claims sharing an owner is reported, because
enforcement does not error in that state, it silently stops.

**The gate reads the band from the markdown, never from the claim.** A claim file records the band it
was taken in, but `current_band` answers from `worklist.md`. Editing the writable state file cannot
talk the gate out of a band the markdown still asserts — failing open is not the same as failing
permissive.

**Markdown stays the source of truth.** The runtime reads and rewrites individual fields in
`worklist.md` in place. Nothing is stored in a database the human cannot see or edit.

## Portability

| Agent | Runtime | Blocking gates |
|---|---|---|
| Claude Code | yes | **yes** — PreToolUse hooks |
| Codex | yes | **yes** — project-local Codex hooks |
| Gemini | yes, via shell | no equivalent hook |
| Copilot | yes, via shell | no equivalent hook |

All four benefit from deterministic band extraction, real scheduling, and executable verification.
Claude Code and Codex can also enforce read/write gates through lifecycle hooks.
