"""Parsing worklist.md into a dependency graph, and writing unit state back.

The markdown stays the source of truth — a human edits it, and this module reads
and rewrites individual fields in place without disturbing anything else.
"""

import re

from . import paths

UNIT_HEAD = re.compile(r"^###\s+(?P<id>[A-Za-z]\w*)\s+—\s+(?P<name>.+?)\s*$", re.M)
# Accept a plain hyphen too — not everyone types an em dash.
UNIT_HEAD_ALT = re.compile(r"^###\s+(?P<id>[A-Za-z]\w*)\s+-\s+(?P<name>.+?)\s*$", re.M)

# A field runs until the next thing that starts a line at the margin. Its value
# may wrap, and a wrapped `Check:` is normal — a check is supposed to be a
# concrete observation, and those are not always short. A continuation line is an
# indented one that does not itself open a list item or a heading.
#
# The lookahead sits immediately after the newline, spanning the whole indent, so
# that it cannot be stepped around. Written as `[ \t]+(?![-*#])` it would be
# useless: the greedy indent backtracks to one space, the lookahead then reads a
# space rather than the bullet, succeeds, and a nested list item gets swallowed
# into the value above it.
CONTINUATION = r"(?:\n(?![ \t]*[-*#])[ \t]+.*)*"
FIELD = re.compile(
    r"^-[ \t]*(?P<key>[A-Za-z][A-Za-z ]*?)[ \t]*:[ \t]*(?P<val>.*" + CONTINUATION + r")",
    re.M)

STATUSES = ("pending", "in_progress", "done", "blocked")
NONE_TOKENS = ("—", "-", "none", "n/a", "")


class GraphError(Exception):
    pass


def _split_units(text):
    """Yield (id, name, body, span) for each unit block in the file."""
    marks = [(m.start(), m.end(), m.group("id"), m.group("name"))
             for m in UNIT_HEAD.finditer(text)]
    marks += [(m.start(), m.end(), m.group("id"), m.group("name"))
              for m in UNIT_HEAD_ALT.finditer(text)]
    marks.sort()

    for i, (start, end, uid, name) in enumerate(marks):
        stop = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        yield uid, name, text[end:stop], (start, stop)


def _parse_deps(raw):
    raw = raw.strip()
    if raw.lower() in NONE_TOKENS:
        return []
    return [p.strip() for p in re.split(r"[,\s]+", raw) if p.strip() and p.strip() not in ("—", "-")]


def _unwrap(value):
    """Join a wrapped value into one line, leaving its own spacing alone.

    Only the newline-plus-indent that markdown wrapping introduces is collapsed;
    runs of spaces the author typed inside a line survive.
    """
    return re.sub(r"[ \t]*\n[ \t]+", " ", value).strip()


def parse(text):
    """Return the unit list. Order follows the file."""
    units = []
    for uid, name, body, span in _split_units(text):
        fields = {m.group("key").strip().lower(): _unwrap(m.group("val"))
                  for m in FIELD.finditer(body)}
        status = fields.get("status", "pending").strip().lower()
        if status not in STATUSES:
            status = "pending"
        units.append({
            "id": uid,
            "name": name,
            "band": fields.get("band", "").strip().lower() or None,
            "blocked_by": _parse_deps(fields.get("blocked by", "")),
            "parallel": fields.get("parallel", "").strip().lower() in ("yes", "true"),
            "check": fields.get("check", "").strip(),
            "status": status,
            "reason": fields.get("reason", "").strip(),
            "span": span,
        })
    return units


def load(path):
    try:
        text = paths.read_text(path)
    except FileNotFoundError:
        raise paths.ProjectError(
            "%s not found.\nRun the `worklist` skill first." % path
        )
    return text, parse(text)


def validate(units):
    """Structural problems that would otherwise surface as silent misbehavior."""
    problems = []
    ids = [u["id"] for u in units]
    seen = set()
    for uid in ids:
        if uid in seen:
            problems.append("duplicate unit id: %s" % uid)
        seen.add(uid)

    known = set(ids)
    for u in units:
        if not u["band"]:
            problems.append("%s: no band tag" % u["id"])
        elif u["band"] not in paths.BANDS:
            problems.append("%s: unknown band '%s' (expected one of %s)"
                            % (u["id"], u["band"], ", ".join(paths.BANDS)))
        if not u["check"]:
            problems.append("%s: no check — cannot be proven done" % u["id"])
        for dep in u["blocked_by"]:
            if dep not in known:
                problems.append("%s: blocked by unknown unit '%s'" % (u["id"], dep))
            if dep == u["id"]:
                problems.append("%s: blocked by itself" % u["id"])

    for cycle in find_cycles(units):
        problems.append("dependency cycle: %s" % " → ".join(cycle + [cycle[0]]))

    return problems


def find_cycles(units):
    """Every dependency cycle, via iterative DFS with a colour map."""
    graph = {u["id"]: [d for d in u["blocked_by"] if d in {x["id"] for x in units}]
             for u in units}
    WHITE, GREY, BLACK = 0, 1, 2
    colour = {n: WHITE for n in graph}
    cycles = []
    seen_cycles = set()

    for origin in graph:
        if colour[origin] != WHITE:
            continue
        stack = [(origin, iter(graph[origin]))]
        path = [origin]
        colour[origin] = GREY
        while stack:
            node, it = stack[-1]
            advanced = False
            for nxt in it:
                if colour.get(nxt, BLACK) == GREY:
                    idx = path.index(nxt)
                    cyc = path[idx:]
                    key = tuple(sorted(cyc))
                    if key not in seen_cycles:
                        seen_cycles.add(key)
                        cycles.append(cyc)
                elif colour.get(nxt, BLACK) == WHITE:
                    colour[nxt] = GREY
                    path.append(nxt)
                    stack.append((nxt, iter(graph[nxt])))
                    advanced = True
                    break
            if not advanced:
                colour[node] = BLACK
                stack.pop()
                path.pop()
    return cycles


def ready(units):
    """Units that can start now: pending, with every dependency done."""
    done = {u["id"] for u in units if u["status"] == "done"}
    out = []
    for u in units:
        if u["status"] != "pending":
            continue
        if all(dep in done for dep in u["blocked_by"]):
            out.append(u)
    return out


def batches(units):
    """Ready units grouped by band — the parallel fan-out candidates."""
    grouped = {}
    for u in ready(units):
        grouped.setdefault(u["band"] or "unassigned", []).append(u)
    return grouped


def critical_path(units):
    """Longest dependency chain, by unit count."""
    by_id = {u["id"]: u for u in units}
    if find_cycles(units):
        return []
    memo = {}

    def depth(uid, guard):
        if uid in memo:
            return memo[uid]
        if uid in guard:
            return []
        u = by_id.get(uid)
        if not u:
            return []
        best = []
        for dep in u["blocked_by"]:
            cand = depth(dep, guard | {uid})
            if len(cand) > len(best):
                best = cand
        memo[uid] = best + [uid]
        return memo[uid]

    longest = []
    for uid in by_id:
        cand = depth(uid, set())
        if len(cand) > len(longest):
            longest = cand
    return longest


def set_status(path, uid, status, reason=""):
    """Rewrite one unit's Status (and Reason) in place."""
    if status not in STATUSES:
        raise GraphError("invalid status '%s' (use: %s)" % (status, ", ".join(STATUSES)))

    text = paths.read_text(path)
    units = parse(text)
    target = next((u for u in units if u["id"] == uid), None)
    if target is None:
        raise GraphError("unit '%s' not found in %s" % (uid, path))

    start, stop = target["span"]
    block = text[start:stop]

    block = _upsert_field(block, "Status", status)
    if status == "blocked":
        block = _upsert_field(block, "Reason", reason or "no reason given")
    else:
        block = _drop_field(block, "Reason")

    paths.write_text(path, text[:start] + block + text[stop:])
    return target


def _field_pattern(key):
    """Match one field and everything that wraps under it."""
    return re.compile(r"^-[ \t]*%s[ \t]*:.*%s" % (re.escape(key), CONTINUATION),
                      re.M | re.I)


def _last_field_line(lines):
    """Index of the last line belonging to a field, continuations included.

    Not simply the last line that opens with `-`: for a wrapped field that is the
    field's *first* line, and inserting after it lands in the middle of somebody's
    sentence.
    """
    last, in_field = None, False
    for i, line in enumerate(lines):
        if line.lstrip().startswith("-"):
            last, in_field = i, True
        elif in_field and line.strip() and line[:1] in (" ", "\t"):
            last = i          # still inside the field above
        elif line.strip():
            in_field = False  # prose at the margin ends the field list
    return last


def _upsert_field(block, key, value):
    pattern = _field_pattern(key)
    if pattern.search(block):
        # Replacing consumes the old continuations too, so a value that used to
        # wrap does not leave orphaned lines behind.
        return pattern.sub(lambda _: "- %s: %s" % (key, value), block, count=1)

    lines = block.rstrip("\n").split("\n")
    last = _last_field_line(lines)
    insert_at = (last + 1) if last is not None else len(lines)
    lines.insert(insert_at, "- %s: %s" % (key, value))
    return "\n".join(lines) + "\n\n"


def _drop_field(block, key):
    return re.sub(_field_pattern(key).pattern + r"\n?", "", block, flags=re.M | re.I)
