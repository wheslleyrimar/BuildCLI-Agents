"""Locating the project root and the files the runtime owns."""

import os

STATE_DIR = ".buildcli"
CONTEXT = "context.md"
ACTIVE = "active"
BANDS_MAP = "bands.json"
JOURNAL = os.path.join("journal", "session.log")

BANDS = ("service", "interface", "store", "verify", "delivery")


class ProjectError(Exception):
    """Raised when the runtime cannot operate on the current directory."""


def find_root(start=None):
    """Walk upward looking for a .buildcli/ directory.

    Returns the project root. Raises ProjectError when there is none, so every
    command fails with the same actionable message instead of a stack trace.
    """
    cur = os.path.abspath(start or os.getcwd())
    while True:
        if os.path.isdir(os.path.join(cur, STATE_DIR)):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            raise ProjectError(
                "no .buildcli/ found in this directory or any parent.\n"
                "Run the bootstrap script from your project root first."
            )
        cur = parent


def state_dir(root):
    return os.path.join(root, STATE_DIR)


def context_path(root):
    return os.path.join(root, STATE_DIR, CONTEXT)


def active_path(root):
    return os.path.join(root, STATE_DIR, ACTIVE)


def bands_map_path(root):
    return os.path.join(root, STATE_DIR, BANDS_MAP)


def journal_path(root):
    return os.path.join(root, STATE_DIR, JOURNAL)


def read_text(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def write_text(path, text):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, path)
