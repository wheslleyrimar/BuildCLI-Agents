"""Hook handlers — the part that can say no.

Claude Code runs these on PreToolUse / PostToolUse / Stop. A PreToolUse handler
that exits 2 blocks the tool call and shows stderr to the model, which turns the
band rule into a mechanism rather than a request.

Every handler fails open. A harness that bricks the session on its own bug is
worse than no harness, so any unexpected error allows the call through.
"""

import json
import os
import re
import sys

from . import paths, state, verify, worklist

ALLOW, BLOCK = 0, 2

DEFAULT_ENFORCE = {
    "enabled": True,
    "context_gate": True,   # force band reads through the CLI
    "write_gate": True,     # keep edits inside the claimed unit's band
    "verify_on_stop": False,
}


def _settings(root):
    path = os.path.join(paths.state_dir(root), "enforce.json")
    cfg = dict(DEFAULT_ENFORCE)
    try:
        cfg.update(json.loads(paths.read_text(path)))
    except Exception:
        pass
    return cfg


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


def _tool_path(event):
    ti = event.get("tool_input") or {}
    for key in ("file_path", "path", "notebook_path", "filePath"):
        v = ti.get(key)
        if isinstance(v, str) and v:
            return v
    return None


def _rel(root, path):
    try:
        return os.path.relpath(os.path.abspath(path), root).replace(os.sep, "/")
    except Exception:
        return path


def _deny(message):
    sys.stderr.write(message.rstrip() + "\n")
    return BLOCK


def current_band(root):
    """The band of the single in-progress unit, or None when it is ambiguous."""
    try:
        active = state.get_active(root)
        if not active:
            return None
        wl = os.path.join(root, active, "worklist.md")
        if not os.path.isfile(wl):
            return None
        units = worklist.parse(paths.read_text(wl))
    except Exception:
        return None

    claimed = [u for u in units if u["status"] == "in_progress"]
    if len(claimed) != 1:
        return None
    return claimed[0]["band"]


# ── handlers ──────────────────────────────────────────────────────────────────

def pre_read(root, event):
    cfg = _settings(root)
    if not (cfg["enabled"] and cfg["context_gate"]):
        return ALLOW

    path = _tool_path(event)
    if not path:
        return ALLOW

    rel = _rel(root, path)
    if rel != os.path.join(paths.STATE_DIR, paths.CONTEXT).replace(os.sep, "/"):
        return ALLOW

    return _deny(
        "Blocked: reading the whole context file defeats band scoping.\n"
        "Load exactly the band you need:\n"
        "    buildcli band <service|interface|store|verify|delivery>\n"
        "For the shared header only (Metadata / Stack / Architecture):\n"
        "    buildcli header"
    )


def pre_write(root, event):
    cfg = _settings(root)
    if not (cfg["enabled"] and cfg["write_gate"]):
        return ALLOW

    path = _tool_path(event)
    if not path:
        return ALLOW

    rel = _rel(root, path)
    if rel.startswith("..") or rel.startswith(paths.STATE_DIR + "/") or rel.startswith("blueprints/"):
        return ALLOW  # the framework's own state is not band-scoped

    band = current_band(root)
    if not band:
        return ALLOW  # no single claimed unit — nothing to enforce against

    if matches_band(root, rel, band) in (None, True):
        return ALLOW

    # Only cross-band writes are blocked. A path that no band claims — docs,
    # root config, scratch files — is not band-scoped territory, so it passes.
    owner = [b for b in _bands_map(root) if matches_band(root, rel, b)]
    if not owner:
        return ALLOW

    return _deny(
        "Blocked: %s belongs to the '%s' band, but the unit currently claimed "
        "is in '%s'.\n"
        "Cross-band work is a separate unit. Either flag it as a follow-up, or "
        "close this unit and claim one in the other band:\n"
        "    buildcli done <unit>\n"
        "    buildcli next" % (rel, owner[0], band))


def post_tool(root, event):
    path = _tool_path(event)
    tool = event.get("tool_name") or "tool"
    if path:
        state.journal(root, "edit", "%-9s %s" % (tool, _rel(root, path)))
    else:
        cmd = (event.get("tool_input") or {}).get("command")
        if cmd and re.search(r"\b(test|lint|build)\b", cmd):
            state.journal(root, "cmd", cmd.strip()[:200])
    return ALLOW


def on_stop(root, event):
    state.journal(root, "stop", "session ended")
    cfg = _settings(root)
    if not (cfg["enabled"] and cfg.get("verify_on_stop")):
        return ALLOW
    result = verify.run(root)
    if result["ran"] and not result["passed"]:
        sys.stderr.write("Tests failed at session end: %s\n" % result["command"])
    return ALLOW


HANDLERS = {
    "pre-read": pre_read,
    "pre-write": pre_write,
    "post": post_tool,
    "stop": on_stop,
}


def dispatch(name):
    """Entry point for `buildcli gate <name>`. Never propagates an exception."""
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
