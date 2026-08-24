"""Locating the project root and the files the runtime owns."""

import json
import os

STATE_DIR = ".buildcli"
CONTEXT = "context.md"
ACTIVE = "active"
BANDS_MAP = "bands.json"
ENFORCE = "enforce.json"
JOURNAL = os.path.join("journal", "session.log")
JOURNAL_PREV = os.path.join("journal", "session.1.log")

# Ownership of a claimed unit. One file per unit, plus the short mutex that
# serialises rewrites of worklist.md. Both are gitignored: like `active`, they
# describe what one machine is doing right now, not what the project is.
CLAIMS = "claims"
CLAIM_SUFFIX = ".claim"
WORKLIST_LOCK = ".worklist.lock"

# Which kit revision this copy of the runtime came from. Deliberately not a .py
# file, and deliberately not inside bcx_lib/ — see build_stamp().
BUILD_STAMP = "BUILD"

BANDS = ("service", "interface", "store", "verify", "delivery")

# The switch file, with every key defaulted. It lives here rather than in gate.py
# because the journal writer needs `journal_max_kb` and gate.py imports state.py,
# not the other way round. One dictionary, so a new key cannot drift between two.
DEFAULT_ENFORCE = {
    "enabled": True,
    "context_gate": True,     # force band reads through the CLI
    "write_gate": True,       # keep edits inside the claimed unit's band
    "verify_on_stop": False,
    "session_start": True,    # inject the resume digest when a session opens
    "journal_max_kb": 256,    # rotate past this size; 0 or less disables rotation
    "routing": {},            # band -> agent name, reported by `bcx next`
    "lock_timeout_s": 10,     # how long a transition waits for the worklist mutex
}


class ProjectError(Exception):
    """Raised when the runtime cannot operate on the current directory."""


def find_root(start=None):
    """Walk upward looking for a .buildcli/ directory.

    Returns the project root. Raises ProjectError when there is none, so every
    command fails with the same actionable message instead of a stack trace.
    """
    cur = os.path.abspath(start or os.getcwd())
    while True:
        if os.path.isdir(os.path.join(cur, STATE_DIR)):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            raise ProjectError(
                "no .buildcli/ found in this directory or any parent.\n"
                "Run the bootstrap script from your project root first."
            )
        cur = parent


def state_dir(root):
    return os.path.join(root, STATE_DIR)


def context_path(root):
    return os.path.join(root, STATE_DIR, CONTEXT)


def active_path(root):
    return os.path.join(root, STATE_DIR, ACTIVE)


def bands_map_path(root):
    return os.path.join(root, STATE_DIR, BANDS_MAP)


def enforce_path(root):
    return os.path.join(root, STATE_DIR, ENFORCE)


def journal_path(root):
    return os.path.join(root, STATE_DIR, JOURNAL)


def journal_prev_path(root):
    return os.path.join(root, STATE_DIR, JOURNAL_PREV)


def runtime_dir():
    """The directory this runtime is executing from.

    Resolved from `__file__`, not from the project root, because the two are not
    the same thing: the kit runs out of `buildcli/runtime/`, an installed project
    out of `.buildcli/runtime/`. Whichever copy is running is the one whose build
    stamp answers "which version is this".
    """
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build_stamp():
    """The kit revision this runtime was installed from, or None.

    Written by `bootstrap.sh` at install time, because the runtime cannot ask git
    itself: it is *copied* into the target project, so a `git rev-parse` there
    would report the target's history rather than the kit's. It lives outside
    `bcx_lib/` so that `doctor`'s stale-runtime check — which compares the two
    module directories file by file — does not read it as drift.
    """
    try:
        with open(os.path.join(runtime_dir(), BUILD_STAMP), "r", encoding="utf-8") as fh:
            return fh.read().strip() or None
    except Exception:
        return None


def claims_dir(root):
    return os.path.join(root, STATE_DIR, CLAIMS)


def claim_path(root, unit):
    """The claim file for one unit.

    Unit ids come from `worklist.UNIT_HEAD`, which admits `[A-Za-z]\\w*` and so
    can never contain a separator. The guard is here anyway because this is the
    only place a caller-supplied id becomes a filesystem path, and a traversal
    is not the kind of bug worth discovering later.
    """
    if not unit or not all(c.isalnum() or c == "_" for c in unit):
        raise ProjectError("invalid unit id for a claim: %r" % (unit,))
    return os.path.join(claims_dir(root), unit + CLAIM_SUFFIX)


def lock_path(root):
    """The mutex guarding every read-modify-write of worklist.md.

    It lives beside the claims because it is the same kind of state, but its
    lifetime is the opposite: a claim is held for as long as the work takes and
    never expires on its own, while this is held for milliseconds and must break
    on age — otherwise one crashed process freezes every transition in the
    project.
    """
    return os.path.join(claims_dir(root), WORKLIST_LOCK)


def settings(root):
    """The enforce.json switch, with defaults filled in. Never raises."""
    cfg = dict(DEFAULT_ENFORCE)
    try:
        data = json.loads(read_text(enforce_path(root)))
        if isinstance(data, dict):
            cfg.update(data)
    except Exception:
        pass
    return cfg


def read_text(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def write_text(path, text):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, path)
