"""The active blueprint pointer, blueprint discovery, and the journal."""

import datetime
import os
import subprocess

from . import paths

KINDS = ("features", "defects")
STAGE_FILES = (("brief", "brief.md"), ("shape", "shape.md"),
               ("worklist", "worklist.md"), ("audit", "audit.md"))

_DERIVED_CACHE = {}


def blueprint_dirs(root):
    """Every directory under blueprints/ that holds a brief.md, in path order."""
    out = []
    for kind in KINDS:
        base = os.path.join(root, "blueprints", kind)
        if not os.path.isdir(base):
            continue
        for slug in sorted(os.listdir(base)):
            rel = os.path.join("blueprints", kind, slug)
            if os.path.isfile(os.path.join(root, rel, "brief.md")):
                out.append(rel)
    return out


def _last_commit_ts(root, rel):
    """When this blueprint was last committed, or None if git cannot say."""
    try:
        out = subprocess.check_output(
            ["git", "log", "-1", "--format=%ct", "--", rel],
            cwd=root, stderr=subprocess.DEVNULL, timeout=5)
    except Exception:
        return None
    value = out.decode("utf-8", "replace").strip()
    return int(value) if value.isdigit() else None


def derive_active(root):
    """The most recently committed blueprint, when there is no local pointer.

    `.buildcli/active` is gitignored on purpose — it is per-machine and per-branch,
    and committing it would make every merge fight over it. That leaves a fresh
    clone with blueprints but no pointer, which is what this recovers. Git history
    is the signal, so a blueprint that exists only in the working tree is not a
    candidate: it has no commit to be recent.

    Resolution only. Nothing is written — the pointer is still moved solely by
    `bcx active <path>` and the `focus` skill.
    """
    if root in _DERIVED_CACHE:
        return _DERIVED_CACHE[root]
    best, best_ts = None, None
    for rel in blueprint_dirs(root):
        ts = _last_commit_ts(root, rel)
        if ts is None:
            continue
        if best_ts is None or ts > best_ts:
            best, best_ts = rel, ts
    _DERIVED_CACHE[root] = best
    return best


def active_with_source(root):
    """(path, source) — source is 'pointer', 'derived', or None when there is neither."""
    try:
        value = paths.read_text(paths.active_path(root)).strip()
    except Exception:
        value = ""
    if value:
        return value, "pointer"
    derived = derive_active(root)
    if derived:
        return derived, "derived"
    return None, None


def get_active(root):
    return active_with_source(root)[0]


def require_active(root):
    active = get_active(root)
    if not active:
        raise paths.ProjectError(
            "no active blueprint.\nRun the `brief` skill, or `bcx active <path>`."
        )
    full = os.path.join(root, active)
    if not os.path.isdir(full):
        raise paths.ProjectError(
            "active blueprint points at a missing directory: %s" % active
        )
    return active


def set_active(root, rel):
    rel = rel.strip().rstrip("/")
    full = os.path.join(root, rel)
    if not os.path.isfile(os.path.join(full, "brief.md")):
        raise paths.ProjectError(
            "%s has no brief.md — not a blueprint directory." % rel
        )
    paths.write_text(paths.active_path(root), rel + "\n")
    _DERIVED_CACHE.pop(root, None)
    return rel


def resolve(root, token):
    """Accept a full path or a bare slug, and find the blueprint it names."""
    token = token.strip().rstrip("/")
    candidates = []
    if os.path.isdir(os.path.join(root, token)):
        candidates.append(token)
    for kind in KINDS:
        cand = os.path.join("blueprints", kind, token)
        if os.path.isdir(os.path.join(root, cand)):
            candidates.append(cand)

    uniq = list(dict.fromkeys(candidates))
    if not uniq:
        raise paths.ProjectError("no blueprint matches '%s'." % token)
    if len(uniq) > 1:
        raise paths.ProjectError(
            "'%s' is ambiguous:\n  %s\nPass the full path." % (token, "\n  ".join(uniq))
        )
    return uniq[0]


def stage_of(root, rel):
    """Furthest stage with a file on disk."""
    full = os.path.join(root, rel)
    stage = "none"
    for name, filename in STAGE_FILES:
        if os.path.isfile(os.path.join(full, filename)):
            stage = name
    return stage


def stages_present(root, rel):
    full = os.path.join(root, rel)
    return {name: os.path.isfile(os.path.join(full, filename))
            for name, filename in STAGE_FILES}


def list_blueprints(root):
    out = []
    active = get_active(root)
    for rel in blueprint_dirs(root):
        kind, slug = rel.split(os.sep)[1], os.path.basename(rel)
        out.append({
            "path": rel,
            "kind": kind,
            "slug": slug,
            "stage": stage_of(root, rel),
            "stages": stages_present(root, rel),
            "active": rel == active,
        })
    return out


def parse_journal_line(line):
    """Split one journal line into (stamp, kind, detail). None when it is not one."""
    parts = line.rstrip("\n").split(" | ", 2)
    if len(parts) != 3:
        return None
    return {"stamp": parts[0].strip(), "kind": parts[1].strip(), "detail": parts[2].strip()}


def journal_entries(root):
    """Every parsed entry in the current log, oldest first. [] when there is none."""
    try:
        text = paths.read_text(paths.journal_path(root))
    except Exception:
        return []
    out = []
    for line in text.splitlines():
        entry = parse_journal_line(line)
        if entry:
            out.append(entry)
    return out


def journal_tail(root, count=5):
    """The last `count` entries, oldest first."""
    if count <= 0:
        return []
    return journal_entries(root)[-count:]


def journal_since_stop(root):
    """Every entry after the most recent STOP — one session's worth of activity."""
    entries = journal_entries(root)
    for i in range(len(entries) - 1, -1, -1):
        if entries[i]["kind"] == "STOP":
            return entries[i + 1:]
    return entries


def _rotate(root, path):
    """Move the log aside once it passes the cap. One generation is kept.

    The journal is a resume aid, not an archive — `session.1.log` is overwritten
    rather than shifted down a chain. A failed rename is swallowed so the append
    that triggered it still happens.
    """
    cap_kb = paths.settings(root).get("journal_max_kb", 0)
    try:
        cap = int(cap_kb) * 1024
    except (TypeError, ValueError):
        return
    if cap <= 0:
        return
    try:
        if os.path.getsize(path) < cap:
            return
        os.replace(path, paths.journal_prev_path(root))
    except Exception:
        pass


def journal(root, kind, detail):
    """Append one line to the audit journal. Never raises — logging must not break a run."""
    try:
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = "%s | %-6s | %s\n" % (stamp, kind.upper()[:6], detail)
        path = paths.journal_path(root)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        _rotate(root, path)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line)
    except Exception:
        pass
