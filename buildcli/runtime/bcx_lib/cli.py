"""Command dispatch for the buildcli runtime."""

import argparse
import json
import os
import sys

from . import (__version__, claims, context, gate, paths, resume, shim, state,
               verify, worklist)

OK, FAIL, MISUSE = 0, 1, 2

JOURNAL_KIND = {"in_progress": "claim", "done": "done", "blocked": "block"}

# Statuses that end a unit's turn. Reaching one drops the claim: the work is
# either finished or handed back, and either way nobody is holding it.
TERMINAL = ("done", "blocked")

AGENT_HELP = ("identity of the calling agent (default: $BCX_AGENT_ID). "
              "Parallel workers each pass their own, so the write gate can tell "
              "them apart")


def _out(obj, as_json):
    if as_json:
        print(json.dumps(obj, indent=2, sort_keys=True))
        return True
    return False


def _worklist_path(root, blueprint=None):
    rel = blueprint or state.require_active(root)
    return os.path.join(root, rel, "worklist.md"), rel


# ── context ───────────────────────────────────────────────────────────────────

def cmd_band(root, args):
    body = context.extract(root, args.name)
    if args.check and not context.is_populated(body):
        sys.stderr.write(
            "band '%s' has no populated fields — run the `survey` skill.\n" % args.name)
        return FAIL
    sys.stdout.write(body)
    return OK


def cmd_header(root, args):
    sys.stdout.write(context.header(root))
    return OK


def cmd_bands(root, args):
    report = context.survey_report(root)
    if _out(report, args.json):
        return OK
    for row in report:
        print("  %-10s %-13s %4d words"
              % (row["band"], "populated" if row["populated"] else "EMPTY", row["words"]))
    return OK


# ── state ─────────────────────────────────────────────────────────────────────

def cmd_active(root, args):
    if args.target:
        rel = state.set_active(root, state.resolve(root, args.target))
        state.journal(root, "active", rel)
        print(rel)
        return OK
    current, source = state.active_with_source(root)
    if not current:
        sys.stderr.write("no active blueprint\n")
        return FAIL
    print(current)
    if source == "derived":
        # stdout stays the bare path — callers feed it straight to another command.
        sys.stderr.write("derived from git history; no local pointer. "
                         "`bcx active %s` writes one.\n" % current)
    return OK


def cmd_blueprints(root, args):
    rows = state.list_blueprints(root)
    if _out(rows, args.json):
        return OK
    if not rows:
        print("  no blueprints yet — run the `brief` skill")
        return OK
    for r in rows:
        flags = " ".join("%s%s" % (k, "+" if v else "-") for k, v in r["stages"].items())
        print("  %-42s %-9s %s%s"
              % (r["path"], r["stage"], flags, "   <- active" if r["active"] else ""))
    return OK


# ── graph ─────────────────────────────────────────────────────────────────────

def _routing(root):
    """The band -> agent table from enforce.json, empty when it is unusable.

    Scheduling is the one thing `next` must always be able to do, so a
    hand-mangled table degrades to "no recommendation" instead of an error.
    """
    table = paths.settings(root).get("routing")
    if not isinstance(table, dict):
        return {}
    return {b: a for b, a in table.items()
            if isinstance(b, str) and isinstance(a, str) and a}


def cmd_next(root, args):
    path, rel = _worklist_path(root, args.blueprint)
    _, units = worklist.load(path)
    problems = worklist.validate(units)
    blocking = [p for p in problems if "cycle" in p]
    if blocking:
        sys.stderr.write("worklist is not schedulable:\n  %s\n" % "\n  ".join(blocking))
        return FAIL

    grouped = worklist.batches(units)
    routing = _routing(root)

    def row(u):
        # The key is omitted, never emitted as null: a project with no routing
        # table must produce exactly the payload it produced before routing
        # existed, and an unmapped band is a gap in configuration rather than a
        # recommendation of "nobody".
        out = {k: u[k] for k in ("id", "name", "band", "check")}
        agent = routing.get(u["band"])
        if agent:
            out["agent"] = agent
        return out

    payload = {"blueprint": rel,
               "ready": {b: [row(u) for u in us] for b, us in grouped.items()}}
    if _out(payload, args.json):
        return OK

    if not grouped:
        remaining = [u for u in units if u["status"] != "done"]
        print("  nothing ready." if remaining else "  all units done.")
        for u in remaining:
            print("    %s %s (%s) blocked by %s"
                  % (u["id"], u["name"], u["status"], ", ".join(u["blocked_by"]) or "-"))
        return OK

    for band, us in sorted(grouped.items()):
        agent = routing.get(band)
        print("  [%s]%s" % (band, " -> %s" % agent if agent else ""))
        for u in us:
            print("    %-5s %s" % (u["id"], u["name"]))
            print("          check: %s" % u["check"])
    if len(grouped) > 1:
        print("\n  %d bands ready in parallel — safe to fan out one sub-agent per band."
              % len(grouped))
    return OK


def _owners(root):
    """unit id -> owning agent, for every claim on disk.

    One directory scan answers for the whole graph. `all_claims` already skips
    anything it cannot read, so a corrupt store degrades to "unowned" rather
    than to an error — reporting ownership must never be able to break `graph`.
    """
    return {unit: record.get("owner")
            for unit, record in claims.all_claims(root).items()}


def cmd_graph(root, args):
    path, rel = _worklist_path(root, args.blueprint)
    _, units = worklist.load(path)
    owners = _owners(root)

    def row(u):
        # `owner` is None for anything unclaimed, including an in_progress unit a
        # human set by hand in the markdown. Absent ownership is a fact worth
        # reporting, so the key is always present rather than conditional.
        out = {k: u[k] for k in
               ("id", "name", "band", "blocked_by", "status", "parallel", "check")}
        out["owner"] = owners.get(u["id"])
        return out

    payload = {
        "blueprint": rel,
        "units": [row(u) for u in units],
        "critical_path": worklist.critical_path(units),
        "cycles": worklist.find_cycles(units),
        "problems": worklist.validate(units),
    }
    if _out(payload, args.json):
        return FAIL if payload["problems"] else OK

    counts = {}
    for u in units:
        counts[u["status"]] = counts.get(u["status"], 0) + 1
    print("  units    : %d  (%s)" % (len(units),
          ", ".join("%s %d" % (k, v) for k, v in sorted(counts.items()))))
    cp = payload["critical_path"]
    print("  critical : %s" % (" -> ".join(cp) if cp else "(none)"))
    live = [u for u in units if u["status"] == "in_progress"]
    if live:
        print("  active   :")
        for u in live:
            print("    - %s (%s) held by %s"
                  % (u["id"], u["band"], owners.get(u["id"]) or "nobody"))
    if payload["problems"]:
        print("  problems :")
        for p in payload["problems"]:
            print("    - %s" % p)
        return FAIL
    print("  problems : none")
    return OK


def _identity(args):
    """Who is calling: `--agent` first, then BCX_AGENT_ID, then nobody.

    `None` is the ordinary single-agent case, and it has to stay
    indistinguishable from how the runtime behaved before identities existed.
    """
    return claims.resolve_identity(getattr(args, "agent", None))


def _apply(root, args, status, reason=""):
    """Write one status and journal it. The worklist mutex must already be held."""
    path, _ = _worklist_path(root, args.blueprint)
    unit = worklist.set_status(path, args.id, status, reason)
    owner = _identity(args)
    # The kind carries the transition, so the checkpoint can count completions
    # without parsing the detail. `journal` truncates a kind at six characters.
    state.journal(root, JOURNAL_KIND.get(status, "unit"),
                  "%s -> %s (%s)%s" % (args.id, status, unit["band"],
                                       " by %s" % owner if owner else ""))
    print("  %s %s -> %s" % (args.id, unit["name"], status))
    return OK


def _release(root, unit, owner):
    """Drop the claim a terminal transition ends.

    Closing a unit nobody claimed is ordinary and silent — plenty of work
    predates the claim store, and `done` must never fail because of it. Closing
    somebody *else's* is allowed on purpose: a human or an orchestrator has to be
    able to clear a unit whose worker is gone. It is journaled, because the agent
    that was holding it will not otherwise learn its work was closed out.
    """
    record = claims.release(root, unit)
    if record is None:
        return
    held = record.get("owner")
    if held != owner:
        state.journal(root, "freed", "%s released from %s by %s"
                      % (unit, held or "an unnamed agent", owner or "an unnamed agent"))


def _transition(root, args, status, reason=""):
    """One status change, serialised against every other writer.

    `worklist.set_status` reads the whole file, parses it, and rewrites it. Two
    agents transitioning *different* units are not in conflict as far as the
    worklist is concerned, and they still lose one of the two writes without
    this. The lock stays here rather than inside `set_status` so that a caller
    needing read-check-write — `cmd_claim` — can hold it across the whole span
    instead of only the write.
    """
    owner = _identity(args)
    try:
        with claims.worklist_lock(root):
            code = _apply(root, args, status, reason)
            if code == OK and status in TERMINAL:
                _release(root, args.id, owner)
            return code
    except claims.ClaimError as exc:
        sys.stderr.write("%s\n" % exc)
        return FAIL


def _blocking_units(root, units, target_id, owner):
    """The other in-progress units that stand in the way of this claim.

    Without an identity, every one of them does — that is the original rule, and
    it is the right one when the gate cannot tell two callers apart: a second
    claim would make the current band ambiguous and enforcement would stop.

    With an identity, only the caller's *own* other claims count. A sibling
    worker holding a unit in another band is not a conflict; it is the entire
    point of fanning out. An in-progress unit that no claim file covers — a
    hand-edited status, or one claimed before identities existed — belongs to
    nobody and blocks nobody; `bcx doctor` reports it instead.
    """
    others = [u["id"] for u in units
              if u["status"] == "in_progress" and u["id"] != target_id]
    if owner is None:
        return others
    mine = set(claims.held_by(root, owner))
    return [u for u in others if u in mine]


def cmd_claim(root, args):
    owner = _identity(args)
    try:
        with claims.worklist_lock(root):
            path, rel = _worklist_path(root, args.blueprint)
            _, units = worklist.load(path)
            already = _blocking_units(root, units, args.id, owner)
            if already and not args.force:
                if owner is None:
                    sys.stderr.write(
                        "already in progress: %s\n"
                        "The write gate keys off a single claimed unit. "
                        "Finish it, or pass --force.\n"
                        % ", ".join(already))
                else:
                    sys.stderr.write(
                        "%s already holds: %s\n"
                        "One unit at a time keeps that agent's band unambiguous. "
                        "Finish it, or pass --force.\n"
                        % (owner, ", ".join(already)))
                return FAIL
            target = next((u for u in units if u["id"] == args.id), None)
            if target is None:
                sys.stderr.write("unit '%s' not found\n" % args.id)
                return FAIL
            done = {u["id"] for u in units if u["status"] == "done"}
            missing = [d for d in target["blocked_by"] if d not in done]
            if missing and not args.force:
                sys.stderr.write("%s is blocked by: %s\n" % (args.id, ", ".join(missing)))
                return FAIL

            held = claims.read(root, args.id)
            foreign = held is not None and held.get("owner") != owner
            if foreign and not args.force:
                sys.stderr.write(
                    "%s is held by %s\n"
                    "Pass --force to take it over.\n"
                    % (args.id, claims.describe(held)))
                return FAIL

            if foreign:
                # A takeover is journaled apart from an ordinary claim: someone
                # else's work was interrupted, and that is worth finding later.
                state.journal(root, "steal", "%s taken from %s by %s"
                              % (args.id, held.get("owner") or "an unnamed agent",
                                 owner or "an unnamed agent"))
            claims.release(root, args.id)
            claims.acquire(root, args.id, owner, target["band"], rel)
            return _apply(root, args, "in_progress")
    except claims.ClaimError as exc:
        sys.stderr.write("%s\n" % exc)
        return FAIL


def cmd_done(root, args):
    return _transition(root, args, "done")


def cmd_block(root, args):
    return _transition(root, args, "blocked", args.reason)


# ── verify ────────────────────────────────────────────────────────────────────

def cmd_verify(root, args):
    result = verify.run(root, args.command, timeout=args.timeout)
    if args.json:
        payload = dict(result)
        payload["output"] = verify.tail(result.get("output", ""), args.lines)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return OK if result.get("passed") else FAIL
    if not result["ran"]:
        sys.stderr.write("  %s\n" % result["reason"])
        return FAIL
    print("  command : %s" % result["command"])
    print("  result  : %s (exit %s)"
          % ("PASS" if result["passed"] else "FAIL", result["exit"]))
    if not result["passed"]:
        print("  output  :")
        for line in verify.tail(result["output"], args.lines).splitlines():
            print("    %s" % line)
        return FAIL
    return OK


# ── diagnostics ───────────────────────────────────────────────────────────────

def cmd_status(root, args):
    active, source = state.active_with_source(root)
    payload = {"root": root, "active": active, "active_source": source,
               "bands": context.survey_report(root)}
    if active:
        payload["stage"] = state.stage_of(root, active)
        payload["stages"] = state.stages_present(root, active)
        wl = os.path.join(root, active, "worklist.md")
        if os.path.isfile(wl):
            units = worklist.parse(paths.read_text(wl))
            counts = {}
            for u in units:
                counts[u["status"]] = counts.get(u["status"], 0) + 1
            payload["units"] = {"total": len(units), "by_status": counts,
                                "ready": [u["id"] for u in worklist.ready(units)]}
    if _out(payload, args.json):
        return OK

    print("  root     : %s" % root)
    print("  active   : %s%s" % (active or "(none)",
                                 "   (derived — no local pointer)"
                                 if source == "derived" else ""))
    if active:
        print("  stage    : %s" % payload["stage"])
        u = payload.get("units")
        if u:
            print("  units    : %d (%s)" % (u["total"], ", ".join(
                "%s %d" % (k, v) for k, v in sorted(u["by_status"].items()))))
            print("  ready    : %s" % (", ".join(u["ready"]) or "none"))
    empty = [b["band"] for b in payload["bands"] if not b["populated"]]
    print("  bands    : %d declared%s"
          % (len(payload["bands"]), (", empty: " + ", ".join(empty)) if empty else ""))
    return OK


# `resume` lives in its own module: gate.py prints the same digest at
# SessionStart, and it cannot import cli.py — cli.py already imports it.
RESUME_MAX_LINES = resume.MAX_LINES
RESUME_MAX_ENTRIES = resume.MAX_ENTRIES
resume_payload = resume.payload
resume_lines = resume.lines


def cmd_resume(root, args):
    if _out(resume.payload(root, args.entries), args.json):
        return OK
    for line in resume.lines(root, args.entries):
        print(line)
    return OK


KIT_RUNTIME = os.path.join("buildcli", "runtime", "bcx_lib")


def stale_runtime(root):
    """First module where the installed runtime disagrees with the kit source.

    Only meaningful in the kit's own repository, which bootstraps itself: there,
    `.buildcli/runtime/` is a *copy* of `buildcli/runtime/`, so editing the source
    leaves the runtime this project actually executes behind — silently, and with
    the wrong behaviour. A normal project has no `buildcli/runtime/` and never
    sees this check. Returns None when there is nothing to say.
    """
    src = os.path.join(root, KIT_RUNTIME)
    dest = os.path.join(paths.state_dir(root), "runtime", "bcx_lib")
    if not (os.path.isdir(src) and os.path.isdir(dest)):
        return None
    try:
        here = sorted(f for f in os.listdir(src) if f.endswith(".py"))
        there = sorted(f for f in os.listdir(dest) if f.endswith(".py"))
        for name in here:
            if name not in there:
                return name
            if paths.read_text(os.path.join(src, name)) != \
                    paths.read_text(os.path.join(dest, name)):
                return name
        for name in there:
            if name not in here:
                return name
    except Exception:
        return None
    return None


def _claim_drift(root, active):
    """Where the claim store and the worklist stop agreeing.

    Ownership is auxiliary state: the markdown decides what is in progress, the
    store decides who is holding it. Every disagreement below means the write
    gate is reasoning from something nobody is maintaining — so this reports,
    and never rewrites. Which file is wrong is a judgement call, and the runtime
    does not get to make it.
    """
    if not active:
        return []
    wl = os.path.join(root, active, "worklist.md")
    if not os.path.isfile(wl):
        return []
    try:
        units = worklist.parse(paths.read_text(wl))
    except Exception:
        return []

    records = claims.all_claims(root)
    by_id = {u["id"]: u for u in units}
    out = []

    for unit in sorted(records):
        target = by_id.get(unit)
        if target is None:
            out.append("%s is claimed but is not in the worklist — "
                       "`bcx done %s` clears the claim" % (unit, unit))
        elif target["status"] != "in_progress":
            out.append("%s is claimed but its status is '%s' — the work was closed "
                       "without releasing it; `bcx done %s` clears the claim"
                       % (unit, target["status"], unit))

    for u in units:
        if u["status"] == "in_progress" and u["id"] not in records:
            out.append("%s is in_progress but nothing claims it — no agent owns "
                       "it, so the write gate has no band to enforce" % u["id"])

    held_by_owner = {}
    for unit, record in records.items():
        owner = record.get("owner")
        if owner:
            held_by_owner.setdefault(owner, []).append(unit)
    for owner, held in sorted(held_by_owner.items()):
        if len(held) > 1:
            # The quiet failure. Enforcement does not error here, it simply
            # stops: `current_band` cannot pick between two claims, so it
            # returns None and every write is allowed. Worth saying out loud.
            out.append("%s holds %s at once — the write gate cannot tell which "
                       "band applies and allows every write"
                       % (owner, ", ".join(sorted(held))))
    return out


def cmd_doctor(root, args):
    problems = []

    stale = stale_runtime(root)
    if stale:
        problems.append(
            "installed runtime is stale (bcx_lib/%s differs from the kit source) — "
            "re-run `bash buildcli/scripts/bootstrap.sh --repo .`" % stale)

    declared = context.band_names(root)
    for want in paths.BANDS:
        if want not in declared:
            problems.append("context.md is missing [band:%s]" % want)
    for row in context.survey_report(root):
        if not row["populated"]:
            problems.append("[band:%s] has no populated fields — run `survey`" % row["band"])
        if row["words"] > 400:
            problems.append("[band:%s] is %d words; the budget is ~300"
                            % (row["band"], row["words"]))

    active, source = state.active_with_source(root)
    notes = []
    if not active:
        problems.append("no active blueprint")
    else:
        if source == "derived":
            # Not a fault. A clone has the blueprints but not the gitignored
            # pointer, so the value was read out of git history instead.
            notes.append("active blueprint derived from git history — "
                         "`bcx active %s` pins it locally" % active)
        wl = os.path.join(root, active, "worklist.md")
        if os.path.isfile(wl):
            problems.extend("worklist: " + p
                            for p in worklist.validate(worklist.parse(paths.read_text(wl))))
        problems.extend("claims: " + p for p in _claim_drift(root, active))

    if verify.discover_command(root) is None:
        problems.append("no test command in [band:verify] — `verify` cannot run")

    if _out({"problems": problems, "notes": notes, "active_source": source,
             "ok": not problems}, args.json):
        return FAIL if problems else OK
    for n in notes:
        print("  note: %s" % n)
    if not problems:
        print("  all checks passed")
        return OK
    for p in problems:
        print("  - %s" % p)
    return FAIL


def cmd_gate(root, args):
    return gate.dispatch(args.name)


def cmd_shim(root, args):
    """Install (or print) the PATH dispatcher for human use.

    The framework's own files always call the runtime by its explicit project
    path. This is purely a convenience for typing at a prompt.
    """
    if not args.install:
        sys.stdout.write(shim.render())
        return OK
    try:
        path, notes = shim.install(args.dir, force=args.force)
    except RuntimeError as exc:
        sys.stderr.write("bcx: %s\n" % exc)
        return FAIL
    print("  installed  %s" % path)
    for note in notes:
        print("  note       %s" % note)
    print("  usage      bcx <command>, from anywhere inside a bootstrapped project")
    return OK


# ── parser ────────────────────────────────────────────────────────────────────

def build_parser():
    p = argparse.ArgumentParser(
        prog="bcx",
        description="BuildCLI Agents runtime — deterministic context, scheduling, enforcement.")
    p.add_argument("--version", action="version", version="bcx %s" % __version__)
    sub = p.add_subparsers(dest="cmd")

    def add(name, fn, help_text, needs_root=True):
        sp = sub.add_parser(name, help=help_text)
        sp.set_defaults(fn=fn, needs_root=needs_root)
        return sp

    sp = add("band", cmd_band, "print exactly one context band")
    sp.add_argument("name")
    sp.add_argument("--check", action="store_true", help="fail if the band is unpopulated")

    add("header", cmd_header, "print the shared context header, without any band")

    sp = add("bands", cmd_bands, "list bands and whether they are populated")
    sp.add_argument("--json", action="store_true")

    sp = add("active", cmd_active, "show or move the active blueprint pointer")
    sp.add_argument("target", nargs="?")

    sp = add("blueprints", cmd_blueprints, "list every blueprint and its stage")
    sp.add_argument("--json", action="store_true")

    sp = add("next", cmd_next, "units ready to start, grouped by band")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("--blueprint")

    sp = add("graph", cmd_graph, "dependency graph, critical path, cycle report")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("--blueprint")

    for name, fn, helptext in (("claim", cmd_claim, "mark a unit in progress"),
                               ("done", cmd_done, "mark a unit done")):
        sp = add(name, fn, helptext)
        sp.add_argument("id")
        sp.add_argument("--blueprint")
        sp.add_argument("--agent", default=None, help=AGENT_HELP)
        if name == "claim":
            sp.add_argument("--force", action="store_true")

    sp = add("block", cmd_block, "mark a unit blocked, with a reason")
    sp.add_argument("id")
    sp.add_argument("--reason", default="")
    sp.add_argument("--blueprint")
    sp.add_argument("--agent", default=None, help=AGENT_HELP)

    sp = add("verify", cmd_verify, "run the project's test command and report")
    sp.add_argument("--command")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("--timeout", type=int, default=900)
    sp.add_argument("--lines", type=int, default=40)

    sp = add("status", cmd_status, "machine-readable pipeline snapshot")
    sp.add_argument("--json", action="store_true")

    sp = add("resume", cmd_resume, "where this project left off, in one screen")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("--entries", type=int, default=6,
                    help="journal entries to show (capped at %d)" % RESUME_MAX_ENTRIES)

    sp = add("doctor", cmd_doctor, "validate context, graph, and configuration")
    sp.add_argument("--json", action="store_true")

    sp = add("gate", cmd_gate, "hook handler (reads the event on stdin)", needs_root=False)
    sp.add_argument("name", choices=sorted(gate.HANDLERS))

    sp = add("shim", cmd_shim, "print or install the PATH dispatcher for interactive use",
             needs_root=False)
    sp.add_argument("--install", action="store_true", help="write the shim to disk")
    sp.add_argument("--dir", default=None, help="target directory (default: ~/bin)")
    sp.add_argument("--force", action="store_true", help="replace an existing file")

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "cmd", None):
        parser.print_help()
        return MISUSE

    if not getattr(args, "needs_root", True):
        return args.fn(None, args)

    try:
        root = paths.find_root()
    except paths.ProjectError as exc:
        sys.stderr.write("bcx: %s\n" % exc)
        return FAIL

    try:
        return args.fn(root, args)
    except (paths.ProjectError, worklist.GraphError) as exc:
        sys.stderr.write("bcx: %s\n" % exc)
        return FAIL
    except BrokenPipeError:
        return OK
