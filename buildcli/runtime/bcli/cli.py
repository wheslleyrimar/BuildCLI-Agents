"""Command dispatch for the buildcli runtime."""

import argparse
import json
import os
import sys

from . import __version__, context, gate, paths, state, verify, worklist

OK, FAIL, MISUSE = 0, 1, 2


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
    current = state.get_active(root)
    if not current:
        sys.stderr.write("no active blueprint\n")
        return FAIL
    print(current)
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

def cmd_next(root, args):
    path, rel = _worklist_path(root, args.blueprint)
    _, units = worklist.load(path)
    problems = worklist.validate(units)
    blocking = [p for p in problems if "cycle" in p]
    if blocking:
        sys.stderr.write("worklist is not schedulable:\n  %s\n" % "\n  ".join(blocking))
        return FAIL

    grouped = worklist.batches(units)
    payload = {"blueprint": rel,
               "ready": {b: [{k: u[k] for k in ("id", "name", "band", "check")} for u in us]
                         for b, us in grouped.items()}}
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
        print("  [%s]" % band)
        for u in us:
            print("    %-5s %s" % (u["id"], u["name"]))
            print("          check: %s" % u["check"])
    if len(grouped) > 1:
        print("\n  %d bands ready in parallel — safe to fan out one sub-agent per band."
              % len(grouped))
    return OK


def cmd_graph(root, args):
    path, rel = _worklist_path(root, args.blueprint)
    _, units = worklist.load(path)
    payload = {
        "blueprint": rel,
        "units": [{k: u[k] for k in
                   ("id", "name", "band", "blocked_by", "status", "parallel", "check")}
                  for u in units],
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
    if payload["problems"]:
        print("  problems :")
        for p in payload["problems"]:
            print("    - %s" % p)
        return FAIL
    print("  problems : none")
    return OK


def _transition(root, args, status, reason=""):
    path, _ = _worklist_path(root, args.blueprint)
    unit = worklist.set_status(path, args.id, status, reason)
    state.journal(root, "unit", "%s -> %s (%s)" % (args.id, status, unit["band"]))
    print("  %s %s -> %s" % (args.id, unit["name"], status))
    return OK


def cmd_claim(root, args):
    path, _ = _worklist_path(root, args.blueprint)
    _, units = worklist.load(path)
    already = [u["id"] for u in units if u["status"] == "in_progress" and u["id"] != args.id]
    if already and not args.force:
        sys.stderr.write(
            "already in progress: %s\n"
            "The write gate keys off a single claimed unit. Finish it, or pass --force.\n"
            % ", ".join(already))
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
    return _transition(root, args, "in_progress")


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
    active = state.get_active(root)
    payload = {"root": root, "active": active, "bands": context.survey_report(root)}
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
    print("  active   : %s" % (active or "(none)"))
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


def cmd_doctor(root, args):
    problems = []

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

    active = state.get_active(root)
    if not active:
        problems.append("no active blueprint")
    else:
        wl = os.path.join(root, active, "worklist.md")
        if os.path.isfile(wl):
            problems.extend("worklist: " + p
                            for p in worklist.validate(worklist.parse(paths.read_text(wl))))

    if verify.discover_command(root) is None:
        problems.append("no test command in [band:verify] — `verify` cannot run")

    if _out({"problems": problems, "ok": not problems}, args.json):
        return FAIL if problems else OK
    if not problems:
        print("  all checks passed")
        return OK
    for p in problems:
        print("  - %s" % p)
    return FAIL


def cmd_gate(root, args):
    return gate.dispatch(args.name)


# ── parser ────────────────────────────────────────────────────────────────────

def build_parser():
    p = argparse.ArgumentParser(
        prog="buildcli",
        description="BuildCLI Agents runtime — deterministic context, scheduling, enforcement.")
    p.add_argument("--version", action="version", version="buildcli %s" % __version__)
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
        if name == "claim":
            sp.add_argument("--force", action="store_true")

    sp = add("block", cmd_block, "mark a unit blocked, with a reason")
    sp.add_argument("id")
    sp.add_argument("--reason", default="")
    sp.add_argument("--blueprint")

    sp = add("verify", cmd_verify, "run the project's test command and report")
    sp.add_argument("--command")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("--timeout", type=int, default=900)
    sp.add_argument("--lines", type=int, default=40)

    sp = add("status", cmd_status, "machine-readable pipeline snapshot")
    sp.add_argument("--json", action="store_true")

    sp = add("doctor", cmd_doctor, "validate context, graph, and configuration")
    sp.add_argument("--json", action="store_true")

    sp = add("gate", cmd_gate, "hook handler (reads the event on stdin)", needs_root=False)
    sp.add_argument("name", choices=sorted(gate.HANDLERS))

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
        sys.stderr.write("buildcli: %s\n" % exc)
        return FAIL

    try:
        return args.fn(root, args)
    except (paths.ProjectError, worklist.GraphError) as exc:
        sys.stderr.write("buildcli: %s\n" % exc)
        return FAIL
    except BrokenPipeError:
        return OK
