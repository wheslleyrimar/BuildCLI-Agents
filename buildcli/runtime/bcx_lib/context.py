"""Deterministic band extraction from .buildcli/context.md.

This is the piece that turns the band rule from a prompt convention into a
mechanism: the caller names one band and receives exactly that block. There is
no path through this module that returns the whole file.
"""

import re

from . import paths

HEADING = re.compile(r"^##\s+\[band:([a-z0-9_-]+)\]\s*$", re.M)
ANY_H2 = re.compile(r"^##\s+", re.M)

# A band whose every field still reads like the template carries no information.
EMPTY_MARKERS = ("N/A — not detected", "N/A - not detected", "NEEDS CLARIFICATION")


def _load(root):
    path = paths.context_path(root)
    try:
        return paths.read_text(path), path
    except FileNotFoundError:
        raise paths.ProjectError(
            "%s not found.\nRun the `survey` skill to generate it." % path
        )


def band_names(root):
    """Every band declared in context.md, in file order."""
    text, _ = _load(root)
    return [m.group(1) for m in HEADING.finditer(text)]


def extract(root, name):
    """Return the text of one band: its heading plus everything up to the next H2."""
    text, path = _load(root)

    start = None
    for m in HEADING.finditer(text):
        if m.group(1) == name:
            start = m
            break

    if start is None:
        declared = band_names(root)
        raise paths.ProjectError(
            "band '%s' is not declared in %s.\nDeclared bands: %s"
            % (name, path, ", ".join(declared) or "(none)")
        )

    tail = text[start.end():]
    nxt = ANY_H2.search(tail)
    body = tail[: nxt.start()] if nxt else tail
    return (text[start.start(): start.end()] + body).rstrip() + "\n"


def header(root):
    """The shared header: everything before the first band heading.

    `brief` needs Metadata / Stack / Architecture and must not see the bands.
    """
    text, _ = _load(root)
    m = HEADING.search(text)
    return (text[: m.start()] if m else text).rstrip() + "\n"


def is_populated(body):
    """True when a band carries at least one field with a real value."""
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith("-"):
            continue
        value = line.lstrip("- ").split(":", 1)
        if len(value) != 2:
            continue
        v = value[1].strip()
        if not v:
            continue
        if any(marker in v for marker in EMPTY_MARKERS):
            continue
        return True
    return False


def survey_report(root):
    """Per-band population status, for `doctor` and `bands`."""
    out = []
    for name in band_names(root):
        body = extract(root, name)
        out.append({"band": name, "populated": is_populated(body),
                    "words": len(body.split())})
    return out
