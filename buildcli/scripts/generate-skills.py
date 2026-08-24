#!/usr/bin/env python3
"""Generate pipeline skills from their command files.

A pipeline stage is defined once, in `<agent>/commands/<name>.md`. The matching
`<agent>/skills/<name>/SKILL.md` is a derived view of that file: same body, a
skill frontmatter instead of a command frontmatter, and agent-specific command
references rewritten to the way that agent invokes skills.

There is deliberately no table of descriptions in here. Each command carries its
own `skill_description` and `skill_title` in frontmatter, because a second copy
of that text is a second thing to forget when something is renamed — and one
such copy did once keep a dead path alive through a project-wide rename.

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

# Skills authored by hand: band skills, plus specialties that have no command.
AGENTS = {
    "claude": {
        "src": os.path.join(KIT, "claude", "commands"),
        "dst": os.path.join(KIT, "claude", "skills"),
        "not_generated": {
            "service", "interface", "store", "verify", "delivery", "design-review"
        },
        "require_skill_description": True,
        "command_ref": lambda name: name,
    },
    "codex": {
        "src": os.path.join(KIT, "codex", "commands"),
        "dst": os.path.join(KIT, "codex", "skills"),
        "not_generated": {
            "service", "interface", "store", "verify", "delivery", "code-standard"
        },
        "require_skill_description": False,
        "command_ref": lambda name: "$" + name,
    },
}

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


def command_names(src):
    return sorted(f[:-3] for f in os.listdir(src) if f.endswith(".md"))


def render(agent, name):
    """Build the SKILL.md text for one command."""
    cfg = AGENTS[agent]
    path = os.path.join(cfg["src"], name + ".md")
    with open(path, encoding="utf-8") as fh:
        frontmatter, body = split_frontmatter(fh.read(), path)

    description = field(frontmatter, "skill_description", path,
                        required=cfg["require_skill_description"])
    if not description:
        description = field(frontmatter, "description", path, required=True)
    title = field(frontmatter, "skill_title", path) or name.capitalize()
    arguments = field(frontmatter, ARGUMENT_FIELD, path)
    output = field(frontmatter, OUTPUT_FIELD, path)

    # Drop the command-only "## User Input" / $ARGUMENTS preamble.
    body = re.sub(r"\A\n*## User Input\n\n```text\n\$ARGUMENTS\n```\n\n", "", body)
    body = body.lstrip("\n")

    # Rewrite exact command references to the agent's skill invocation form.
    others = "|".join(command_names(cfg["src"]))
    body = re.sub(r"`/(%s)`" % others,
                  lambda m: "`%s`" % cfg["command_ref"](m.group(1)),
                  body)

    parts = ["---", "name: %s" % name, "description: %s" % description, "---", "",
             "# %s" % title, "",
             "## Arguments", "",
             arguments if arguments and arguments.lower() != "none" else "None.", ""]
    if output:
        parts += ["## Output", "", output.rstrip(".") + ".", ""]

    text = "\n".join(parts) + body
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text if text.endswith("\n") else text + "\n"


def target_path(agent, name):
    return os.path.join(AGENTS[agent]["dst"], name, "SKILL.md")


def selected_agents(name):
    if name == "all":
        return sorted(AGENTS)
    return [name]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="verify the skills match their commands; write nothing")
    ap.add_argument("--agent", choices=sorted(AGENTS) + ["all"], default="all",
                    help="agent tree to generate (default: all)")
    args = ap.parse_args(argv)

    stale, written, orphans = [], [], []
    checked = 0

    for agent in selected_agents(args.agent):
        cfg = AGENTS[agent]
        names = command_names(cfg["src"])
        checked += len(names)

        for name in names:
            try:
                want = render(agent, name)
            except GenerationError as exc:
                sys.stderr.write("error: %s\n" % exc)
                return 2

            dest = target_path(agent, name)
            have = None
            if os.path.isfile(dest):
                with open(dest, encoding="utf-8") as fh:
                    have = fh.read()

            if have == want:
                continue
            label = "%s/%s" % (agent, name)
            if args.check:
                stale.append("%s (%s)" % (label, "missing" if have is None else "out of date"))
            else:
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, "w", encoding="utf-8") as fh:
                    fh.write(want)
                written.append((agent, name))

        # A skill with no command and no hand-authored exemption is an orphan.
        generated = set(names)
        orphans.extend(
            "%s/%s" % (agent, d)
            for d in sorted(os.listdir(cfg["dst"]))
            if os.path.isdir(os.path.join(cfg["dst"], d))
            and d not in generated and d not in cfg["not_generated"]
        )

    if args.check:
        if stale or orphans:
            for s in stale:
                sys.stderr.write("out of sync: %s\n" % s)
            for o in orphans:
                sys.stderr.write("orphan skill (no command, not hand-authored): %s\n" % o)
            sys.stderr.write("\nRun: python3 buildcli/scripts/generate-skills.py\n")
            return 1
        print("skills are in sync with their commands (%d checked)" % checked)
        return 0

    for agent, name in written:
        print("  wrote %s" % os.path.relpath(target_path(agent, name), KIT))
    if not written:
        print("  already up to date (%d skills)" % checked)
    for o in orphans:
        sys.stderr.write("warning: orphan skill %s\n" % o)
    return 0


if __name__ == "__main__":
    sys.exit(main())
