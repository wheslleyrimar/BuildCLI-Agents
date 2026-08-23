"""The active blueprint pointer, blueprint discovery, and the journal."""

import datetime
import os

from . import paths

KINDS = ("features", "defects")
STAGE_FILES = (("brief", "brief.md"), ("shape", "shape.md"),
               ("worklist", "worklist.md"), ("audit", "audit.md"))


def get_active(root):
    path = paths.active_path(root)
    try:
        value = paths.read_text(path).strip()
    except FileNotFoundError:
        return None
    return value or None


def require_active(root):
    active = get_active(root)
    if not active:
        raise paths.ProjectError(
            "no active blueprint.\nRun the `brief` skill, or `buildcli active <path>`."
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
    for kind in KINDS:
        base = os.path.join(root, "blueprints", kind)
        if not os.path.isdir(base):
            continue
        for slug in sorted(os.listdir(base)):
            rel = os.path.join("blueprints", kind, slug)
            if not os.path.isfile(os.path.join(root, rel, "brief.md")):
                continue
            out.append({
                "path": rel,
                "kind": kind,
                "slug": slug,
                "stage": stage_of(root, rel),
                "stages": stages_present(root, rel),
                "active": rel == active,
            })
    return out


def journal(root, kind, detail):
    """Append one line to the audit journal. Never raises — logging must not break a run."""
    try:
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = "%s | %-6s | %s\n" % (stamp, kind.upper()[:6], detail)
        path = paths.journal_path(root)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line)
    except Exception:
        pass
