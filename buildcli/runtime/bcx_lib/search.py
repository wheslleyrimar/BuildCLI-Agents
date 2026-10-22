"""Which shell searches would sweep the context file into their output.

`pre-read` blocks a command that names .buildcli/context.md. A recursive search
run at the project root never names it and still prints every band, so this
module judges a search by its reach instead: the tool, the paths it walks, and
whether anything keeps it out of the state directory.

Three tools are judged — the grep family, ripgrep, and `git grep`. A search that
only prints file names or counts is never a leak. Anything this cannot parse is
allowed, like every other gate decision.
"""

import glob
import os
import re
import subprocess

from . import paths, shell

GREP = {"grep", "egrep", "fgrep", "ggrep"}

_GREP_VALUE_SHORT = set("ABCDdefm")
_GREP_VALUE_LONG = {
    "--regexp", "--file", "--max-count", "--after-context", "--before-context",
    "--context", "--include", "--exclude", "--exclude-dir", "--exclude-from",
    "--label", "--binary-files", "--devices", "--directories", "--group-separator",
}
_GREP_NAMES_ONLY = {"-l", "-L", "-c", "-q", "--files-with-matches",
                    "--files-without-match", "--count", "--quiet", "--silent"}

_RG_VALUE_SHORT = set("ABCEMTdefgjmrt")
_RG_VALUE_LONG = {
    "--after-context", "--before-context", "--context", "--encoding", "--max-columns",
    "--type-not", "--max-depth", "--regexp", "--file", "--glob", "--iglob", "--threads",
    "--max-count", "--replace", "--type", "--type-add", "--type-clear", "--sort",
    "--sortr", "--pre", "--pre-glob", "--path-separator", "--color", "--colors",
    "--engine", "--max-filesize", "--ignore-file", "--context-separator",
    "--field-match-separator", "--field-context-separator", "--dfa-size-limit",
    "--regex-size-limit", "--hostname-bin", "--hyperlink-format", "--generate",
}
_RG_NAMES_ONLY = {"-l", "-c", "-q", "--files", "--files-with-matches",
                  "--files-without-match", "--count", "--count-matches", "--quiet",
                  "--type-list"}
_RG_MD_TYPES = {"md", "markdown", "all"}

_GIT_VALUE_SHORT = set("ABCefm")
_GIT_VALUE_LONG = {"--max-depth", "--threads", "--after-context", "--before-context",
                   "--context", "--max-count"}
_GIT_NAMES_ONLY = {"-l", "-L", "-c", "-q", "--name-only", "--files-with-matches",
                   "--files-without-match", "--count", "--quiet"}
_GIT_GLOBAL_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}


def ignore_path(root):
    return os.path.join(root, paths.STATE_DIR, ".ignore")


def ignore_covers_context(root):
    """Whether .buildcli/.ignore keeps ripgrep-based search out of context.md."""
    try:
        lines = paths.read_text(ignore_path(root)).splitlines()
    except Exception:
        return False
    return any(l.strip() in (paths.CONTEXT, "/" + paths.CONTEXT) for l in lines)


def _parse(args, value_short, value_long):
    """Split a search's arguments into (flags, positionals). Flags keep their values."""
    flags, pos, i = [], [], 0
    while i < len(args):
        a = args[i]
        if a == "--":
            pos.extend(args[i + 1:])
            break
        if a.startswith("--"):
            name, eq, val = a.partition("=")
            if not eq and name in value_long and i + 1 < len(args):
                flags.append((name, args[i + 1]))
                i += 2
                continue
            flags.append((name, val if eq else None))
        elif a.startswith("-") and len(a) > 1:
            body = a[1:]
            for j, c in enumerate(body):
                if c in value_short:
                    val = body[j + 1:]
                    if not val and i + 1 < len(args):
                        i += 1
                        val = args[i]
                    flags.append(("-" + c, val))
                    break
                flags.append(("-" + c, None))
        else:
            pos.append(a)
        i += 1
    return flags, pos


def _paths_after_pattern(flags, pos):
    """Positionals that are paths: all of them when -e/-f gave the pattern."""
    explicit = any(n in ("-e", "-f", "--regexp", "--file") for n, _ in flags)
    return pos if explicit else pos[1:]


def _within(child, parent):
    try:
        return os.path.commonpath([child, parent]) == parent
    except ValueError:
        return False


def _targets(cwd, operands):
    """Real paths the operands name, with globs expanded the way a shell would."""
    out = []
    for op in operands:
        full = os.path.join(cwd, os.path.expanduser(op))
        if any(c in op for c in "*?["):
            out.extend(os.path.realpath(p) for p in glob.glob(full))
        else:
            out.append(os.path.realpath(full))
    return out


def _state(root):
    return os.path.realpath(os.path.join(root, paths.STATE_DIR))


def _name_matches(pattern, name):
    rx = "".join(".*" if c == "*" else "." if c == "?" else re.escape(c) for c in pattern)
    return re.match("^" + rx + "$", name) is not None


def _grep(root, cwd, words, piped):
    flags, pos = _parse(words[1:], _GREP_VALUE_SHORT, _GREP_VALUE_LONG)
    names = {n for n, _ in flags}
    recursive = names & {"-r", "-R", "--recursive", "--dereference-recursive"} or any(
        n in ("-d", "--directories") and v == "recurse" for n, v in flags)
    if not recursive:
        return None
    if names & _GREP_NAMES_ONLY:
        return None
    for n, v in flags:
        if n == "--exclude-dir" and v and paths.STATE_DIR in v:
            return None
        if n == "--exclude" and v and paths.CONTEXT in v:
            return None
    includes = [v for n, v in flags if n == "--include" and v]
    if includes and not any(_name_matches(p, paths.CONTEXT) for p in includes):
        return None
    operands = _paths_after_pattern(flags, pos) or ["."]
    state = _state(root)
    if not any(_within(state, t) for t in _targets(cwd, operands)):
        return None
    return ("Blocked: this recursive grep reaches .buildcli/ and would print every band "
            "of the context file.\nExclude the state directory:\n"
            "    grep ... --exclude-dir=.buildcli\n"
            "Load project context one band at a time:\n"
            "    bcx band <service|interface|store|verify|delivery>")


def _rg(root, cwd, words, piped):
    flags, pos = _parse(words[1:], _RG_VALUE_SHORT, _RG_VALUE_LONG)
    names = [n for n, _ in flags]
    if set(names) & _RG_NAMES_ONLY:
        return None
    for n, v in flags:
        if n in ("-g", "--glob", "--iglob") and v and v.startswith("!") and \
                (paths.STATE_DIR in v or paths.CONTEXT in v):
            return None
    types = [v for n, v in flags if n in ("-t", "--type") and v]
    if types and not set(types) & _RG_MD_TYPES:
        return None
    globs = [v for n, v in flags if n in ("-g", "--glob", "--iglob")
             and v and not v.startswith("!")]
    if globs and not any(_name_matches(g.rsplit("/", 1)[-1], paths.CONTEXT) for g in globs):
        return None

    unrestricted = names.count("-u") + names.count("--unrestricted")
    hidden = "--hidden" in names or "-." in names or unrestricted >= 2
    ignore_off = unrestricted >= 1 or "--no-ignore" in names or "--no-ignore-dot" in names

    operands = _paths_after_pattern(flags, pos)
    if not operands:
        if piped:
            return None  # ripgrep searches stdin when it is a pipe
        operands = ["."]
    state = _state(root)
    targets = _targets(cwd, operands)
    if not any(_within(state, t) or _within(t, state) for t in targets):
        return None
    # A hidden directory is walked only with --hidden, or when named outright.
    named = any(_within(t, state) for t in targets)
    if not (hidden or named):
        return None
    if not ignore_off and ignore_covers_context(root):
        return None
    return ("Blocked: this ripgrep search would read .buildcli/context.md and print every "
            "band.\nDrop the flag that disables ignore files, or exclude the state "
            "directory:\n"
            "    rg ... -g '!.buildcli'\n"
            "Load project context one band at a time:\n"
            "    bcx band <service|interface|store|verify|delivery>")


def _git_grep(root, cwd, words, piped):
    args = words[1:]
    while args and args[0].startswith("-"):
        opt = args.pop(0)
        if opt in _GIT_GLOBAL_VALUE and args:
            val = args.pop(0)
            if opt == "-C":
                cwd = os.path.join(cwd, os.path.expanduser(val))
    if not args or args[0] != "grep":
        return None
    flags, pos = _parse(args[1:], _GIT_VALUE_SHORT, _GIT_VALUE_LONG)
    names = {n for n, _ in flags}
    if names & _GIT_NAMES_ONLY:
        return None
    specs = _paths_after_pattern(flags, pos)
    if any(paths.STATE_DIR in s and (s.startswith(":!") or s.startswith(":^")
                                     or s.startswith(":(exclude)")) for s in specs):
        return None
    operands = [s for s in specs if not s.startswith(":")] or ["."]
    state = _state(root)
    if not any(_within(state, t) for t in _targets(cwd, operands)):
        return None
    if not _git_sees_context(root, cwd, names):
        return None
    return ("Blocked: this git grep covers .buildcli/ and would print every band of the "
            "context file.\nExclude the state directory with a pathspec:\n"
            "    git grep ... -- . ':!.buildcli'\n"
            "Load project context one band at a time:\n"
            "    bcx band <service|interface|store|verify|delivery>")


def _git(cwd, *args):
    """A git exit code, or None when git could not be asked."""
    try:
        return subprocess.run(["git", "-C", cwd] + list(args), stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, timeout=5).returncode
    except Exception:
        return None


def _git_sees_context(root, cwd, names):
    """Whether git grep would search context.md at all.

    It reads tracked files only, unless --untracked adds files .gitignore does not
    exclude, or --no-index drops git out of it. A project that keeps .buildcli/
    out of git is safe from a plain `git grep`, and blocking it there would be
    friction with nothing behind it. When git cannot be asked, allow.
    """
    if "--no-index" in names:
        return True
    ctx = paths.context_path(root)
    tracked = _git(cwd, "ls-files", "--error-unmatch", "--", ctx)
    if tracked is None:
        return False
    if tracked == 0:
        return True
    if "--untracked" not in names:
        return False
    if "--no-exclude-standard" in names:
        return True
    return _git(cwd, "check-ignore", "-q", "--", ctx) != 0


def leak(root, cwd, line):
    """The refusal for a search in `line` that would print context.md, or None.

    `cwd` is where the line runs. A `cd` inside it moves that; one that cannot be
    followed ends the judgment, because nothing after it can be placed.
    """
    for cmd in shell.commands(line):
        words = cmd["words"]
        if words[0] == "cd":
            target = words[1] if len(words) > 1 else "~"
            if target == "-":
                return None
            cwd = os.path.join(cwd, os.path.expanduser(target))
            continue
        if words[0] in GREP:
            judge = _grep
        elif words[0] == "rg":
            judge = _rg
        elif words[0] == "git":
            judge = _git_grep
        else:
            continue
        message = judge(root, cwd, words, cmd["piped"])
        if message:
            return message
    return None
