"""The `bcx shim` command.

The runtime is project-local by design: the agent invokes it as
`.buildcli/runtime/bcx`, which cannot be shadowed and does not depend on the
PATH of whoever cloned the repository. That is right for the agent and tedious
for a human at a prompt, so this installs a small dispatcher that walks up from
the working directory and execs whichever project runtime it lands in.
"""

import os
import stat

SHIM = r'''#!/usr/bin/env bash
# bcx — dispatcher for the project-local BuildCLI Agents runtime.
# Installed by `bcx shim --install`. Walks up from the working directory and
# runs the runtime belonging to whichever project you are standing in.

set -euo pipefail

dir="$PWD"
while :; do
  if [ -x "$dir/.buildcli/runtime/bcx" ]; then
    exec "$dir/.buildcli/runtime/bcx" "$@"
  fi
  parent="$(dirname "$dir")"
  [ "$parent" = "$dir" ] && break
  dir="$parent"
done

echo "bcx: no .buildcli/runtime/bcx in this directory or any parent." >&2
echo "     Run the BuildCLI Agents bootstrap in your project first." >&2
exit 1
'''

DEFAULT_DIR = "~/bin"


def _on_path(directory):
    real = os.path.realpath(directory)
    return any(os.path.realpath(p) == real
               for p in os.environ.get("PATH", "").split(os.pathsep) if p)


def _shadowed_by():
    """Anything already named bcx that would win on PATH."""
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if not entry:
            continue
        cand = os.path.join(entry, "bcx")
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    return None


def render():
    return SHIM


def install(target_dir=None, force=False):
    """Write the shim. Returns (path, list of notes for the user)."""
    notes = []
    directory = os.path.expanduser(target_dir or DEFAULT_DIR)
    path = os.path.join(directory, "bcx")

    existing = _shadowed_by()
    if existing and os.path.realpath(existing) != os.path.realpath(path):
        notes.append("another 'bcx' is already on PATH at %s and would win; "
                     "remove it or install elsewhere" % existing)

    if os.path.exists(path) and not force:
        current = ""
        try:
            with open(path, "r", encoding="utf-8") as fh:
                current = fh.read()
        except Exception:
            pass
        if current.strip() == SHIM.strip():
            return path, ["already installed and up to date"]
        raise RuntimeError(
            "%s exists and is not this shim. Inspect it, then re-run with --force "
            "to replace it." % path)

    os.makedirs(directory, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(SHIM)
    os.chmod(tmp, os.stat(tmp).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    os.replace(tmp, path)

    if not _on_path(directory):
        notes.append("%s is not on your PATH — add it, or the shim will not be found"
                     % directory)

    return path, notes
