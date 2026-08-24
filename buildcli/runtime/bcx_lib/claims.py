"""Who holds what, and the mutex that keeps the worklist honest.

Two locks live here, and they are not the same thing.

A **claim** is ownership of one unit. It is held for as long as the work takes,
and it never expires on its own: a lease that outlived its worker should stop
that unit until a human looks, because yanking a unit away from a slow-but-live
agent is worse than waiting for it.

The **worklist mutex** guards every read-modify-write of `worklist.md`. It is
held for milliseconds and it *must* break on age — `worklist.set_status` reads
the whole file, parses it, and rewrites it, so two agents transitioning
different units each hold a perfectly valid claim and still race on the markdown.
Without this, one status write is silently lost. And a mutex that never expired
would let a single crashed process freeze every transition in the project.

Both are built on `os.open(..., O_CREAT | O_EXCL)`, which is the one atomic
create-if-absent the standard library offers. No `fcntl`: it is stdlib, but
advisory locking buys nothing here and file creation is the primitive that
already stores the owner.
"""

import contextlib
import datetime
import errno
import json
import os
import socket
import time

from . import paths

POLL_SECONDS = 0.05

# How long the mutex must sit untouched before its holder is presumed dead.
#
# This is deliberately *not* `lock_timeout_s`. Using one number for both "how
# long I wait" and "how old is dead" means the two cross at the same instant, and
# because the staleness check runs first, a waiter breaks the lock at exactly the
# moment it would otherwise give up — stealing it from a holder that is merely
# slow. The window this guards is a single markdown rewrite, milliseconds long,
# so anything still holding it a minute later is gone.
STALE_FACTOR = 10
STALE_FLOOR_SECONDS = 60.0


class ClaimError(Exception):
    """Raised when a claim or the mutex cannot be taken."""


def resolve_identity(explicit=None):
    """The calling agent's identity, or None.

    Never inferred. An explicit argument wins, then the environment, then
    nothing — and `None` means every caller looks alike, which is what keeps the
    single-agent path behaving exactly as it always has.
    """
    if explicit:
        return explicit
    value = os.environ.get("BCX_AGENT_ID", "").strip()
    return value or None


def _record(owner, **extra):
    out = {
        "owner": owner,
        "pid": os.getpid(),
        "host": socket.gethostname(),
        "stamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    out.update(extra)
    return out


def _write_new(path, payload):
    """Create `path` with `payload`, or raise if it already exists.

    The O_EXCL create is the serialisation point: whoever creates the file wins,
    and every loser sees EEXIST rather than a half-written file.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except OSError as exc:
        if exc.errno == errno.EEXIST:
            raise ClaimError("already held")
        raise
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, sort_keys=True)
    except Exception:
        # A record nobody can parse is worse than no record: `read` would return
        # None and the holder would look free while the file still blocks writes.
        with contextlib.suppress(OSError):
            os.unlink(path)
        raise
    return payload


def read(root, unit):
    """One claim, or None when it is absent, unreadable, or not valid JSON.

    Returning None for a corrupt file is deliberate. Callers use this to decide
    whether to enforce, and enforcement must fail open.
    """
    try:
        with open(paths.claim_path(root, unit), "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def acquire(root, unit, owner=None, band=None, blueprint=None):
    """Take ownership of one unit. Raises ClaimError when it is already held."""
    payload = _record(owner, unit=unit, band=band, blueprint=blueprint)
    try:
        return _write_new(paths.claim_path(root, unit), payload)
    except ClaimError:
        held = read(root, unit)
        raise ClaimError("%s is held by %s" % (unit, describe(held)))


def release(root, unit):
    """Drop a claim. Returns the record that was there, or None if there was none."""
    existing = read(root, unit)
    with contextlib.suppress(OSError):
        os.unlink(paths.claim_path(root, unit))
    return existing


def steal(root, unit, owner=None, band=None, blueprint=None):
    """Take a claim someone else holds. The caller decides this is warranted."""
    previous = release(root, unit)
    return acquire(root, unit, owner, band, blueprint), previous


def all_claims(root):
    """Every claim on disk, keyed by unit id. Unreadable files are skipped."""
    out = {}
    try:
        names = sorted(os.listdir(paths.claims_dir(root)))
    except OSError:
        return out
    for name in names:
        if not name.endswith(paths.CLAIM_SUFFIX) or name.startswith("."):
            continue
        unit = name[:-len(paths.CLAIM_SUFFIX)]
        record = read(root, unit)
        if record is not None:
            out[unit] = record
    return out


def held_by(root, owner):
    """Unit ids this owner holds. With owner None, every claim regardless of owner."""
    claims = all_claims(root)
    if owner is None:
        return sorted(claims)
    return sorted(u for u, r in claims.items() if r.get("owner") == owner)


def age_seconds(record):
    """How long ago a record was stamped, or None when the stamp is unusable."""
    stamp = (record or {}).get("stamp")
    if not stamp:
        return None
    try:
        then = datetime.datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return None
    return max(0.0, (datetime.datetime.now() - then).total_seconds())


def describe(record):
    """A claim rendered for a refusal message. Specific enough to act on."""
    if not record:
        return "an unreadable claim"
    who = record.get("owner") or "an unnamed agent"
    age = age_seconds(record)
    where = record.get("host")
    parts = [str(who)]
    if where:
        parts.append("on %s" % where)
    if record.get("pid"):
        parts.append("pid %s" % record["pid"])
    if age is not None:
        parts.append("for %s" % _duration(age))
    return " ".join(parts)


def _duration(seconds):
    seconds = int(seconds)
    if seconds < 60:
        return "%ds" % seconds
    if seconds < 3600:
        return "%dm" % (seconds // 60)
    return "%dh%dm" % (seconds // 3600, (seconds % 3600) // 60)


@contextlib.contextmanager
def worklist_lock(root, timeout=None):
    """Serialise a read-modify-write of worklist.md.

    Unlike a claim, this breaks on age. Waiting forever on a dead process would
    make one crash permanently unschedulable, and the window it protects is a
    single file rewrite.
    """
    if timeout is None:
        timeout = paths.settings(root).get("lock_timeout_s", 10)
    try:
        timeout = float(timeout)
    except (TypeError, ValueError):
        timeout = 10.0

    path = paths.lock_path(root)
    stale_after = max(timeout * STALE_FACTOR, STALE_FLOOR_SECONDS)
    deadline = time.time() + max(0.0, timeout)
    while True:
        try:
            _write_new(path, _record(resolve_identity()))
            break
        except ClaimError:
            held = _read_path(path)
            # Staleness is measured from the file's mtime, not from the record's
            # `stamp`. The stamp is written to the second, so for a short timeout
            # a lock taken moments ago can measure older than the limit and get
            # broken while its holder is very much alive. mtime has sub-second
            # resolution and survives a record that failed to parse.
            age = _file_age(path)
            if age is not None and age > stale_after:
                # Older than any rewrite could be. Break it, then retry rather
                # than assuming the break succeeded — another waiter may have
                # broken it first and already be inside.
                with contextlib.suppress(OSError):
                    os.unlink(path)
                continue
            if time.time() >= deadline:
                raise ClaimError(
                    "timed out after %gs waiting for the worklist lock: %s\n"
                    "Held by %s. Remove it if that process is gone."
                    % (timeout, path, describe(held)))
            time.sleep(POLL_SECONDS)
    try:
        yield path
    finally:
        with contextlib.suppress(OSError):
            os.unlink(path)


def _file_age(path):
    """Seconds since `path` was last written, or None when it is gone."""
    try:
        return max(0.0, time.time() - os.path.getmtime(path))
    except OSError:
        return None


def _read_path(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return None
    return data if isinstance(data, dict) else None
