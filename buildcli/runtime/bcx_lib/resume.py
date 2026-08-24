"""The resume digest — where a project left off, in one screen.

It lives in its own module because both ends need it and they cannot import each
other: `cli` exposes it as `bcx resume`, and `gate` prints it at SessionStart,
while `cli` already imports `gate`.

One rule governs everything here: the digest carries pointers, never band
content. It is injected into a fresh session as model-visible context, so a line
of `[band:service]` reaching it would defeat `gate.pre_read` from the inside and
band scoping would stop being a mechanism.

Two things enforce that, and both are needed. Nothing below reads context.md —
and journal details are trimmed on the way out, because the runtime does copy one
piece of band text into the log: `verify` records the command it discovered in
[band:verify]. Not reading the file is not enough on its own when something else
already carried a fragment across.
"""

import os

from . import paths, state, worklist

# Hard ceiling on the digest. It competes with the work for room in a fresh
# session's context — pointers are cheap, prose is not.
MAX_LINES = 30
MAX_ENTRIES = 12


def payload(root, entries=6):
    """Everything the digest reports, as data."""
    active, source = state.active_with_source(root)
    out = {
        "root": root,
        "active": active,
        "active_source": source,
        "stage": state.stage_of(root, active) if active else None,
        "units": None,
        "claimed": [],
        "ready": [],
        # Trimmed here too: `--json` is the same digest, and a model can read it.
        "journal": [dict(e, detail=safe_detail(e))
                    for e in state.journal_tail(root, min(entries, MAX_ENTRIES))],
    }
    if not active:
        return out
    wl = os.path.join(root, active, "worklist.md")
    if not os.path.isfile(wl):
        return out
    try:
        units = worklist.parse(paths.read_text(wl))
    except Exception:
        return out
    counts = {}
    for u in units:
        counts[u["status"]] = counts.get(u["status"], 0) + 1
    out["units"] = {"total": len(units), "by_status": counts}
    out["claimed"] = [u["id"] for u in units if u["status"] == "in_progress"]
    out["ready"] = [u["id"] for u in worklist.ready(units)]
    return out


def safe_detail(entry):
    """One journal detail, with band-derived text removed.

    `verify` journals `PASS exit=0 :: <command>`, and that command was read out of
    [band:verify]. The outcome is what a resuming session needs; the command is
    not, and it is the only band text the runtime puts in the log. The journal on
    disk keeps it — that file is for the human, and is never injected anywhere.
    """
    detail = entry.get("detail", "")
    if entry.get("kind") == "VERIFY" and " :: " in detail:
        return detail.split(" :: ", 1)[0] + " :: (command in [band:verify])"
    return detail


def lines(root, entries=6):
    """The digest as a list of lines, capped at MAX_LINES."""
    p = payload(root, entries)
    out = ["BuildCLI Agents — where this project left off"]
    if not p["active"]:
        out.append("  active   : (none) — run the `brief` skill to start one")
    else:
        out.append("  active   : %s%s" % (
            p["active"],
            "   (derived from git — `bcx active <path>` pins it)"
            if p["active_source"] == "derived" else ""))
        out.append("  stage    : %s" % p["stage"])
        u = p["units"]
        if u:
            out.append("  units    : %d (%s)" % (u["total"], ", ".join(
                "%s %d" % (k, v) for k, v in sorted(u["by_status"].items()))))
            out.append("  claimed  : %s" % (", ".join(p["claimed"]) or "none"))
            out.append("  ready    : %s" % (", ".join(p["ready"]) or "none"))
    if p["journal"]:
        out.append("  recent   :")
        for e in p["journal"]:
            out.append("    %s | %-6s | %s" % (e["stamp"], e["kind"], safe_detail(e)))
    out.append("  next     : `bcx next` for ready units, `bcx band <name>` for context")
    return out[:MAX_LINES]
