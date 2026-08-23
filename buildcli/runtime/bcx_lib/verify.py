"""The executable half of verification: actually run the tests.

`audit` reads code and judges coverage. This runs the suite and reports what
happened, so a quality gate can be checked rather than asserted.
"""

import re
import shlex
import subprocess

from . import context, paths, state

# Fields in [band:verify] that plausibly hold a runnable command.
COMMAND_KEYS = ("test command", "unit test framework", "ci gate", "integration test approach")
CMD_IN_BACKTICKS = re.compile(r"`([^`]+)`")


def discover_command(root):
    """Pull the test command out of [band:verify].

    Prefers a value in backticks, which is how the survey skill is told to write
    commands. Returns None when the band names no runnable command.
    """
    try:
        body = context.extract(root, "verify")
    except paths.ProjectError:
        return None

    for line in body.splitlines():
        line = line.strip()
        if not line.startswith("-") or ":" not in line:
            continue
        key, val = line.lstrip("- ").split(":", 1)
        if key.strip().lower() not in COMMAND_KEYS:
            continue
        val = val.strip()
        if not val or "NEEDS CLARIFICATION" in val or val.startswith("N/A"):
            continue
        m = CMD_IN_BACKTICKS.search(val)
        if m:
            return m.group(1).strip()
        # A bare value is only a command if it looks like one.
        if re.match(r"^[\w./-]+(\s+[\w./=@:-]+)*$", val) and " " in val or "/" in val:
            return val
    return None


def run(root, command=None, timeout=900):
    """Run the test command and return a structured result."""
    cmd = command or discover_command(root)
    if not cmd:
        return {
            "ran": False,
            "command": None,
            "passed": None,
            "reason": "no test command found in [band:verify] — "
                      "record one there (in backticks) or pass --command",
        }

    try:
        proc = subprocess.run(
            cmd, shell=True, cwd=root, timeout=timeout,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
    except subprocess.TimeoutExpired:
        state.journal(root, "verify", "TIMEOUT after %ss: %s" % (timeout, cmd))
        return {"ran": True, "command": cmd, "passed": False, "exit": None,
                "output": "", "reason": "timed out after %ss" % timeout}

    output = proc.stdout or ""
    passed = proc.returncode == 0
    state.journal(root, "verify", "%s exit=%d :: %s"
                  % ("PASS" if passed else "FAIL", proc.returncode, cmd))
    return {
        "ran": True,
        "command": cmd,
        "passed": passed,
        "exit": proc.returncode,
        "output": output,
        "reason": None,
    }


def tail(output, lines=40):
    parts = (output or "").rstrip().splitlines()
    if len(parts) <= lines:
        return "\n".join(parts)
    return "\n".join(["... (%d earlier lines omitted)" % (len(parts) - lines)] + parts[-lines:])
