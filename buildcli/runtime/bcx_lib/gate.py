"""Hook handlers — the part that can say no.

Claude Code and Codex run these on their lifecycle hook events. A PreToolUse
handler that exits 2 blocks the tool call and shows stderr to the model, which
turns the band rule into a mechanism rather than a request.

Every handler fails open. A harness that bricks the session on its own bug is
worse than no harness, so any unexpected error allows the call through.
"""

import json
import os
import re
import sys

from . import claims, paths, resume, state, verify, worklist

ALLOW, BLOCK = 0, 2

# The defaults live in paths.py — state.py needs the journal cap from the same
# file, and it cannot import this module without a cycle.
DEFAULT_ENFORCE = paths.DEFAULT_ENFORCE


def _settings(root):
    return paths.settings(root)


def _bands_map(root):
    try:
        data = json.loads(paths.read_text(paths.bands_map_path(root)))
    except Exception:
        return {}
    return {k: v for k, v in data.items() if isinstance(v, list)}


def _glob_to_regex(pattern):
    """Translate a path glob to a regex. Handles ** across separators."""
    out, i = [], 0
    while i < len(pattern):
        c = pattern[i]
        if pattern.startswith("**/", i):
            out.append(r"(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(r".*")
            i += 2
        elif c == "*":
            out.append(r"[^/]*")
            i += 1
        elif c == "?":
            out.append(r"[^/]")
            i += 1
        else:
            out.append(re.escape(c))
            i += 1
    return re.compile(r"^" + "".join(out) + r"$")


def matches_band(root, rel_path, band):
    patterns = _bands_map(root).get(band) or []
    if not patterns:
        return None  # nothing configured — cannot judge
    return any(_glob_to_regex(p).match(rel_path) for p in patterns)


def read_event():
    try:
        raw = sys.stdin.read()
    except Exception:
        return {}
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _paths_from_patch(command):
    """Files named by an apply_patch payload, best-effort and fail-open."""
    if not isinstance(command, str):
        return []
    out = []
    for line in command.splitlines():
        m = re.match(r"^\*\*\* (?:Add|Delete|Update) File: (.+)$", line)
        if not m:
            m = re.match(r"^\*\*\* Move to: (.+)$", line)
        if m:
            out.append(m.group(1).strip())
    return out


def _tool_paths(event):
    ti = event.get("tool_input") or {}
    out = []
    for key in ("file_path", "path", "notebook_path", "filePath"):
        v = ti.get(key)
        if isinstance(v, str) and v:
            out.append(v)
    # Codex reports apply_patch as tool_input.command. Parse the patch so the
    # same write gate can judge the changed files without knowing the host.
    out.extend(_paths_from_patch(ti.get("command")))

    seen, unique = set(), []
    for path in out:
        if path not in seen:
            unique.append(path)
            seen.add(path)
    return unique


def _tool_path(event):
    paths = _tool_paths(event)
    return paths[0] if paths else None


def _command_mentions_context(root, event):
    """Whether a shell command tries to read the whole context file."""
    command = (event.get("tool_input") or {}).get("command")
    if not isinstance(command, str):
        return False
    haystack = command.replace(os.sep, "/")
    rel = os.path.join(paths.STATE_DIR, paths.CONTEXT).replace(os.sep, "/")
    dot_rel = "./" + rel
    abs_path = os.path.join(root, paths.STATE_DIR, paths.CONTEXT).replace(os.sep, "/")
    return rel in haystack or dot_rel in haystack or abs_path in haystack


def _rel(root, path):
    try:
        if not os.path.isabs(path):
            path = os.path.join(root, path)
        return os.path.relpath(os.path.abspath(path), root).replace(os.sep, "/")
    except Exception:
        return path


def _deny(message):
    sys.stderr.write(message.rstrip() + "\n")
    return BLOCK


def active_units(root):
    """The active blueprint's units, or [] when there is no readable worklist."""
    try:
        active = state.get_active(root)
        if not active:
            return []
        wl = os.path.join(root, active, "worklist.md")
        if not os.path.isfile(wl):
            return []
        return worklist.parse(paths.read_text(wl))
    except Exception:
        return []


def current_band(root, agent=None):
    """The band this caller may write to, or None when that cannot be settled.

    Without an agent the rule is the original one: exactly one unit in progress,
    or nothing is enforced. It has to stay that way — a session with no identity
    must behave as it did before identities existed.

    With an agent, the question becomes *which* of several live claims is this
    caller's. Exactly one, and it must still be in progress in the worklist: a
    claim file left behind by a unit somebody already closed is drift, not
    authority, and enforcing a band from it would block writes on the strength of
    a stale file. `bcx doctor` reports that case; the gate declines to act on it.

    Returning None always means "allow". Every path out of here that cannot prove
    a band takes that exit.
    """
    units = active_units(root)
    if agent is not None:
        mine = claims.held_by(root, agent)
        if len(mine) != 1:
            return None
        live = [u for u in units
                if u["id"] == mine[0] and u["status"] == "in_progress"]
        return live[0]["band"] if len(live) == 1 else None
    claimed = [u for u in units if u["status"] == "in_progress"]
    if len(claimed) != 1:
        return None
    return claimed[0]["band"]


# ── handlers ──────────────────────────────────────────────────────────────────

def pre_read(root, event):
    cfg = _settings(root)
    if not (cfg["enabled"] and cfg["context_gate"]):
        return ALLOW

    if _command_mentions_context(root, event):
        return _deny(
            "Blocked: reading the whole context file defeats band scoping.\n"
            "Load exactly the band you need:\n"
            "    bcx band <service|interface|store|verify|delivery>\n"
            "For the shared header only (Metadata / Stack / Architecture):\n"
            "    bcx header"
        )

    path = _tool_path(event)
    if not path:
        return ALLOW

    rel = _rel(root, path)
    if rel != os.path.join(paths.STATE_DIR, paths.CONTEXT).replace(os.sep, "/"):
        return ALLOW

    return _deny(
        "Blocked: reading the whole context file defeats band scoping.\n"
        "Load exactly the band you need:\n"
        "    bcx band <service|interface|store|verify|delivery>\n"
        "For the shared header only (Metadata / Stack / Architecture):\n"
        "    bcx header"
    )


def pre_write(root, event):
    cfg = _settings(root)
    if not (cfg["enabled"] and cfg["write_gate"]):
        return ALLOW

    target_paths = _tool_paths(event)
    if not target_paths:
        return ALLOW

    # Identity comes from the environment and nowhere else — a hook event carries
    # no agent field, and guessing one would be worse than not knowing. When the
    # host gives every worker the same environment, this resolves to one value
    # for all of them, `current_band` finds several claims, and the gate falls
    # back to allowing. That is the old behaviour, not a new failure.
    agent = claims.resolve_identity()
    band = current_band(root, agent)
    if not band:
        return ALLOW  # nothing this caller can be held to — nothing to enforce

    for path in target_paths:
        rel = _rel(root, path)
        if rel.startswith("..") or rel.startswith(paths.STATE_DIR + "/") or \
                rel.startswith("blueprints/"):
            continue  # the framework's own state is not band-scoped

        if matches_band(root, rel, band) in (None, True):
            continue

        # Only cross-band writes are blocked. A path that no band claims — docs,
        # root config, scratch files — is not band-scoped territory, so it passes.
        owner = [b for b in _bands_map(root) if matches_band(root, rel, b)]
        if not owner:
            continue

        return _deny(
            "Blocked: %s belongs to the '%s' band, but the unit %s is in '%s'.\n"
            "Cross-band work is a separate unit. Either flag it as a follow-up, or "
            "close this unit and claim one in the other band:\n"
            "    bcx done <unit>\n"
            "    bcx next"
            % (rel, owner[0],
               "%s has claimed" % agent if agent else "currently claimed", band))

    return ALLOW


def post_tool(root, event):
    target_paths = _tool_paths(event)
    tool = event.get("tool_name") or "tool"
    if target_paths:
        for path in target_paths:
            state.journal(root, "edit", "%-9s %s" % (tool, _rel(root, path)))
    else:
        cmd = (event.get("tool_input") or {}).get("command")
        if cmd and re.search(r"\b(test|lint|build)\b", cmd):
            state.journal(root, "cmd", cmd.strip()[:200])
    return ALLOW


def checkpoint(root, result=None):
    """The one line a session leaves behind for the next one to read.

    Pointers only — blueprint, claimed units, what finished, how the suite ended.
    Never band content: this line is read back into a fresh session's context.
    """
    active = state.get_active(root) or "(none)"
    claimed = [u["id"] for u in active_units(root) if u["status"] == "in_progress"]
    # Counted before the new STOP line lands, so the window is the session just ending.
    completed = len([e for e in state.journal_since_stop(root) if e["kind"] == "DONE"])
    if result is None:
        outcome = "not-run"
    elif not result.get("ran"):
        outcome = "unavailable"
    else:
        outcome = "pass" if result.get("passed") else "fail"
    return "blueprint=%s claimed=%s completed=%d verify=%s" % (
        active, ",".join(claimed) or "-", completed, outcome)


def on_stop(root, event):
    cfg = _settings(root)
    result = None
    if cfg["enabled"] and cfg.get("verify_on_stop"):
        result = verify.run(root)
    state.journal(root, "stop", checkpoint(root, result))
    if result and result["ran"] and not result["passed"]:
        sys.stderr.write("Tests failed at session end: %s\n" % result["command"])
    return ALLOW


def session_start(root, event):
    """Print the resume digest so a fresh session opens knowing where it is.

    SessionStart is one of the three events whose plain stdout Claude Code adds
    as model-visible context, so exit 0 and print is the whole contract — there
    is no JSON envelope to fill in. It never blocks: an opening session is not a
    tool call, and there is nothing here worth refusing.
    """
    cfg = _settings(root)
    if not (cfg["enabled"] and cfg.get("session_start")):
        return ALLOW
    for line in resume.lines(root):
        sys.stdout.write(line + "\n")
    return ALLOW


HANDLERS = {
    "pre-read": pre_read,
    "pre-write": pre_write,
    "post": post_tool,
    "stop": on_stop,
    "session-start": session_start,
}


def dispatch(name):
    """Entry point for `bcx gate <name>`. Never propagates an exception."""
    handler = HANDLERS.get(name)
    if handler is None:
        sys.stderr.write("unknown gate '%s' (use: %s)\n" % (name, ", ".join(HANDLERS)))
        return ALLOW
    event = read_event()
    try:
        root = paths.find_root(event.get("cwd") or None)
    except Exception:
        return ALLOW
    try:
        return handler(root, event)
    except Exception:
        return ALLOW
