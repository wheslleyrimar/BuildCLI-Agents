"""Which files a shell line writes, so the write gate can judge Bash like an edit tool.

Covered: output redirections, `tee`, `sed -i`, `perl -i`, `cp`, `mv` (both
ends — a move deletes its source), `install`, `ln`, `rm`, `unlink`, `touch`,
`truncate`, and `dd of=`. A program that writes from inside an interpreter or a
script is not seen. Like every gate input, this is best-effort, and a line it
cannot take apart yields nothing to judge.
"""

import glob
import os

from . import shell

_COPY_VALUE = {"-t", "-S", "-m", "-o", "-g", "--suffix", "--mode", "--owner", "--group",
               "--target-directory"}
_TRUNCATE_VALUE = {"-s", "-r", "--size", "--reference"}


def _positionals(args, value_flags=()):
    pos, i = [], 0
    while i < len(args):
        a = args[i]
        if a == "--":
            pos.extend(args[i + 1:])
            break
        if a.startswith("-") and len(a) > 1:
            if a in value_flags:
                i += 1
        else:
            pos.append(a)
        i += 1
    return pos


def _expand(cwd, word):
    """Absolute paths for one word, globs expanded the way a shell would.

    A directory comes back with a trailing separator, so a band pattern such as
    `src/api/**` can claim the directory itself.
    """
    full = os.path.join(cwd, os.path.expanduser(word))
    found = glob.glob(full) if any(c in word for c in "*?[") else []
    out = found or [full]
    return [p + os.sep if os.path.isdir(p) and not p.endswith(os.sep) else p for p in out]


def _copy_like(prog, args, cwd):
    target_dir = None
    for i, a in enumerate(args):
        if a == "-t" and i + 1 < len(args):
            target_dir = args[i + 1]
        elif a.startswith("--target-directory="):
            target_dir = a.split("=", 1)[1]
    pos = _positionals(args, _COPY_VALUE)
    if target_dir is not None:
        srcs, dest = pos, target_dir
    elif len(pos) >= 2:
        srcs, dest = pos[:-1], pos[-1]
    else:
        return []
    sources = [p for s in srcs for p in _expand(cwd, s)]
    dest_full = os.path.join(cwd, os.path.expanduser(dest))
    if target_dir is not None or os.path.isdir(dest_full) or len(sources) > 1:
        out = [os.path.join(dest_full, os.path.basename(s.rstrip(os.sep))) for s in sources]
    else:
        out = [dest_full]
    if prog == "mv":
        out.extend(sources)
    return out


def _sed(args):
    """Files `sed` rewrites in place; [] unless -i or --in-place is given."""
    in_place, script_given, pos, i = False, False, [], 0
    while i < len(args):
        a = args[i]
        if a == "--":
            pos.extend(args[i + 1:])
            break
        if a in ("-e", "-f", "--expression", "--file"):
            script_given = True
            i += 2
            continue
        if a.startswith(("--expression=", "--file=")):
            script_given = True
        elif a.startswith("--in-place"):
            in_place = True
        elif a.startswith("-") and len(a) > 1 and not a.startswith("--"):
            body = a[1:]
            if "i" in body:
                in_place = True
                # BSD sed takes the backup suffix as its own word: `-i ''`, `-i .bak`.
                nxt = args[i + 1] if i + 1 < len(args) else None
                if body == "i" and nxt is not None and \
                        (nxt == "" or (nxt.startswith(".") and "/" not in nxt)):
                    i += 1
            if body[-1] in "ef":
                script_given = True
                i += 2
                continue
        else:
            pos.append(a)
        i += 1
    if not in_place:
        return []
    return pos if script_given else pos[1:]


def _perl(args):
    """Files `perl -i` rewrites in place."""
    in_place, script_given, pos, i = False, False, [], 0
    while i < len(args):
        a = args[i]
        if a.startswith("-") and len(a) > 1 and not a.startswith("--"):
            body = a[1:]
            if "i" in body:
                in_place = True
            if body[-1] in "eE":
                script_given = True
                i += 2
                continue
        else:
            pos.append(a)
        i += 1
    if not in_place:
        return []
    return pos if script_given else pos[1:]


def targets(line, cwd):
    """Absolute paths the line would create, change, or delete."""
    out = []
    for cmd, here in shell.walk(line, cwd):
        for w in cmd["writes"]:
            out.extend(_expand(here, w))
        prog, args = cmd["words"][0], cmd["words"][1:]
        if prog in ("tee", "rm", "unlink", "touch"):
            words = _positionals(args)
        elif prog == "truncate":
            words = _positionals(args, _TRUNCATE_VALUE)
        elif prog == "dd":
            words = [a[3:] for a in args if a.startswith("of=")]
        elif prog == "sed":
            words = _sed(args)
        elif prog == "perl":
            words = _perl(args)
        elif prog in ("cp", "mv", "install", "ln"):
            out.extend(_copy_like(prog, args, here))
            continue
        else:
            continue
        for w in words:
            out.extend(_expand(here, w))
    return out
