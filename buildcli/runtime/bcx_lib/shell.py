"""Shell command lines, read just well enough for the gates to judge them.

Best-effort on purpose. The gates fail open, so a line this cannot take apart is
a line nobody is held to — never a reason to block.
"""

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
    the program reduced by `program()`) and `piped` (stdin comes from a pipe).
    Redirections are removed with their targets. `bash -c '...'` is unfolded into
    the commands it runs.
    """
    if not isinstance(line, str):
        return []
    text = _strip_heredocs(line).replace("\\\n", " ").replace("\n", " ; ")
    try:
        tokens = _tokens(text)
    except ValueError:
        # An unbalanced quote. Fall back to splitting on the obvious operators.
        return [{"words": w, "piped": False}
                for w in (_clean(seg.split()) for seg in _FALLBACK_SPLIT.split(line)) if w]

    out, words, piped, skip = [], [], False, False
    for tok in tokens:
        if skip:
            skip = False
            continue
        if tok and all(c in _PUNCT for c in tok):
            if "<" in tok or ">" in tok:
                if words and words[-1].isdigit():
                    words.pop()  # the fd number of `2>&1`
                skip = True
                continue
            _emit(out, words, piped)
            words, piped = [], tok in ("|", "|&")
            continue
        words.append(tok)
    _emit(out, words, piped)
    return out


def _emit(out, words, piped):
    words = _clean(words)
    if not words:
        return
    if words[0] in _SHELLS:
        for i, w in enumerate(words[1:-1], 1):
            if w.startswith("-") and not w.startswith("--") and "c" in w:
                out.extend(commands(words[i + 1]))
                return
    out.append({"words": words, "piped": piped})


def _clean(words):
    words = list(words)
    while words and (_ASSIGNMENT.match(words[0]) or words[0] in _PREFIXES):
        words.pop(0)
    if words:
        words[0] = program(words[0])
    return words


def segments(line):
    """The words of each simple command — `commands()` without the pipe flag."""
    return [c["words"] for c in commands(line)]
