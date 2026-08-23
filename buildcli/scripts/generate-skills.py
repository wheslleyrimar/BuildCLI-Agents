#!/usr/bin/env python3
"""Generate the Claude pipeline skills from their command files.

A pipeline stage is defined once, in `claude/commands/<name>.md`. The matching
`claude/skills/<name>/SKILL.md` is a derived view of that file: same body, a
skill frontmatter instead of a command frontmatter, and slash-prefixed command
references rewritten as bare skill names.

There is deliberately no table of descriptions in here. Each command carries its
own `skill_description` and `skill_title` in frontmatter, because a second copy
of that text is a second thing to forget when something is renamed — which is
exactly how `.prism/` survived a rename once already.

Usage:
    python3 buildcli/scripts/generate-skills.py            # write the skills
    python3 buildcli/scripts/generate-skills.py --check    # verify, write nothing

`--check` exits non-zero when a skill is missing or out of date, so CI catches
drift instead of a reader noticing it months later.
"""

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(HERE)
SRC = os.path.join(KIT, "claude", "commands")
DST = os.path.join(KIT, "claude", "skills")

# Skills authored by hand: band skills, plus specialties that have no command.
NOT_GENERATED = {"service", "interface", "store", "verify", "delivery", "design-review"}

ARGUMENT_FIELD = "arguments"
OUTPUT_FIELD = "output"


class GenerationError(Exception):
    pass


def split_frontmatter(text, path):
    if not text.startswith("---\n"):
        raise GenerationError("%s has no frontmatter" % path)
    try:
        end = text.index("\n---\n", 3)
    except ValueError:
        raise GenerationError("%s has an unterminated frontmatter block" % path)
    return text[4:end + 1], text[end + 5:]


def field(frontmatter, key, path, required=False):
    m = re.search(r"^%s:\s*(.*)$" % re.escape(key), frontmatter, re.M)
    if m:
        return m.group(1).strip()
    if required:
        raise GenerationError("%s is missing the '%s' field" % (path, key))
    return None


def command_names():
    return sorted(f[:-3] for f in os.listdir(SRC) if f.endswith(".md"))


def render(name):
    """Build the SKILL.md text for one command."""
    path = os.path.join(SRC, name + ".md")
    with open(path, encoding="utf-8") as fh:
        frontmatter, body = split_frontmatter(fh.read(), path)

    description = field(frontmatter, "skill_description", path, required=True)
    title = field(frontmatter, "skill_title", path) or name.capitalize()
    arguments = field(frontmatter, ARGUMENT_FIELD, path)
    output = field(frontmatter, OUTPUT_FIELD, path)

    # Drop the command-only "## User Input" / $ARGUMENTS preamble.
    body = re.sub(r"\A\n*## User Input\n\n```text\n\$ARGUMENTS\n```\n\n", "", body)
    body = body.lstrip("\n")

    # A skill is invoked by name, so `/shape` becomes `shape`.
    others = "|".join(command_names())
    body = re.sub(r"`/(%s)`" % others, lambda m: "`%s`" % m.group(1), body)

    parts = ["---", "name: %s" % name, "description: %s" % description, "---", "",
             "# %s" % title, "",
             "## Arguments", "",
             arguments if arguments and arguments.lower() != "none" else "None.", ""]
    if output:
        parts += ["## Output", "", output.rstrip(".") + ".", ""]

    text = "\n".join(parts) + body
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text if text.endswith("\n") else text + "\n"


def target_path(name):
    return os.path.join(DST, name, "SKILL.md")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="verify the skills match their commands; write nothing")
    args = ap.parse_args(argv)

    stale, written = [], []
    for name in command_names():
        try:
            want = render(name)
        except GenerationError as exc:
            sys.stderr.write("error: %s\n" % exc)
            return 2

        dest = target_path(name)
        have = None
        if os.path.isfile(dest):
            with open(dest, encoding="utf-8") as fh:
                have = fh.read()

        if have == want:
            continue
        if args.check:
            stale.append("%s (%s)" % (name, "missing" if have is None else "out of date"))
        else:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "w", encoding="utf-8") as fh:
                fh.write(want)
            written.append(name)

    # A skill with no command and no hand-authored exemption is an orphan.
    generated = set(command_names())
    orphans = sorted(
        d for d in os.listdir(DST)
        if os.path.isdir(os.path.join(DST, d))
        and d not in generated and d not in NOT_GENERATED
    )

    if args.check:
        if stale or orphans:
            for s in stale:
                sys.stderr.write("out of sync: %s\n" % s)
            for o in orphans:
                sys.stderr.write("orphan skill (no command, not hand-authored): %s\n" % o)
            sys.stderr.write("\nRun: python3 buildcli/scripts/generate-skills.py\n")
            return 1
        print("skills are in sync with their commands (%d checked)" % len(generated))
        return 0

    for name in written:
        print("  wrote %s" % os.path.relpath(target_path(name), KIT))
    if not written:
        print("  already up to date (%d skills)" % len(generated))
    for o in orphans:
        sys.stderr.write("warning: orphan skill %s\n" % o)
    return 0


if __name__ == "__main__":
    sys.exit(main())
