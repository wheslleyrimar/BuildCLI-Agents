"""Shell command lines, read just well enough for the gates to judge them.

Best-effort on purpose. The gates fail open, so a line this cannot take apart is
a line nobody is held to — never a reason to block.
"""

import os
import re
import shlex

# Words that run the command after them rather than being the command.
_PREFIXES = {"sudo", "env", "command", "time", "nice", "nohup", "exec", "builtin"}
_SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}
_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_PYTHON = re.compile(r"^python[\d.]*$")
_PUNCT = set("<>&|;()")
# `<<EOF`, `<<-'EOF'` — but not the `<<<` of a here-string.
_HEREDOC = re.compile(r"(?<!<)<<(?!<)-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
_FALLBACK_SPLIT = re.compile(r"&&|\|\||[;|\n]")
_VARIABLE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)")
_DECLARES = {"export", "local", "readonly", "declare", "typeset"}


def program(word):
    """A program as a name: `.venv/bin/pytest` is pytest, `python3.11` is python."""
    name = word.replace("\\", "/").rsplit("/", 1)[-1]
    return "python" if _PYTHON.match(name) else name


def _strip_heredocs(text):
    """Drop here-document bodies. They are data, and a script written to a file
    through one would otherwise be judged as though it were being run."""
    out, pending = [], []
    for line in text.split("\n"):
        if pending:
            if line.strip() == pending[0]:
                pending.pop(0)
            continue
        out.append(line)
        pending.extend(m.group(2) for m in _HEREDOC.finditer(line))
    return "\n".join(out)


def _tokens(text):
    lex = shlex.shlex(text, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    return list(lex)


def commands(line):
    """Each simple command in a shell line, in order.

    Returns dicts of `words` (leading VAR=value and wrappers like `env` dropped,
    the program reduced by `program()`), `piped` (stdin comes from a pipe),
    `writes` and `reads` (files a redirection opens), and `assigns`. Redirections
    are taken out of `words`. A command that only assigns variables (`d=src`,
    `export D=src`) comes back with empty `words` and its `assigns` filled in.
    `bash -c '...'` is unfolded into the commands it runs.
    """
    if not isinstance(line, str):
        return []
    text = _strip_heredocs(line).replace("\\\n", " ").replace("\n", " ; ")
    try:
        tokens = _tokens(text)
    except ValueError:
        # An unbalanced quote. Fall back to splitting on the obvious operators.
        return [{"words": w, "piped": False, "writes": [], "reads": [], "assigns": {}}
                for w in (_clean(seg.split()) for seg in _FALLBACK_SPLIT.split(line)) if w]

    out, words, writes, reads, piped, redirect = [], [], [], [], False, None
    for tok in tokens:
        if redirect is not None:
            # `>&2` and `>&-` duplicate or close a descriptor; nothing is opened.
            dup = redirect.endswith("&") and (tok.isdigit() or tok == "-")
            if ">" in redirect and not dup:
                writes.append(tok)
            elif redirect == "<":
                reads.append(tok)  # not `<<` (a heredoc delimiter) or `<<<` (data)
            redirect = None
            continue
        if tok and all(c in _PUNCT for c in tok):
            if ("<" in tok or ">" in tok) and "(" not in tok:
                if words and words[-1].isdigit():
                    words.pop()  # the fd number of `2>&1`
                redirect = tok
                continue
            _emit(out, words, piped, writes, reads)
            words, writes, reads, piped = [], [], [], tok in ("|", "|&")
            continue
        words.append(tok)
    _emit(out, words, piped, writes, reads)
    return out


def _assignment(word):
    name, _, value = word.partition("=")
    return name, value


def _emit(out, words, piped, writes, reads):
    rest, assigns = list(words), {}
    while rest and _ASSIGNMENT.match(rest[0]):
        name, value = _assignment(rest.pop(0))
        assigns[name] = value
    if rest and rest[0] in _DECLARES:
        assigns.update(_assignment(w) for w in rest[1:] if _ASSIGNMENT.match(w))
        rest = []
    words = _clean(rest)
    if not words:
        if assigns:
            out.append({"words": [], "piped": piped, "writes": writes, "reads": reads,
                        "assigns": assigns})
        return
    if words[0] in _SHELLS:
        for i, w in enumerate(words[1:-1], 1):
            if w.startswith("-") and not w.startswith("--") and "c" in w:
                out.extend(commands(words[i + 1]))
                return
    # A prefix assignment (`CI=1 npm test`) holds for that command only.
    out.append({"words": words, "piped": piped, "writes": writes, "reads": reads,
                "assigns": {}})


def _clean(words):
    words = list(words)
    while words and (_ASSIGNMENT.match(words[0]) or words[0] in _PREFIXES):
        words.pop(0)
    if words:
        words[0] = program(words[0])
    return words


def segments(line):
    """The words of each simple command — `commands()` without the other keys."""
    return [c["words"] for c in commands(line) if c["words"]]


def _substitute(word, env):
    """`$NAME` and `${NAME}` for variables the line itself set. Others stay as typed."""
    return _VARIABLE.sub(lambda m: env.get(m.group(1) or m.group(2), m.group(0)), word)


def walk(line, cwd):
    """Each command of a line with the directory it runs in.

    Variables the line assigns are substituted into the commands after them, so
    `d=.buildcli; cat $d/context.md` is judged as the path it reads. A `cd` moves
    the directory and is not yielded. One that cannot be followed (`cd -`) ends
    the walk, because nothing after it can be placed.
    """
    env = {}
    for cmd in commands(line):
        if not cmd["words"]:
            env.update((k, _substitute(v, env)) for k, v in cmd["assigns"].items())
            continue
        cmd = dict(cmd, **{key: [_substitute(w, env) for w in cmd[key]]
                           for key in ("words", "writes", "reads")})
        words = cmd["words"]
        if words[0] == "cd":
            target = words[1] if len(words) > 1 else "~"
            if target == "-":
                return
            cwd = os.path.join(cwd, os.path.expanduser(target))
            continue
        yield cmd, cwd
