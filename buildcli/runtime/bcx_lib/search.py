"""Which shell searches would sweep the context file into their output.

`pre-read` blocks a command that names .buildcli/context.md. A recursive search
run at the project root never names it and still prints every band, so this
module judges a search by its reach instead: the tool, the paths it walks, and
whether anything keeps it out of the state directory.

Judged directly: the grep family, ripgrep, `git grep`, ack, and ag. A search that
prints only file names is no leak on its own, but it can feed one: `find`,
`rg --files`, `fd`, `grep -rl`, and `git ls-files` hand names to `xargs`, and
`find -exec` or `fd -x` hand them to a command. Those are followed too.

It also resolves what a command names: a glob such as `.buildcli/con*`, a
symlink to the file, or a variable set earlier on the line. Anything this cannot
parse is allowed, like every other gate decision.
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

_AG_VALUE_SHORT = set("ABCGgm")
_AG_VALUE_LONG = {"--after", "--before", "--context", "--ignore", "--ignore-dir",
                  "--file-search-regex", "--max-count", "--depth", "--path-to-ignore"}
_ACK_VALUE_SHORT = set("ABCgmt")
_ACK_VALUE_LONG = {"--ignore-dir", "--ignore-directory", "--noignore-dir", "--type",
                   "--max-count", "--after-context", "--before-context", "--context",
                   "--match", "--output"}
_FD_VALUE_SHORT = set("Ecdejt")
_FD_VALUE_LONG = {"--exclude", "--extension", "--type", "--max-depth", "--min-depth",
                  "--changed-within", "--changed-before",
                  "--size", "--owner", "--color", "--threads", "--search-path",
                  "--base-directory", "--path-separator", "--max-results", "--format"}


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


def _reach(root, targets):
    """Whether any target walks into the state directory, or sits inside it."""
    state = _state(root)
    return any(_within(state, t) or _within(t, state) for t in targets)


def _verdict(names, hint, exec_words=None):
    """A search that reaches context.md: does it print names only, or content?"""
    return {"names": names, "hint": hint, "exec": exec_words}


def _grep(root, cwd, words, piped):
    flags, pos = _parse(words[1:], _GREP_VALUE_SHORT, _GREP_VALUE_LONG)
    names = {n for n, _ in flags}
    recursive = names & {"-r", "-R", "--recursive", "--dereference-recursive"} or any(
        n in ("-d", "--directories") and v == "recurse" for n, v in flags)
    if not recursive:
        return None
    if names & {"-c", "-q", "--count", "--quiet", "--silent"}:
        return None  # counts and exit codes carry no band text
    for n, v in flags:
        if n == "--exclude-dir" and v and paths.STATE_DIR in v:
            return None
        if n == "--exclude" and v and paths.CONTEXT in v:
            return None
    includes = [v for n, v in flags if n == "--include" and v]
    if includes and not any(_name_matches(p, paths.CONTEXT) for p in includes):
        return None
    operands = _paths_after_pattern(flags, pos) or ["."]
    if not _reach(root, _targets(cwd, operands)):
        return None
    return _verdict(bool(names & _GREP_NAMES_ONLY), "grep ... --exclude-dir=.buildcli")


def _ignores_reached(root, targets, hidden, ignore_off):
    """ripgrep, ag, and fd skip hidden directories and honour .ignore files."""
    named = any(_within(t, _state(root)) for t in targets)
    if not (hidden or named):
        return False
    return ignore_off or not ignore_covers_context(root)


def _rg(root, cwd, words, piped):
    flags, pos = _parse(words[1:], _RG_VALUE_SHORT, _RG_VALUE_LONG)
    names = [n for n, _ in flags]
    listing = bool(set(names) & {"-l", "--files", "--files-with-matches",
                                 "--files-without-match"})
    if set(names) & (_RG_NAMES_ONLY - {"-l", "--files", "--files-with-matches",
                                       "--files-without-match"}):
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

    # With --files every positional is a path; otherwise the first is the pattern.
    operands = pos if "--files" in names else _paths_after_pattern(flags, pos)
    if not operands:
        if piped and "--files" not in names:
            return None  # ripgrep searches stdin when it is a pipe
        operands = ["."]
    targets = _targets(cwd, operands)
    if not _reach(root, targets):
        return None
    if not _ignores_reached(root, targets, hidden, ignore_off):
        return None
    return _verdict(listing, "rg ... -g '!.buildcli'")


def _ag(root, cwd, words, piped):
    flags, pos = _parse(words[1:], _AG_VALUE_SHORT, _AG_VALUE_LONG)
    names = [n for n, _ in flags]
    if set(names) & {"-c", "--count"}:
        return None
    for n, v in flags:
        if n in ("--ignore", "--ignore-dir") and v and \
                (paths.STATE_DIR in v or paths.CONTEXT in v):
            return None
    unrestricted = "-u" in names or "--unrestricted" in names
    hidden = unrestricted or "--hidden" in names
    operands = pos if "-g" in names else pos[1:]
    if not operands:
        if piped:
            return None
        operands = ["."]
    targets = _targets(cwd, operands)
    if not _reach(root, targets):
        return None
    if not _ignores_reached(root, targets, hidden, unrestricted):
        return None
    listing = bool(set(names) & {"-l", "-L", "-g", "--files-with-matches",
                                 "--files-without-matches"})
    return _verdict(listing, "ag ... --ignore-dir .buildcli")


def _ack(root, cwd, words, piped):
    flags, pos = _parse(words[1:], _ACK_VALUE_SHORT, _ACK_VALUE_LONG)
    names = {n for n, _ in flags}
    if names & {"-c", "--count", "-n", "--no-recurse"}:
        return None
    for n, v in flags:
        if n in ("--ignore-dir", "--ignore-directory") and v and paths.STATE_DIR in v:
            return None
    listing = bool(names & {"-l", "-L", "-f", "-g", "--files-with-matches",
                            "--files-without-matches"})
    operands = pos if names & {"-f", "-g"} else _paths_after_pattern(flags, pos)
    if not operands:
        if piped:
            return None
        operands = ["."]
    if not _reach(root, _targets(cwd, operands)):
        return None
    return _verdict(listing, "ack ... --ignore-dir=.buildcli")


def _git_cmd(root, cwd, words, piped):
    args = words[1:]
    while args and args[0].startswith("-"):
        opt = args.pop(0)
        if opt in _GIT_GLOBAL_VALUE and args:
            val = args.pop(0)
            if opt == "-C":
                cwd = os.path.join(cwd, os.path.expanduser(val))
    if not args or args[0] not in ("grep", "ls-files"):
        return None
    sub = args[0]
    if sub == "grep":
        flags, pos = _parse(args[1:], _GIT_VALUE_SHORT, _GIT_VALUE_LONG)
        specs = _paths_after_pattern(flags, pos)
    else:
        flags, specs = _parse(args[1:], set("x"), {"--exclude", "--exclude-from"})
    names = {n for n, _ in flags}
    if sub == "grep" and names & {"-c", "-q", "--count", "--quiet"}:
        return None
    if any(paths.STATE_DIR in s and (s.startswith(":!") or s.startswith(":^")
                                     or s.startswith(":(exclude)")) for s in specs):
        return None
    operands = [s for s in specs if not s.startswith(":")] or ["."]
    state = _state(root)
    if not any(_within(state, t) or _within(t, state) for t in _targets(cwd, operands)):
        return None
    if sub == "ls-files":
        seen = names & {"-o", "--others"} or _git_sees_context(root, cwd, set())
        return _verdict(True, "git ls-files -- . ':!.buildcli'") if seen else None
    if not _git_sees_context(root, cwd, names):
        return None
    listing = bool(names & {"-l", "-L", "--name-only", "--files-with-matches",
                            "--files-without-match"})
    return _verdict(listing, "git grep ... -- . ':!.buildcli'")


def _find(root, cwd, words, piped):
    args = words[1:]
    while args and args[0] in ("-H", "-L", "-P"):
        args.pop(0)
    i = 0
    while i < len(args) and not (args[i].startswith("-") or args[i] in ("!", "(", ")")):
        i += 1
    scope, expr = args[:i] or ["."], args[i:]
    if any(paths.STATE_DIR in w for w in expr):
        return None  # -prune, -not -path: the state directory is being kept out
    for j, w in enumerate(expr[:-1]):
        if w == "-type" and expr[j + 1] == "d":
            return None  # directories only
    patterns = [expr[j + 1] for j, w in enumerate(expr[:-1]) if w in ("-name", "-iname")]
    if patterns and not any(_name_matches(p, paths.CONTEXT) for p in patterns):
        return None
    if not _reach(root, _targets(cwd, scope)):
        return None
    exec_words = None
    for j, w in enumerate(expr):
        if w in ("-exec", "-execdir", "-ok", "-okdir") and j + 1 < len(expr):
            rest = expr[j + 1:]
            end = next((k for k, x in enumerate(rest) if x in (";", "+")), len(rest))
            exec_words = [shell.program(rest[0])] + rest[1:end]
            break
    return _verdict(exec_words is None, "find ... -path ./.buildcli -prune -o ...", exec_words)


def _fd(root, cwd, words, piped):
    # -x/-X take the rest of the line as the command to run, so split it off first.
    cut = next((i for i, w in enumerate(words)
                if w in ("-x", "--exec", "-X", "--exec-batch")), len(words))
    exec_words = None
    if cut + 1 < len(words):
        rest = words[cut + 1:]
        end = next((i for i, x in enumerate(rest) if x == ";"), len(rest))
        exec_words = [shell.program(rest[0])] + rest[1:end]
    flags, pos = _parse(words[1:cut], _FD_VALUE_SHORT, _FD_VALUE_LONG)
    names = [n for n, _ in flags]
    for n, v in flags:
        if n in ("-E", "--exclude") and v and (paths.STATE_DIR in v or paths.CONTEXT in v):
            return None
        if n in ("-t", "--type") and v and v[0] == "d":
            return None
    exts = [v for n, v in flags if n in ("-e", "--extension") and v]
    if exts and "md" not in [e.lstrip(".") for e in exts]:
        return None
    unrestricted = names.count("-u") + names.count("--unrestricted")
    hidden = "-H" in names or "--hidden" in names or unrestricted >= 1
    ignore_off = "-I" in names or "--no-ignore" in names or unrestricted >= 1
    operands = pos[1:] or ["."]
    targets = _targets(cwd, operands)
    if not _reach(root, targets):
        return None
    if not _ignores_reached(root, targets, hidden, ignore_off):
        return None
    return _verdict(exec_words is None, "fd ... -E .buildcli", exec_words)


JUDGES = {"rg": _rg, "ag": _ag, "ack": _ack, "git": _git_cmd, "find": _find, "fd": _fd}
JUDGES.update({g: _grep for g in GREP})

# Programs that print only names, counts, or nothing at all from the files they get.
_NAME_ONLY = {"ls", "stat", "file", "wc", "du", "echo", "printf", "basename", "dirname",
              "realpath", "readlink", "rm", "chmod", "chown", "touch", "mkdir", "test",
              "[", "true", "md5sum", "sha1sum", "sha256sum", "shasum"}
# Programs that pass a list of names through a pipe without reading the files.
_FILTERS = {"sort", "uniq", "head", "tail", "grep", "egrep", "fgrep", "sed", "awk",
            "tr", "cut", "tac"}
_XARGS_VALUE = {"-I", "-n", "-P", "-L", "-l", "-s", "-d", "-E", "-e", "-a", "--delimiter",
                "--max-args", "--max-procs", "--max-lines", "--max-chars", "--arg-file",
                "--replace", "--eof"}


def _reads(words):
    """Whether a command handed file names would print their contents."""
    if not words or words[0] in _NAME_ONLY:
        return False
    if words[0] in GREP:
        flags, _ = _parse(words[1:], _GREP_VALUE_SHORT, _GREP_VALUE_LONG)
        return not {n for n, _ in flags} & _GREP_NAMES_ONLY
    return True


def _xargs_command(words):
    args, i = words[1:], 0
    while i < len(args) and args[i].startswith("-"):
        i += 2 if args[i] in _XARGS_VALUE else 1
    rest = args[i:]
    return [shell.program(rest[0])] + rest[1:] if rest else ["echo"]


def _refusal(what, hint):
    return ("Blocked: %s reaches .buildcli/ and would print every band of the context "
            "file.\nKeep the state directory out of it:\n    %s\n"
            "Load project context one band at a time:\n"
            "    bcx band <service|interface|store|verify|delivery>" % (what, hint))


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

    `cwd` is where the line runs; `shell.walk` follows any `cd` inside it. A
    names-only search that reaches the file marks the pipe it writes into, and an
    `xargs` downstream that reads what it is handed is refused.
    """
    listing = False
    for cmd, here in shell.walk(line, cwd):
        words = cmd["words"]
        prog = words[0]
        if not cmd["piped"]:
            listing = False
        if prog == "xargs":
            if listing and _reads(_xargs_command(words)):
                return _refusal("this xargs, fed a file list that",
                                "find/rg/fd ... excluding .buildcli, then | xargs ...")
            listing = False
            continue
        if listing and cmd["piped"] and prog in _FILTERS:
            if not any(paths.STATE_DIR in w or paths.CONTEXT in w for w in words[1:]):
                continue  # the names flow on through the filter
        judge = JUDGES.get(prog)
        verdict = judge(root, here, words, cmd["piped"]) if judge else None
        if verdict is None:
            listing = False
            continue
        if verdict["exec"] is not None:
            if _reads(verdict["exec"]):
                return _refusal("this %s, running %s on each file," % (prog, verdict["exec"][0]),
                                verdict["hint"])
            listing = False
        elif verdict["names"]:
            listing = True
        else:
            return _refusal("this %s" % prog, verdict["hint"])
    return None


# git subcommands that take paths and print none of their contents.
_GIT_QUIET = {"add", "rm", "mv", "restore", "checkout", "stash", "commit", "status",
              "ls-files", "check-ignore", "update-index"}


def _git_without_output(words):
    sub = next((w for w in words[1:] if not w.startswith("-")), None)
    return words[0] == "git" and sub in _GIT_QUIET


def aliases_context(root, cwd, line):
    """Whether a command reaches context.md by a name other than its own.

    `cat .buildcli/con*`, `cat notes.md` with notes.md a link to the file, and
    `d=.buildcli; cat $d/context.md` all name it without spelling the path out.
    Programs that only print names or counts are left alone, so `ls .buildcli/*`
    still works.
    """
    ctx = os.path.realpath(paths.context_path(root))
    for cmd, here in shell.walk(line, cwd):
        if cmd["words"][0] in _NAME_ONLY or _git_without_output(cmd["words"]):
            continue
        for word in cmd["words"][1:] + cmd["reads"]:
            for cand in (word, word.partition("=")[2]):
                if cand and ctx in _targets(here, [cand]):
                    return True
    return False
