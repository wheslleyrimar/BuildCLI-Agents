"""Regression tests for the buildcli runtime.

Run from the runtime directory:
    python3 -m unittest discover -s tests -q
"""

import datetime
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bcx_lib import (claims, cli, context, gate, paths, resume, shim, state,  # noqa: E402
                     verify, worklist)

CONTEXT = """# Project Context

## Stack

- Languages: Python

## [band:service]

- Framework: FastAPI

## [band:interface]

- Framework + version: N/A — not detected

## [band:verify]

- Unit test framework: `python3 -m unittest -q`
"""

WORKLIST = """## Units

### W01 — Schema
- Band: store
- Blocked by: —
- Check: migration applies

### W02 — Endpoint
- Band: service
- Blocked by: W01
- Check: returns 201
"""

CYCLIC = """## Units

### A1 — one
- Band: service
- Blocked by: A3
- Check: x

### A2 — two
- Band: store
- Blocked by: A1
- Check: x

### A3 — three
- Band: verify
- Blocked by: A2
- Check: x
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, ".buildcli"))
        paths.write_text(paths.context_path(self.root), CONTEXT)
        self.bp = os.path.join("blueprints", "features", "demo")
        os.makedirs(os.path.join(self.root, self.bp))
        paths.write_text(os.path.join(self.root, self.bp, "brief.md"), "# Brief\n")
        self.wl = os.path.join(self.root, self.bp, "worklist.md")
        paths.write_text(self.wl, WORKLIST)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)


class TestContext(Base):
    def test_band_returns_only_that_band(self):
        body = context.extract(self.root, "service")
        self.assertIn("FastAPI", body)
        self.assertNotIn("band:interface", body)
        self.assertNotIn("## Stack", body)

    def test_unknown_band_raises(self):
        with self.assertRaises(paths.ProjectError):
            context.extract(self.root, "backend")

    def test_header_excludes_every_band(self):
        head = context.header(self.root)
        self.assertIn("## Stack", head)
        self.assertNotIn("## [band:", head)

    def test_population_detection(self):
        self.assertTrue(context.is_populated(context.extract(self.root, "service")))
        self.assertFalse(context.is_populated(context.extract(self.root, "interface")))


class TestGraph(Base):
    def test_ready_respects_dependencies(self):
        units = worklist.parse(WORKLIST)
        self.assertEqual([u["id"] for u in worklist.ready(units)], ["W01"])

    def test_completion_unblocks(self):
        worklist.set_status(self.wl, "W01", "done")
        _, units = worklist.load(self.wl)
        self.assertEqual([u["id"] for u in worklist.ready(units)], ["W02"])

    def test_cycle_is_detected(self):
        units = worklist.parse(CYCLIC)
        self.assertTrue(worklist.find_cycles(units))
        self.assertTrue(any("cycle" in p for p in worklist.validate(units)))

    def test_critical_path(self):
        self.assertEqual(worklist.critical_path(worklist.parse(WORKLIST)), ["W01", "W02"])

    def test_validation_catches_bad_band_and_missing_check(self):
        bad = "## Units\n\n### X1 — x\n- Band: nonsense\n- Blocked by: X9\n- Check:\n"
        problems = " ".join(worklist.validate(worklist.parse(bad)))
        self.assertIn("unknown band", problems)
        self.assertIn("no check", problems)
        self.assertIn("unknown unit", problems)

    def test_status_write_is_idempotent(self):
        worklist.set_status(self.wl, "W01", "in_progress")
        worklist.set_status(self.wl, "W01", "done")
        text = paths.read_text(self.wl)
        self.assertEqual(text.count("- Status:"), 1)
        self.assertIn("- Status: done", text)

    def test_block_records_and_clears_reason(self):
        worklist.set_status(self.wl, "W02", "blocked", "waiting")
        self.assertIn("- Reason: waiting", paths.read_text(self.wl))
        worklist.set_status(self.wl, "W02", "pending")
        self.assertNotIn("- Reason:", paths.read_text(self.wl))


class TestState(Base):
    def test_set_and_get_active(self):
        state.set_active(self.root, self.bp)
        self.assertEqual(state.get_active(self.root), self.bp)

    def test_reject_directory_without_brief(self):
        empty = os.path.join("blueprints", "features", "empty")
        os.makedirs(os.path.join(self.root, empty))
        with self.assertRaises(paths.ProjectError):
            state.set_active(self.root, empty)

    def test_resolve_bare_slug(self):
        self.assertEqual(state.resolve(self.root, "demo"), self.bp)


class TestVerify(Base):
    def test_command_discovered_from_band(self):
        self.assertEqual(verify.discover_command(self.root), "python3 -m unittest -q")

    def test_runs_and_reports_failure(self):
        result = verify.run(self.root, command="exit 3")
        self.assertTrue(result["ran"])
        self.assertFalse(result["passed"])
        self.assertEqual(result["exit"], 3)


class TestGate(Base):
    def _event(self, path):
        return {"cwd": self.root, "tool_input": {"file_path": os.path.join(self.root, path)}}

    def _configure(self):
        paths.write_text(paths.bands_map_path(self.root), json.dumps({
            "service": ["src/api/**"], "store": ["migrations/**"],
        }))
        state.set_active(self.root, self.bp)

    def test_context_read_is_blocked(self):
        self.assertEqual(
            gate.pre_read(self.root, self._event(".buildcli/context.md")), gate.BLOCK)

    def test_other_reads_pass(self):
        self.assertEqual(gate.pre_read(self.root, self._event("src/api/x.py")), gate.ALLOW)

    def test_cross_band_write_is_blocked(self):
        self._configure()
        worklist.set_status(self.wl, "W01", "in_progress")  # store
        self.assertEqual(gate.pre_write(self.root, self._event("src/api/x.py")), gate.BLOCK)

    def test_in_band_write_passes(self):
        self._configure()
        worklist.set_status(self.wl, "W01", "in_progress")
        self.assertEqual(gate.pre_write(self.root, self._event("migrations/1.sql")), gate.ALLOW)

    def test_unmapped_path_passes(self):
        self._configure()
        worklist.set_status(self.wl, "W01", "in_progress")
        self.assertEqual(gate.pre_write(self.root, self._event("README.md")), gate.ALLOW)

    def test_no_claimed_unit_means_no_enforcement(self):
        self._configure()
        self.assertEqual(gate.pre_write(self.root, self._event("src/api/x.py")), gate.ALLOW)

    def test_ambiguous_claim_means_no_enforcement(self):
        self._configure()
        worklist.set_status(self.wl, "W01", "in_progress")
        worklist.set_status(self.wl, "W02", "in_progress")
        self.assertIsNone(gate.current_band(self.root))
        self.assertEqual(gate.pre_write(self.root, self._event("src/api/x.py")), gate.ALLOW)

    def test_glob_translation(self):
        self.assertTrue(gate._glob_to_regex("src/**/*.ts").match("src/a/b/c.ts"))
        self.assertTrue(gate._glob_to_regex("src/api/**").match("src/api/deep/x.py"))
        self.assertFalse(gate._glob_to_regex("src/*.ts").match("src/a/b.ts"))

    def test_gates_fail_open_on_garbage(self):
        for bad in ({}, {"cwd": "/nope"}, {"tool_input": {}}, {"tool_input": {"file_path": ""}}):
            self.assertEqual(gate.pre_write(self.root, bad), gate.ALLOW)
            self.assertEqual(gate.pre_read(self.root, bad), gate.ALLOW)


class TestShim(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_install_is_executable(self):
        path, _ = shim.install(self.dir)
        self.assertTrue(os.access(path, os.X_OK))
        self.assertIn("exec \"$dir/.buildcli/runtime/bcx\"", open(path).read())

    def test_install_is_idempotent(self):
        shim.install(self.dir)
        path, notes = shim.install(self.dir)
        self.assertIn("already installed and up to date", notes)

    def test_refuses_to_clobber_a_stranger(self):
        p = os.path.join(self.dir, "bcx")
        open(p, "w").write("#!/bin/sh\necho something else\n")
        with self.assertRaises(RuntimeError):
            shim.install(self.dir)

    def test_force_replaces(self):
        p = os.path.join(self.dir, "bcx")
        open(p, "w").write("#!/bin/sh\necho something else\n")
        shim.install(self.dir, force=True)
        self.assertIn("BuildCLI Agents runtime", open(p).read())

    def test_warns_when_not_on_path(self):
        _, notes = shim.install(self.dir)
        self.assertTrue(any("not on your PATH" in n for n in notes))

    def test_dispatches_from_a_nested_directory(self):
        import subprocess
        project = tempfile.mkdtemp()
        rt = os.path.join(project, ".buildcli", "runtime")
        os.makedirs(rt)
        target = os.path.join(rt, "bcx")
        open(target, "w").write("#!/bin/sh\necho DISPATCHED \"$@\"\n")
        os.chmod(target, 0o755)
        path, _ = shim.install(self.dir)
        nested = os.path.join(project, "a", "b", "c")
        os.makedirs(nested)
        out = subprocess.run([path, "next"], cwd=nested, stdout=subprocess.PIPE,
                             text=True, timeout=30)
        shutil.rmtree(project, ignore_errors=True)
        self.assertIn("DISPATCHED next", out.stdout)

    def test_fails_outside_a_project(self):
        import subprocess
        path, _ = shim.install(self.dir)
        empty = tempfile.mkdtemp()
        out = subprocess.run([path, "next"], cwd=empty, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, timeout=30)
        shutil.rmtree(empty, ignore_errors=True)
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("no .buildcli/runtime/bcx", out.stderr)


class TestJournal(Base):
    def _enforce(self, **kwargs):
        paths.write_text(paths.enforce_path(self.root), json.dumps(kwargs))

    def test_tail_of_a_missing_journal_is_empty(self):
        self.assertEqual(state.journal_tail(self.root, 5), [])

    def test_tail_returns_the_last_entries_oldest_first(self):
        for detail in ("a", "b", "c"):
            state.journal(self.root, "edit", detail)
        self.assertEqual([e["detail"] for e in state.journal_tail(self.root, 2)], ["b", "c"])
        self.assertEqual(state.journal_tail(self.root, 0), [])

    def test_since_stop_is_one_session_wide(self):
        state.journal(self.root, "edit", "old")
        state.journal(self.root, "stop", "checkpoint")
        state.journal(self.root, "done", "W01 -> done")
        entries = state.journal_since_stop(self.root)
        self.assertEqual([e["detail"] for e in entries], ["W01 -> done"])

    def test_rotation_keeps_exactly_one_generation(self):
        self._enforce(journal_max_kb=1)
        for _ in range(200):
            state.journal(self.root, "edit", "x" * 60)
        self.assertTrue(os.path.isfile(paths.journal_path(self.root)))
        self.assertTrue(os.path.isfile(paths.journal_prev_path(self.root)))
        names = sorted(os.listdir(os.path.dirname(paths.journal_path(self.root))))
        self.assertEqual(names, ["session.1.log", "session.log"])

    def test_rotation_off_at_zero(self):
        self._enforce(journal_max_kb=0)
        for _ in range(200):
            state.journal(self.root, "edit", "x" * 60)
        names = os.listdir(os.path.dirname(paths.journal_path(self.root)))
        self.assertEqual(names, ["session.log"])


class TestCheckpoint(Base):
    def setUp(self):
        Base.setUp(self)
        state.set_active(self.root, self.bp)

    def test_checkpoint_names_blueprint_claim_and_completions(self):
        worklist.set_status(self.wl, "W01", "in_progress")
        state.journal(self.root, "done", "W00 -> done (store)")
        line = gate.checkpoint(self.root)
        self.assertIn("blueprint=%s" % self.bp, line)
        self.assertIn("claimed=W01", line)
        self.assertIn("completed=1", line)
        self.assertIn("verify=not-run", line)

    def test_a_quiet_session_still_reports_zero(self):
        line = gate.checkpoint(self.root)
        self.assertIn("claimed=-", line)
        self.assertIn("completed=0", line)

    def test_completions_are_counted_since_the_last_stop_only(self):
        state.journal(self.root, "done", "W00 -> done (store)")
        state.journal(self.root, "stop", "earlier checkpoint")
        state.journal(self.root, "done", "W01 -> done (store)")
        self.assertIn("completed=1", gate.checkpoint(self.root))

    def test_on_stop_writes_the_checkpoint_and_allows(self):
        self.assertEqual(gate.on_stop(self.root, {}), gate.ALLOW)
        last = state.journal_tail(self.root, 1)[0]
        self.assertEqual(last["kind"], "STOP")
        self.assertIn("blueprint=%s" % self.bp, last["detail"])


class TestResume(Base):
    def setUp(self):
        Base.setUp(self)
        state.set_active(self.root, self.bp)

    def test_digest_reports_the_pipeline_position(self):
        worklist.set_status(self.wl, "W01", "in_progress")
        text = "\n".join(cli.resume_lines(self.root))
        self.assertIn(self.bp, text)
        self.assertIn("claimed  : W01", text)
        self.assertIn("stage    : worklist", text)

    def test_digest_stays_inside_its_line_budget(self):
        for i in range(50):
            state.journal(self.root, "edit", "edit number %d" % i)
        lines = cli.resume_lines(self.root, entries=99)
        self.assertLessEqual(len(lines), cli.RESUME_MAX_LINES)

    def test_digest_never_carries_band_content(self):
        """The load-bearing one: this output is injected as model-visible context.

        If band text reached it, `gate.pre_read` would be defeated from the inside
        and band scoping would stop being a mechanism.
        """
        text = "\n".join(cli.resume_lines(self.root, entries=12))
        for band in context.band_names(self.root):
            body = context.extract(self.root, band)
            if not context.is_populated(body):
                continue
            for line in body.splitlines():
                line = line.strip()
                if line.startswith("- ") and len(line) > 8:
                    self.assertNotIn(line, text)
                # Whole lines are not enough: a band value can arrive reformatted.
                # Backticked spans are how bands carry commands and paths.
                for span in re.findall(r"`([^`]+)`", line):
                    if len(span) > 4:
                        self.assertNotIn(span, text)
        self.assertNotIn("FastAPI", text)

    def test_the_verify_command_is_not_echoed_into_the_digest(self):
        """`verify` journals the command it read out of [band:verify].

        Not reading context.md is not enough on its own — something else already
        carried a fragment of a band into the log the digest prints from.
        """
        command = verify.discover_command(self.root)
        self.assertTrue(command)
        state.journal(self.root, "verify", "PASS exit=0 :: %s" % command)
        text = "\n".join(cli.resume_lines(self.root))
        self.assertIn("PASS exit=0", text)   # the outcome is what resuming needs
        self.assertNotIn(command, text)      # the band text is not
        entries = cli.resume_payload(self.root)["journal"]
        self.assertFalse([e for e in entries if command in e["detail"]])

    def test_a_verify_timeout_is_trimmed_the_same_way(self):
        command = verify.discover_command(self.root)
        state.journal(self.root, "verify", "TIMEOUT after 900s :: %s" % command)
        text = "\n".join(cli.resume_lines(self.root))
        self.assertIn("TIMEOUT after 900s", text)
        self.assertNotIn(command, text)

    def test_the_journal_on_disk_keeps_the_command(self):
        """Only the digest is trimmed. The file is for the human, and is not injected."""
        command = verify.discover_command(self.root)
        state.journal(self.root, "verify", "PASS exit=0 :: %s" % command)
        raw = paths.read_text(paths.journal_path(self.root))
        self.assertIn(command, raw)

    def test_digest_survives_a_project_with_no_active_blueprint(self):
        os.remove(paths.active_path(self.root))
        text = "\n".join(cli.resume_lines(self.root))
        self.assertIn("(none)", text)

    def test_payload_carries_the_same_values(self):
        worklist.set_status(self.wl, "W01", "in_progress")
        payload = cli.resume_payload(self.root)
        self.assertEqual(payload["active"], self.bp)
        self.assertEqual(payload["claimed"], ["W01"])
        self.assertEqual(payload["units"]["total"], 2)


class TestSessionStart(Base):
    def setUp(self):
        Base.setUp(self)
        state.set_active(self.root, self.bp)
        self.buffer = io.StringIO()
        self.saved, sys.stdout = sys.stdout, self.buffer

    def tearDown(self):
        sys.stdout = self.saved
        Base.tearDown(self)

    def _run(self, event=None):
        code = gate.session_start(self.root, event if event is not None else {})
        return code, self.buffer.getvalue()

    def test_registered_as_a_gate(self):
        self.assertIn("session-start", gate.HANDLERS)

    def test_prints_the_digest_and_allows(self):
        code, out = self._run({"hook_event_name": "SessionStart", "source": "startup"})
        self.assertEqual(code, gate.ALLOW)
        self.assertIn(self.bp, out)

    def test_silent_when_switched_off(self):
        paths.write_text(paths.enforce_path(self.root), json.dumps({"session_start": False}))
        code, out = self._run()
        self.assertEqual(code, gate.ALLOW)
        self.assertEqual(out, "")

    def test_silent_when_enforcement_is_off(self):
        paths.write_text(paths.enforce_path(self.root), json.dumps({"enabled": False}))
        code, out = self._run()
        self.assertEqual(code, gate.ALLOW)
        self.assertEqual(out, "")

    def test_an_empty_event_still_allows(self):
        code, out = self._run({})
        self.assertEqual(code, gate.ALLOW)
        self.assertTrue(out)

    def test_never_leaks_band_content(self):
        _, out = self._run()
        self.assertNotIn("FastAPI", out)


class TestDerivedActive(Base):
    """The pointer is gitignored, so a fresh clone has blueprints but no `active`."""

    def setUp(self):
        Base.setUp(self)
        state._DERIVED_CACHE.clear()
        self.second = os.path.join("blueprints", "features", "later")
        os.makedirs(os.path.join(self.root, self.second))
        paths.write_text(os.path.join(self.root, self.second, "brief.md"), "# Later\n")

    def tearDown(self):
        state._DERIVED_CACHE.clear()
        Base.tearDown(self)

    def _git(self, *argv):
        import subprocess
        subprocess.run(["git"] + list(argv), cwd=self.root, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _repo(self):
        self._git("init", "-q")
        self._git("config", "user.email", "t@example.com")
        self._git("config", "user.name", "t")

    def _commit(self, path, message, when):
        import subprocess
        self._git("add", path)
        env = dict(os.environ, GIT_AUTHOR_DATE=when, GIT_COMMITTER_DATE=when)
        subprocess.run(["git", "commit", "-q", "-m", message], cwd=self.root, check=True,
                       env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def test_newest_commit_wins(self):
        self._repo()
        self._commit(self.bp, "first", "2020-01-01T00:00:00")
        self._commit(self.second, "second", "2021-01-01T00:00:00")
        value, source = state.active_with_source(self.root)
        self.assertEqual(value, self.second)
        self.assertEqual(source, "derived")

    def test_an_uncommitted_blueprint_is_never_chosen(self):
        self._repo()
        self._commit(self.bp, "first", "2020-01-01T00:00:00")
        # `self.second` stays in the working tree only — no commit, no recency.
        self.assertEqual(state.get_active(self.root), self.bp)

    def test_a_real_pointer_beats_derivation(self):
        self._repo()
        self._commit(self.second, "second", "2021-01-01T00:00:00")
        state.set_active(self.root, self.bp)
        self.assertEqual(state.active_with_source(self.root), (self.bp, "pointer"))

    def test_no_git_falls_back_to_nothing(self):
        value, source = state.active_with_source(self.root)
        self.assertIsNone(value)
        self.assertIsNone(source)

    def test_derivation_writes_nothing(self):
        self._repo()
        self._commit(self.bp, "first", "2020-01-01T00:00:00")
        self.assertEqual(state.get_active(self.root), self.bp)
        self.assertFalse(os.path.exists(paths.active_path(self.root)))

    def test_digest_labels_a_derived_pointer(self):
        self._repo()
        self._commit(self.bp, "first", "2020-01-01T00:00:00")
        text = "\n".join(cli.resume_lines(self.root))
        self.assertIn("derived from git", text)


class TestStaleRuntime(Base):
    """The kit bootstraps itself, so its installed runtime is a copy that can lag."""

    def setUp(self):
        Base.setUp(self)
        self.src = os.path.join(self.root, cli.KIT_RUNTIME)
        self.dest = os.path.join(paths.state_dir(self.root), "runtime", "bcx_lib")
        os.makedirs(self.src)
        os.makedirs(self.dest)

    def _write(self, where, name, body):
        paths.write_text(os.path.join(where, name), body)

    def test_silent_in_a_project_without_the_kit(self):
        shutil.rmtree(self.src)
        self.assertIsNone(cli.stale_runtime(self.root))

    def test_silent_when_the_copy_matches(self):
        self._write(self.src, "state.py", "x = 1\n")
        self._write(self.dest, "state.py", "x = 1\n")
        self.assertIsNone(cli.stale_runtime(self.root))

    def test_names_the_module_that_drifted(self):
        self._write(self.src, "state.py", "x = 2\n")
        self._write(self.dest, "state.py", "x = 1\n")
        self.assertEqual(cli.stale_runtime(self.root), "state.py")

    def test_a_module_missing_from_the_copy_counts(self):
        self._write(self.src, "resume.py", "x = 1\n")
        self.assertEqual(cli.stale_runtime(self.root), "resume.py")

    def test_a_module_left_behind_in_the_copy_counts(self):
        self._write(self.dest, "gone.py", "x = 1\n")
        self.assertEqual(cli.stale_runtime(self.root), "gone.py")


# ── concurrency ───────────────────────────────────────────────────────────────
#
# The rest of this file tests the library in-process, which is the right default.
# These do not, and cannot: the bug is that two *processes* rewriting worklist.md
# lose one of the two writes, and a lock that only excludes threads would pass a
# threaded test while the real failure survived. So these spawn real interpreters
# and make them lunge at the same instant.

RUNNER = """
import os, sys, time
sys.path.insert(0, %(runtime)r)
from bcx_lib import claims
root, unit, owner, barrier = sys.argv[1:5]
while not os.path.exists(barrier):
    time.sleep(0.001)
%(body)s
"""

CLAIM_BODY = """
try:
    claims.acquire(root, unit, owner=owner)
    sys.exit(0)
except claims.ClaimError:
    sys.exit(1)
"""

TRANSITION_BODY = """
from bcx_lib import worklist
try:
    with claims.worklist_lock(root, timeout=30):
        worklist.set_status(os.path.join(root, %(wl)r), unit, "in_progress")
    sys.exit(0)
except Exception:
    sys.exit(1)
"""

RUNTIME_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ConcurrencyBase(unittest.TestCase):
    """A scratch project plus a way to run N interpreters against it at once."""

    UNITS = 8

    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, ".buildcli"))
        self.bp = os.path.join("blueprints", "features", "demo")
        os.makedirs(os.path.join(self.root, self.bp))
        paths.write_text(os.path.join(self.root, self.bp, "brief.md"), "# Brief\n")
        self.wl_rel = os.path.join(self.bp, "worklist.md")
        self.wl = os.path.join(self.root, self.wl_rel)
        paths.write_text(self.wl, self._worklist(self.UNITS))
        self.barrier = os.path.join(self.root, "go")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    @staticmethod
    def _worklist(count):
        out = ["## Units", ""]
        for i in range(1, count + 1):
            out += ["### U%02d — unit %d" % (i, i),
                    "- Band: service",
                    "- Blocked by: —",
                    "- Check: it exists",
                    ""]
        return "\n".join(out)

    def _race(self, body, jobs):
        """Start one interpreter per job, release them together, collect exit codes."""
        script = os.path.join(self.root, "runner.py")
        paths.write_text(script, RUNNER % {"runtime": RUNTIME_DIR, "body": body})
        procs = [subprocess.Popen(
            [sys.executable, script, self.root, unit, owner, self.barrier],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for unit, owner in jobs]
        # Every child is now spinning on the barrier; one touch starts them all.
        time.sleep(0.4)
        paths.write_text(self.barrier, "")
        return [p.wait(timeout=60) for p in procs]


class TestConcurrentClaims(ConcurrencyBase):
    def test_only_one_process_can_claim_a_unit(self):
        codes = self._race(CLAIM_BODY, [("U01", "agent%d" % i) for i in range(12)])
        self.assertEqual(codes.count(0), 1, "expected exactly one winner, got %r" % codes)
        self.assertEqual(codes.count(1), 11)

    def test_the_winner_owns_the_claim_on_disk(self):
        self._race(CLAIM_BODY, [("U01", "agent%d" % i) for i in range(8)])
        record = claims.read(self.root, "U01")
        self.assertIsNotNone(record)
        self.assertTrue(record["owner"].startswith("agent"))

    def test_claims_on_distinct_units_all_succeed(self):
        jobs = [("U%02d" % i, "agent%d" % i) for i in range(1, self.UNITS + 1)]
        codes = self._race(CLAIM_BODY, jobs)
        self.assertEqual(codes, [0] * self.UNITS)
        self.assertEqual(sorted(claims.all_claims(self.root)),
                         sorted(u for u, _ in jobs))


class TestConcurrentTransitions(ConcurrencyBase):
    """The lost-update case: distinct units, so nothing is contended but the file."""

    def test_no_status_write_is_lost(self):
        body = TRANSITION_BODY % {"wl": self.wl_rel}
        jobs = [("U%02d" % i, "agent%d" % i) for i in range(1, self.UNITS + 1)]
        codes = self._race(body, jobs)
        self.assertEqual(codes, [0] * self.UNITS)

        units = worklist.parse(paths.read_text(self.wl))
        landed = [u["id"] for u in units if u["status"] == "in_progress"]
        self.assertEqual(len(landed), self.UNITS,
                         "lost %d of %d status writes: %r"
                         % (self.UNITS - len(landed), self.UNITS, landed))

    def test_the_file_is_still_parseable_afterwards(self):
        body = TRANSITION_BODY % {"wl": self.wl_rel}
        self._race(body, [("U%02d" % i, "a%d" % i) for i in range(1, self.UNITS + 1)])
        units = worklist.parse(paths.read_text(self.wl))
        self.assertEqual(len(units), self.UNITS)
        self.assertEqual(worklist.validate(units), [])


class TestWorklistLock(Base):
    def test_a_live_lock_is_never_stolen(self):
        os.makedirs(paths.claims_dir(self.root), exist_ok=True)
        paths.write_text(paths.lock_path(self.root),
                         json.dumps({"owner": "ghost", "pid": 4242, "host": "otherbox"}))
        with self.assertRaises(claims.ClaimError) as caught:
            with claims.worklist_lock(self.root, timeout=0.2):
                pass
        message = str(caught.exception)
        self.assertIn(paths.lock_path(self.root), message)
        self.assertIn("ghost", message)
        # Still there: the waiter gave up rather than breaking a lock it could
        # not prove was dead.
        self.assertTrue(os.path.exists(paths.lock_path(self.root)))

    def test_a_stale_lock_is_broken(self):
        os.makedirs(paths.claims_dir(self.root), exist_ok=True)
        lock = paths.lock_path(self.root)
        paths.write_text(lock, json.dumps({"owner": "dead"}))
        old = time.time() - 3600
        os.utime(lock, (old, old))
        with claims.worklist_lock(self.root, timeout=0.2):
            pass
        self.assertFalse(os.path.exists(lock))

    def test_the_lock_is_released_when_the_body_raises(self):
        with self.assertRaises(RuntimeError):
            with claims.worklist_lock(self.root):
                raise RuntimeError("boom")
        self.assertFalse(os.path.exists(paths.lock_path(self.root)))

    def test_staleness_is_not_the_wait_timeout(self):
        # One knob for both would make a waiter break the lock at the exact
        # moment it should have given up, stealing it from a live holder.
        self.assertGreater(claims.STALE_FACTOR, 1)
        self.assertGreaterEqual(claims.STALE_FLOOR_SECONDS, 60)


class TestAgentFlag(Base):
    """`--agent` on the transition commands, and how identity resolves."""

    def setUp(self):
        super(TestAgentFlag, self).setUp()
        self._saved = os.environ.pop("BCX_AGENT_ID", None)

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("BCX_AGENT_ID", None)
        else:
            os.environ["BCX_AGENT_ID"] = self._saved
        super(TestAgentFlag, self).tearDown()

    @staticmethod
    def _parse(argv):
        return cli.build_parser().parse_args(argv)

    def test_the_transition_commands_accept_it(self):
        for argv in (["claim", "W01", "--agent", "alpha"],
                     ["done", "W01", "--agent", "alpha"],
                     ["block", "W01", "--reason", "x", "--agent", "alpha"]):
            self.assertEqual(self._parse(argv).agent, "alpha", argv)

    def test_it_is_optional(self):
        self.assertIsNone(self._parse(["claim", "W01"]).agent)

    def test_help_mentions_it(self):
        buf = io.StringIO()
        parser = cli.build_parser()
        # argparse exposes subparsers only through the private map; the help of
        # the `claim` subcommand is what a user actually reads.
        sub = [a for a in parser._actions if hasattr(a, "choices") and a.choices][0]
        sub.choices["claim"].print_help(buf)
        self.assertIn("--agent", buf.getvalue())

    def test_the_flag_wins_over_the_environment(self):
        os.environ["BCX_AGENT_ID"] = "beta"
        self.assertEqual(cli._identity(self._parse(["claim", "W01", "--agent", "alpha"])),
                         "alpha")

    def test_the_environment_is_used_without_a_flag(self):
        os.environ["BCX_AGENT_ID"] = "beta"
        self.assertEqual(cli._identity(self._parse(["claim", "W01"])), "beta")

    def test_neither_resolves_to_nobody(self):
        self.assertIsNone(cli._identity(self._parse(["claim", "W01"])))

    def test_a_blank_environment_value_is_nobody(self):
        os.environ["BCX_AGENT_ID"] = "   "
        self.assertIsNone(cli._identity(self._parse(["claim", "W01"])))

    def _apply_quietly(self, argv, status="in_progress"):
        """Run one transition, swallowing the line it prints for the operator."""
        buf = io.StringIO()
        stdout, sys.stdout = sys.stdout, buf
        try:
            cli._apply(self.root, self._parse(argv), status)
        finally:
            sys.stdout = stdout
        return state.journal_tail(self.root, 1)[0]["detail"]

    def test_the_owner_reaches_the_journal(self):
        detail = self._apply_quietly(
            ["claim", "W01", "--agent", "alpha", "--blueprint", self.bp])
        self.assertIn("by alpha", detail)

    def test_without_an_identity_the_journal_line_is_unchanged(self):
        detail = self._apply_quietly(["claim", "W01", "--blueprint", self.bp])
        self.assertEqual(detail, "W01 -> in_progress (store)")


PARALLEL_WORKLIST = """## Units

### W01 — Schema
- Band: store
- Blocked by: —
- Check: migration applies

### W02 — Endpoint
- Band: service
- Blocked by: —
- Check: returns 201

### W03 — Page
- Band: interface
- Blocked by: W01
- Check: renders
"""


class ClaimBase(Base):
    """A three-unit worklist and a way to drive claims through the CLI layer.

    Kept apart from the test classes so that extending it does not re-run
    somebody else's tests.
    """

    def setUp(self):
        super(ClaimBase, self).setUp()
        self._saved = os.environ.pop("BCX_AGENT_ID", None)
        paths.write_text(self.wl, PARALLEL_WORKLIST)

    def tearDown(self):
        if self._saved is not None:
            os.environ["BCX_AGENT_ID"] = self._saved
        super(ClaimBase, self).tearDown()

    def _claim(self, unit, agent=None, force=False):
        argv = ["claim", unit, "--blueprint", self.bp]
        if agent:
            argv += ["--agent", agent]
        if force:
            argv.append("--force")
        args = cli.build_parser().parse_args(argv)
        buf, err = io.StringIO(), io.StringIO()
        stdout, stderr = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = buf, err
        try:
            code = cli.cmd_claim(self.root, args)
        finally:
            sys.stdout, sys.stderr = stdout, stderr
        return code, err.getvalue()

    def _close(self, unit, agent=None, status="done", reason="x"):
        argv = [status if status == "done" else "block", unit, "--blueprint", self.bp]
        if status == "blocked":
            argv += ["--reason", reason]
        if agent:
            argv += ["--agent", agent]
        args = cli.build_parser().parse_args(argv)
        buf, err = io.StringIO(), io.StringIO()
        stdout, stderr = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = buf, err
        try:
            code = (cli.cmd_done if status == "done" else cli.cmd_block)(self.root, args)
        finally:
            sys.stdout, sys.stderr = stdout, stderr
        return code, err.getvalue()


class TestClaimOwnership(ClaimBase):
    """Refusal scoped to the caller, takeovers, and the untouched legacy path."""

    def test_another_agents_claim_does_not_block(self):
        self.assertEqual(self._claim("W01", "alpha")[0], cli.OK)
        code, err = self._claim("W02", "beta")
        self.assertEqual(code, cli.OK, err)
        self.assertEqual(claims.read(self.root, "W02")["owner"], "beta")

    def test_my_own_second_claim_is_refused(self):
        self._claim("W01", "alpha")
        code, err = self._claim("W02", "alpha")
        self.assertEqual(code, cli.FAIL)
        self.assertIn("W01", err)
        self.assertIn("alpha", err)

    def test_my_own_second_claim_succeeds_with_force(self):
        self._claim("W01", "alpha")
        self.assertEqual(self._claim("W02", "alpha", force=True)[0], cli.OK)

    def test_the_claim_records_owner_band_and_blueprint(self):
        self._claim("W01", "alpha")
        record = claims.read(self.root, "W01")
        self.assertEqual(record["owner"], "alpha")
        self.assertEqual(record["band"], "store")
        self.assertEqual(record["blueprint"], self.bp)

    def test_taking_a_held_unit_needs_force(self):
        self._claim("W01", "alpha")
        code, err = self._claim("W01", "beta")
        self.assertEqual(code, cli.FAIL)
        self.assertIn("held by alpha", err)
        self.assertEqual(claims.read(self.root, "W01")["owner"], "alpha")

    def test_a_takeover_transfers_ownership(self):
        self._claim("W01", "alpha")
        self.assertEqual(self._claim("W01", "beta", force=True)[0], cli.OK)
        self.assertEqual(claims.read(self.root, "W01")["owner"], "beta")

    def test_a_takeover_is_journaled_apart_from_a_claim(self):
        self._claim("W01", "alpha")
        self._claim("W01", "beta", force=True)
        kinds = [e["kind"] for e in state.journal_entries(self.root)]
        self.assertIn("STEAL", kinds)
        steal = [e for e in state.journal_entries(self.root) if e["kind"] == "STEAL"][0]
        self.assertIn("from alpha", steal["detail"])
        self.assertIn("by beta", steal["detail"])

    def test_an_ordinary_claim_does_not_journal_a_steal(self):
        self._claim("W01", "alpha")
        self.assertNotIn("STEAL",
                         [e["kind"] for e in state.journal_entries(self.root)])

    def test_reclaiming_my_own_unit_is_not_a_steal(self):
        self._claim("W01", "alpha")
        self._claim("W01", "alpha")
        self.assertNotIn("STEAL",
                         [e["kind"] for e in state.journal_entries(self.root)])

    def test_dependencies_are_still_enforced(self):
        code, err = self._claim("W03", "alpha")
        self.assertEqual(code, cli.FAIL)
        self.assertIn("blocked by: W01", err)

    def test_dependencies_are_still_enforced_without_an_identity(self):
        code, err = self._claim("W03")
        self.assertEqual(code, cli.FAIL)
        self.assertIn("blocked by: W01", err)

    def test_an_unowned_in_progress_unit_does_not_block_a_named_agent(self):
        # A hand-edited status, or one claimed before identities existed.
        worklist.set_status(self.wl, "W01", "in_progress")
        self.assertEqual(self._claim("W02", "alpha")[0], cli.OK)

    def test_without_an_identity_any_claim_still_blocks(self):
        self._claim("W01")
        code, err = self._claim("W02")
        self.assertEqual(code, cli.FAIL)
        self.assertEqual(
            err,
            "already in progress: W01\n"
            "The write gate keys off a single claimed unit. Finish it, or pass --force.\n")

    def test_an_unnamed_caller_cannot_silently_take_a_named_claim(self):
        self._claim("W01", "alpha")
        code, err = self._claim("W01")
        self.assertEqual(code, cli.FAIL)
        self.assertIn("held by alpha", err)


class TestClaimRelease(ClaimBase):
    """What a terminal transition does to the claim behind it."""

    def test_done_drops_the_claim(self):
        self._claim("W01", "alpha")
        self.assertEqual(self._close("W01", "alpha")[0], cli.OK)
        self.assertIsNone(claims.read(self.root, "W01"))

    def test_block_drops_the_claim(self):
        self._claim("W01", "alpha")
        self.assertEqual(self._close("W01", "alpha", status="blocked")[0], cli.OK)
        self.assertIsNone(claims.read(self.root, "W01"))

    def test_a_released_unit_is_claimable_without_force(self):
        self._claim("W01", "alpha")
        self._close("W01", "alpha")
        worklist.set_status(self.wl, "W01", "pending")
        code, err = self._claim("W01", "beta")
        self.assertEqual(code, cli.OK, err)
        self.assertEqual(claims.read(self.root, "W01")["owner"], "beta")

    def test_closing_someone_elses_unit_succeeds(self):
        self._claim("W01", "alpha")
        self.assertEqual(self._close("W01", "beta")[0], cli.OK)
        self.assertIsNone(claims.read(self.root, "W01"))

    def test_closing_someone_elses_unit_is_journaled(self):
        self._claim("W01", "alpha")
        self._close("W01", "beta")
        freed = [e for e in state.journal_entries(self.root) if e["kind"] == "FREED"]
        self.assertEqual(len(freed), 1)
        self.assertIn("from alpha", freed[0]["detail"])
        self.assertIn("by beta", freed[0]["detail"])

    def test_closing_my_own_unit_is_not_journaled_as_freed(self):
        self._claim("W01", "alpha")
        self._close("W01", "alpha")
        self.assertNotIn("FREED",
                         [e["kind"] for e in state.journal_entries(self.root)])

    def test_closing_an_unclaimed_unit_is_quiet_and_succeeds(self):
        self.assertIsNone(claims.read(self.root, "W02"))
        code, err = self._close("W02", "alpha")
        self.assertEqual(code, cli.OK, err)
        self.assertNotIn("FREED",
                         [e["kind"] for e in state.journal_entries(self.root)])

    def test_closing_an_unclaimed_unit_without_an_identity_succeeds(self):
        self.assertEqual(self._close("W02")[0], cli.OK)

    def test_a_full_claim_close_reclaim_cycle_leaves_no_residue(self):
        for who in ("alpha", "beta", "gamma"):
            self.assertEqual(self._claim("W01", who)[0], cli.OK)
            self.assertEqual(claims.read(self.root, "W01")["owner"], who)
            self._close("W01", who)
            self.assertIsNone(claims.read(self.root, "W01"))
            worklist.set_status(self.wl, "W01", "pending")
        self.assertEqual(claims.all_claims(self.root), {})
        self.assertNotIn("STEAL",
                         [e["kind"] for e in state.journal_entries(self.root)])

    def test_two_workers_can_run_and_close_independently(self):
        self._claim("W01", "alpha")
        self._claim("W02", "beta")
        self._close("W01", "alpha")
        # beta is untouched by alpha finishing.
        self.assertEqual(claims.read(self.root, "W02")["owner"], "beta")
        self.assertIsNone(claims.read(self.root, "W01"))


class TestCurrentBand(ClaimBase):
    """Which band the gate believes a given caller is working in."""

    def setUp(self):
        super(TestCurrentBand, self).setUp()
        state.set_active(self.root, self.bp)

    def test_each_agent_gets_its_own_band(self):
        self._claim("W01", "alpha")      # store
        self._claim("W02", "beta")       # service
        self.assertEqual(gate.current_band(self.root, "alpha"), "store")
        self.assertEqual(gate.current_band(self.root, "beta"), "service")

    def test_an_agent_holding_nothing_gets_none(self):
        self._claim("W01", "alpha")
        self.assertIsNone(gate.current_band(self.root, "beta"))

    def test_an_agent_holding_two_units_gets_none(self):
        self._claim("W01", "alpha")
        self._claim("W02", "alpha", force=True)
        self.assertIsNone(gate.current_band(self.root, "alpha"))

    def test_a_stale_claim_on_a_closed_unit_gets_none(self):
        self._claim("W01", "alpha")
        worklist.set_status(self.wl, "W01", "done")   # closed behind the claim
        self.assertIsNone(gate.current_band(self.root, "alpha"))

    def test_without_an_agent_one_claim_still_resolves(self):
        self._claim("W01", "alpha")
        self.assertEqual(gate.current_band(self.root), "store")

    def test_without_an_agent_two_claims_are_ambiguous(self):
        self._claim("W01", "alpha")
        self._claim("W02", "beta")
        self.assertIsNone(gate.current_band(self.root))

    def test_without_an_agent_nothing_claimed_is_none(self):
        self.assertIsNone(gate.current_band(self.root))

    def test_an_unreadable_claim_store_resolves_to_none(self):
        self._claim("W01", "alpha")
        shutil.rmtree(paths.claims_dir(self.root))
        self.assertIsNone(gate.current_band(self.root, "alpha"))

    def test_the_legacy_path_is_untouched_by_claim_files(self):
        # No identity in play: the answer comes from the worklist, exactly as
        # it did before a claim store existed.
        worklist.set_status(self.wl, "W02", "in_progress")
        self.assertEqual(gate.current_band(self.root), "service")
        self.assertEqual(claims.all_claims(self.root), {})


class TestGateScopedByAgent(ClaimBase):
    """Two workers, two bands, one gate that can finally tell them apart."""

    def setUp(self):
        super(TestGateScopedByAgent, self).setUp()
        paths.write_text(paths.bands_map_path(self.root), json.dumps({
            "store": ["migrations/**"],
            "service": ["src/api/**"],
            "interface": ["src/ui/**"],
        }))
        state.set_active(self.root, self.bp)
        self._claim("W02", "beta")       # service
        self._claim("W03", "alpha", force=True)   # interface, deps forced

    def _write_event(self, path):
        return {"cwd": self.root,
                "tool_input": {"file_path": os.path.join(self.root, path)}}

    def _as(self, agent, path):
        if agent is None:
            os.environ.pop("BCX_AGENT_ID", None)
        else:
            os.environ["BCX_AGENT_ID"] = agent
        buf, stderr = io.StringIO(), sys.stderr
        sys.stderr = buf
        try:
            return gate.pre_write(self.root, self._write_event(path)), buf.getvalue()
        finally:
            sys.stderr = stderr

    def test_the_interface_worker_may_write_interface_files(self):
        code, _ = self._as("alpha", "src/ui/page.tsx")
        self.assertEqual(code, gate.ALLOW)

    def test_the_service_worker_may_not_write_interface_files(self):
        code, err = self._as("beta", "src/ui/page.tsx")
        self.assertEqual(code, gate.BLOCK)
        self.assertIn("interface", err)
        self.assertIn("service", err)
        self.assertIn("beta", err)

    def test_the_service_worker_may_write_service_files(self):
        self.assertEqual(self._as("beta", "src/api/x.py")[0], gate.ALLOW)

    def test_the_interface_worker_may_not_write_service_files(self):
        code, err = self._as("alpha", "src/api/x.py")
        self.assertEqual(code, gate.BLOCK)
        self.assertIn("alpha", err)

    def test_two_live_claims_and_no_identity_allows(self):
        # The pre-identity behaviour, preserved: the gate cannot attribute the
        # write, so it does not block it.
        self.assertEqual(self._as(None, "src/ui/page.tsx")[0], gate.ALLOW)

    def test_an_unknown_agent_allows(self):
        self.assertEqual(self._as("nobody", "src/ui/page.tsx")[0], gate.ALLOW)

    def test_a_path_no_band_owns_is_never_blocked(self):
        self.assertEqual(self._as("beta", "README.md")[0], gate.ALLOW)

    def test_framework_state_is_never_blocked(self):
        self.assertEqual(self._as("beta", ".buildcli/claims/x.claim")[0], gate.ALLOW)
        self.assertEqual(self._as("beta", "blueprints/features/demo/brief.md")[0],
                         gate.ALLOW)


# ── the single-agent path, pinned ─────────────────────────────────────────────
#
# Assumption 7 of the brief: the no-identity case is the common one, and it must
# not regress in behaviour, message text, or exit code. Every other claim test in
# this file asserts on a substring, so a reworded refusal would sail past all of
# them. These bytes will not.
#
# Captured once, by hand, from the release that shipped before agent-scoped
# claims existed — that revision's `bcx_lib.cli` was run in a subprocess against
# a scratch project and the bytes transcribed here as literals:
#
#     git show <release>:buildcli/runtime/bcx_lib/cli.py
#
# They are literals on purpose. A fixture regenerated at run time from the code
# under test agrees with whatever that code now does, which is precisely the
# thing a regression pin must refuse to do.

RELEASE_FIRST_CLAIM = (0, b"  W01 Schema -> in_progress\n", b"")

RELEASE_SECOND_CLAIM = (
    1,
    b"",
    b"already in progress: W01\n"
    b"The write gate keys off a single claimed unit. Finish it, or pass --force.\n",
)

# `python -c` equivalent of the `bcx` entry point, for the out-of-process pin.
CLI_MAIN = "import sys; from bcx_lib import cli; sys.exit(cli.main())"


class TestSingleAgentRefusalIsPinned(ClaimBase):
    """W08 — the pre-identity refusal, byte for byte, in and out of process."""

    def setUp(self):
        super(TestSingleAgentRefusalIsPinned, self).setUp()
        # ClaimBase already pops it; assert rather than trust, because an
        # identity leaking in would route these through the *other* branch of
        # `_blocking_units` and the pin would be testing the wrong thing.
        os.environ.pop("BCX_AGENT_ID", None)
        self.assertIsNone(claims.resolve_identity())

    def _claim_verbatim(self, unit):
        """Exit code and the exact bytes the CLI wrote, with nothing swallowed."""
        args = cli.build_parser().parse_args(["claim", unit, "--blueprint", self.bp])
        self.assertIsNone(args.agent)
        self.assertFalse(args.force)
        out, err = io.StringIO(), io.StringIO()
        stdout, stderr = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = out, err
        try:
            code = cli.cmd_claim(self.root, args)
        finally:
            sys.stdout, sys.stderr = stdout, stderr
        return code, out.getvalue().encode("utf-8"), err.getvalue().encode("utf-8")

    def test_the_first_claim_still_reads_exactly_as_it_did(self):
        self.assertEqual(self._claim_verbatim("W01"), RELEASE_FIRST_CLAIM)

    def test_the_second_claim_still_reads_exactly_as_it_did(self):
        self.assertEqual(self._claim_verbatim("W01"), RELEASE_FIRST_CLAIM)
        self.assertEqual(self._claim_verbatim("W02"), RELEASE_SECOND_CLAIM)

    def test_the_refusal_leaves_the_second_unit_untouched(self):
        self._claim_verbatim("W01")
        self._claim_verbatim("W02")
        _, units = worklist.load(self.wl)
        by_id = {u["id"]: u["status"] for u in units}
        self.assertEqual(by_id["W01"], "in_progress")
        self.assertEqual(by_id["W02"], "pending")
        self.assertIsNone(claims.read(self.root, "W02"))

    def test_the_process_exit_code_and_streams_match_too(self):
        """The in-process pin asserts a return value; this asserts an exit status.

        `main` hands `cmd_claim`'s return straight to the shell, and a fixture
        about an exit code is worth checking where an exit code actually happens.
        """
        env = dict(os.environ)
        env.pop("BCX_AGENT_ID", None)
        env["PYTHONPATH"] = RUNTIME_DIR

        def run(unit):
            done = subprocess.run(
                [sys.executable, "-c", CLI_MAIN, "claim", unit, "--blueprint", self.bp],
                cwd=self.root, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=60)
            return done.returncode, done.stdout, done.stderr

        self.assertEqual(run("W01"), RELEASE_FIRST_CLAIM)
        self.assertEqual(run("W02"), RELEASE_SECOND_CLAIM)


class TestBriefIdentityCriteria(ClaimBase):
    """W09 — one test per identity-bearing acceptance criterion in the brief.

    These deliberately restate criteria that other classes here already touch in
    pieces. The value is the mapping: each method is the whole of one criterion,
    named after it, so a criterion that stops holding fails a test that says so
    rather than a test about something adjacent.

    Ownership is always read from the claim store. `worklist.md` is the source of
    truth for *status* and says nothing about *who*, so asserting an owner by
    parsing it would be asserting on a fact it does not carry.
    """

    def _owner(self, unit):
        record = claims.read(self.root, unit)
        return record.get("owner") if record else None

    def _graph(self):
        """`bcx graph --json`, parsed — the machine-readable output criterion 2 names."""
        args = cli.build_parser().parse_args(
            ["graph", "--json", "--blueprint", self.bp])
        buf, err = io.StringIO(), io.StringIO()
        stdout, stderr = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = buf, err
        try:
            cli.cmd_graph(self.root, args)
        finally:
            sys.stdout, sys.stderr = stdout, stderr
        return {u["id"]: u for u in json.loads(buf.getvalue())["units"]}

    def _kinds(self):
        return [e["kind"] for e in state.journal_entries(self.root)]

    # (2) alpha claims W01 -> W01 reports in_progress and owner alpha in the
    #     runtime's machine-readable graph output.
    def test_criterion_2_the_graph_reports_status_and_owner(self):
        self.assertEqual(self._claim("W01", "alpha")[0], cli.OK)

        row = self._graph()["W01"]
        self.assertEqual(row["status"], "in_progress")
        self.assertEqual(row["owner"], "alpha")

        # The graph is a view; the claim store is the record it must agree with.
        self.assertEqual(self._owner("W01"), "alpha")
        # An unclaimed unit reports no owner rather than omitting the key.
        self.assertIsNone(self._graph()["W02"]["owner"])
        self.assertIsNone(self._owner("W02"))

    # (3) alpha holds W01; beta claims unblocked W02 -> succeeds without --force.
    def test_criterion_3_a_different_agents_claim_does_not_refuse_the_next(self):
        self.assertEqual(self._claim("W01", "alpha")[0], cli.OK)

        code, err = self._claim("W02", "beta")
        self.assertEqual(code, cli.OK, err)
        self.assertEqual(err, "")

        # Two live claims, two owners, two bands — the whole point of fanning out.
        self.assertEqual(self._owner("W01"), "alpha")
        self.assertEqual(self._owner("W02"), "beta")
        held = claims.all_claims(self.root)
        self.assertEqual(sorted(held), ["W01", "W02"])
        self.assertNotEqual(held["W01"]["band"], held["W02"]["band"])

    # (4) alpha holds W01; alpha claims W02 -> non-zero naming W01, OK with --force.
    def test_criterion_4_my_own_second_claim_is_refused_until_forced(self):
        self.assertEqual(self._claim("W01", "alpha")[0], cli.OK)

        code, err = self._claim("W02", "alpha")
        self.assertEqual(code, cli.FAIL)
        self.assertIn("W01", err)               # it names the unit standing in the way
        self.assertIsNone(self._owner("W02"))   # and took nothing

        code, err = self._claim("W02", "alpha", force=True)
        self.assertEqual(code, cli.OK, err)
        self.assertEqual(self._owner("W02"), "alpha")

    # (7) alpha holds W01; W01 goes done or blocked -> ownership released and any
    #     agent may claim it afterwards without --force.
    def test_criterion_7_a_terminal_transition_releases_ownership(self):
        for status in ("done", "blocked"):
            self.assertEqual(self._claim("W01", "alpha")[0], cli.OK, status)
            self.assertEqual(self._owner("W01"), "alpha", status)

            self.assertEqual(self._close("W01", "alpha", status=status)[0], cli.OK, status)
            self.assertIsNone(claims.read(self.root, "W01"), status)
            self.assertNotIn("W01", claims.all_claims(self.root), status)

            # "any agent": someone other than the one that just let it go.
            code, err = self._claim("W01", "gamma")
            self.assertEqual(code, cli.OK, "%s: %s" % (status, err))
            self.assertEqual(self._owner("W01"), "gamma", status)

            # Reset for the second pass through the loop.
            self._close("W01", "gamma", status="done")
            worklist.set_status(self.wl, "W01", "pending")

    # (8) W01 owned by an agent that is gone -> another agent's claim exits
    #     non-zero naming the stale owner and the override flag; with the
    #     override it succeeds and is journaled apart from an ordinary claim.
    def test_criterion_8_a_stale_claim_needs_a_named_override(self):
        self.assertEqual(self._claim("W01", "alpha")[0], cli.OK)
        self._abandon("W01")

        code, err = self._claim("W01", "beta")
        self.assertEqual(code, cli.FAIL)
        self.assertIn("alpha", err)     # who is holding it
        self.assertIn("--force", err)   # and how to get past them
        self.assertEqual(self._owner("W01"), "alpha")

        before = self._kinds()
        self.assertIn("CLAIM", before)
        self.assertNotIn("STEAL", before)

        code, err = self._claim("W01", "beta", force=True)
        self.assertEqual(code, cli.OK, err)
        self.assertEqual(self._owner("W01"), "beta")

        # Journaled distinctly: a takeover interrupted somebody, and that has to
        # be findable later without inferring it from a run of CLAIM lines.
        steals = [e for e in state.journal_entries(self.root) if e["kind"] == "STEAL"]
        self.assertEqual(len(steals), 1)
        self.assertIn("W01", steals[0]["detail"])
        self.assertIn("from alpha", steals[0]["detail"])
        self.assertIn("by beta", steals[0]["detail"])

    def _abandon(self, unit):
        """Age a claim into one whose worker is plainly no longer around.

        The claim itself never expires — that is the brief's stale-claim policy —
        so 'gone' is modelled the way the runtime would actually meet it: the file
        is still there, hours old, naming a pid on another machine.
        """
        path = paths.claim_path(self.root, unit)
        record = claims.read(self.root, unit)
        self.assertIsNotNone(record)
        record["pid"] = 999999
        record["host"] = "a-box-that-went-away"
        record["stamp"] = (datetime.datetime.now()
                           - datetime.timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S")
        paths.write_text(path, json.dumps(record, sort_keys=True))
        self.assertGreater(claims.age_seconds(claims.read(self.root, unit)), 3600)


class TestGatesFailOpenOnBrokenOwnership(ClaimBase):
    """W12 — a damaged claim store must never block a call, and never raise.

    Assumption 5 of the brief: a harness that bricks a session on its own bug is
    worse than no harness. `gate.dispatch` wraps every handler in a blanket
    `except`, so testing through it would prove only that the blanket exists.
    These call the handlers straight out of `gate.HANDLERS` instead, where a raise
    is visible and a wrong answer is not papered over.

    The setup is arranged so that fail-open is the *interesting* answer: alpha
    holds a `service` unit and the event writes to an `interface` path, which an
    intact store blocks. `test_the_baseline_really_blocks` is what keeps the rest
    of the class from passing vacuously.
    """

    ALL_HANDLERS = None  # set per-instance from gate.HANDLERS

    def setUp(self):
        super(TestGatesFailOpenOnBrokenOwnership, self).setUp()
        paths.write_text(paths.bands_map_path(self.root), json.dumps({
            "store": ["migrations/**"],
            "service": ["src/api/**"],
            "interface": ["src/ui/**"],
        }))
        state.set_active(self.root, self.bp)
        self.assertEqual(self._claim("W02", "alpha")[0], cli.OK)   # service band
        os.environ["BCX_AGENT_ID"] = "alpha"
        self.addCleanup(os.environ.pop, "BCX_AGENT_ID", None)
        # Comparing against the whole keyset is what makes "all handlers, not
        # only pre_write" hold even after somebody registers a sixth one.
        self.ALL_HANDLERS = {name: gate.ALLOW for name in gate.HANDLERS}

    def _event(self, path="src/ui/page.tsx"):
        return {"cwd": self.root,
                "tool_name": "Edit",
                "tool_input": {"file_path": os.path.join(self.root, path)}}

    def _every_handler(self, event=None):
        """Call every registered handler. A raise is recorded, not propagated.

        Recording it means the assertion failure names the handler and the
        exception instead of dumping a traceback from whichever one happened to
        go first.
        """
        event = self._event() if event is None else event
        results = {}
        out, err = io.StringIO(), io.StringIO()
        stdout, stderr = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = out, err
        try:
            for name, handler in sorted(gate.HANDLERS.items()):
                try:
                    results[name] = handler(self.root, event)
                except Exception as exc:                    # noqa: BLE001 - the point
                    results[name] = "raised %s: %s" % (type(exc).__name__, exc)
        finally:
            sys.stdout, sys.stderr = stdout, stderr
        return results

    def _assert_all_allow(self, note):
        self.assertEqual(self._every_handler(), self.ALL_HANDLERS, note)

    # ── the control ───────────────────────────────────────────────────────────

    def test_the_baseline_really_blocks(self):
        """Undamaged, this exact event is refused — so ALLOW below means something."""
        self.assertEqual(gate.current_band(self.root, "alpha"), "service")
        buf, stderr = io.StringIO(), sys.stderr
        sys.stderr = buf
        try:
            code = gate.pre_write(self.root, self._event())
        finally:
            sys.stderr = stderr
        self.assertEqual(code, gate.BLOCK)
        self.assertIn("interface", buf.getvalue())

    def test_every_handler_is_covered(self):
        """The suite asserts on the whole registry, not a hand-picked subset."""
        self.assertEqual(sorted(self._every_handler()), sorted(gate.HANDLERS))
        self.assertIn("pre-write", gate.HANDLERS)
        self.assertGreater(len(gate.HANDLERS), 1)

    # ── an unreadable claims directory ────────────────────────────────────────

    def test_all_allow_when_the_claims_directory_is_unreadable(self):
        d = paths.claims_dir(self.root)
        os.chmod(d, 0o000)
        self.addCleanup(os.chmod, d, 0o755)
        try:
            os.listdir(d)
        except OSError:
            pass
        else:
            self.skipTest("this process can read a 0o000 directory (running as root)")
        self._assert_all_allow("an unreadable claims directory must not enforce")

    def test_all_allow_when_the_claims_directory_is_not_a_directory(self):
        # The privilege-independent form of the same fault: every listdir here
        # fails with ENOTDIR no matter who is running the tests.
        d = paths.claims_dir(self.root)
        shutil.rmtree(d)
        paths.write_text(d, "not a directory\n")
        self._assert_all_allow("a claims path that is not a directory must not enforce")

    def test_all_allow_when_the_claims_directory_is_gone(self):
        shutil.rmtree(paths.claims_dir(self.root))
        self._assert_all_allow("a missing claims directory must not enforce")

    # ── a truncated claim file ────────────────────────────────────────────────

    def test_all_allow_on_a_truncated_claim_file(self):
        path = paths.claim_path(self.root, "W02")
        full = paths.read_text(path)
        self.assertIn("alpha", full)
        paths.write_text(path, full[:len(full) // 2])   # cut mid-JSON
        self.assertIsNone(claims.read(self.root, "W02"))
        self._assert_all_allow("a half-written claim must not enforce")

    def test_all_allow_on_an_empty_claim_file(self):
        paths.write_text(paths.claim_path(self.root, "W02"), "")
        self._assert_all_allow("a zero-byte claim must not enforce")

    def test_all_allow_on_a_claim_that_is_json_but_not_an_object(self):
        paths.write_text(paths.claim_path(self.root, "W02"), json.dumps(["alpha"]))
        self._assert_all_allow("a claim of the wrong shape must not enforce")

    # ── a band nobody declares ────────────────────────────────────────────────

    def _rename_band(self, unit, band):
        """Point both halves of the record for `unit` at `band`."""
        self.assertNotIn(band, paths.BANDS)
        paths.write_text(self.wl, PARALLEL_WORKLIST.replace(
            "### %s — Endpoint\n- Band: service" % unit,
            "### %s — Endpoint\n- Band: %s" % (unit, band)))
        worklist.set_status(self.wl, unit, "in_progress")
        record = claims.read(self.root, unit)
        record["band"] = band
        paths.write_text(paths.claim_path(self.root, unit),
                         json.dumps(record, sort_keys=True))

    def test_all_allow_when_the_claim_names_an_unknown_band(self):
        self._rename_band("W02", "quantum")
        self.assertEqual(claims.read(self.root, "W02")["band"], "quantum")
        self.assertEqual(gate.current_band(self.root, "alpha"), "quantum")
        self._assert_all_allow("an undeclared band maps to no paths — nothing to enforce")

    def test_all_allow_when_only_the_worklist_unit_names_an_unknown_band(self):
        # The record still says `service`; the worklist is what `current_band`
        # actually reads, so this half of the drift is the one that reaches the
        # path matcher.
        self.assertNotIn("quantum", paths.BANDS)
        paths.write_text(self.wl, PARALLEL_WORKLIST.replace(
            "### W02 — Endpoint\n- Band: service",
            "### W02 — Endpoint\n- Band: quantum"))
        worklist.set_status(self.wl, "W02", "in_progress")
        self.assertEqual(claims.read(self.root, "W02")["band"], "service")
        self._assert_all_allow("an undeclared band has no paths, so nothing to enforce")

    def test_a_bogus_band_in_the_record_alone_does_not_widen_the_gate(self):
        """Fail-open is not the same as fail-permissive.

        `current_band` takes the band from `worklist.md`, never from the claim
        record — the markdown is the source of truth and the record is auxiliary.
        So editing the record cannot talk the gate out of a band the worklist
        still asserts, which is what stops a writable state file from being a way
        around enforcement.
        """
        record = claims.read(self.root, "W02")
        record["band"] = "quantum"
        paths.write_text(paths.claim_path(self.root, "W02"),
                         json.dumps(record, sort_keys=True))
        self.assertEqual(gate.current_band(self.root, "alpha"), "service")
        buf, stderr = io.StringIO(), sys.stderr
        sys.stderr = buf
        try:
            self.assertEqual(gate.pre_write(self.root, self._event()), gate.BLOCK)
        finally:
            sys.stderr = stderr

    def test_all_allow_when_the_claim_is_missing_its_fields_entirely(self):
        paths.write_text(paths.claim_path(self.root, "W02"), json.dumps({}))
        self._assert_all_allow("a claim with no owner and no band must not enforce")


class TestVisibilitySurface(ClaimBase):
    """W16 — what `graph`, `next`, and `doctor` say about ownership."""

    def setUp(self):
        super(TestVisibilitySurface, self).setUp()
        state.set_active(self.root, self.bp)

    def _json(self, fn, argv):
        args = cli.build_parser().parse_args(argv)
        buf, stdout = io.StringIO(), sys.stdout
        sys.stdout = buf
        try:
            code = fn(self.root, args)
        finally:
            sys.stdout = stdout
        return code, json.loads(buf.getvalue())

    def _graph(self):
        return self._json(cli.cmd_graph, ["graph", "--json", "--blueprint", self.bp])[1]

    def _next(self):
        return self._json(cli.cmd_next, ["next", "--json", "--blueprint", self.bp])[1]

    def _routing(self, table):
        paths.write_text(paths.enforce_path(self.root), json.dumps({"routing": table}))

    def _doctor(self):
        return self._json(cli.cmd_doctor, ["doctor", "--json"])

    def _claims_problems(self):
        return [p for p in self._doctor()[1]["problems"] if p.startswith("claims: ")]

    # ── graph: owner ──────────────────────────────────────────────────────────

    def test_graph_reports_the_owner_of_a_claimed_unit(self):
        self._claim("W01", "alpha")
        rows = {u["id"]: u for u in self._graph()["units"]}
        self.assertEqual(rows["W01"]["owner"], "alpha")

    def test_graph_reports_null_for_an_unclaimed_unit(self):
        self._claim("W01", "alpha")
        rows = {u["id"]: u for u in self._graph()["units"]}
        self.assertIsNone(rows["W02"]["owner"])

    def test_graph_always_carries_the_owner_key(self):
        for unit in self._graph()["units"]:
            self.assertIn("owner", unit)

    def test_graph_ownership_comes_from_the_claim_store_not_the_markdown(self):
        # A status a human typed grants nobody ownership.
        worklist.set_status(self.wl, "W02", "in_progress")
        rows = {u["id"]: u for u in self._graph()["units"]}
        self.assertEqual(rows["W02"]["status"], "in_progress")
        self.assertIsNone(rows["W02"]["owner"])

    # ── next: routing ─────────────────────────────────────────────────────────

    def test_next_recommends_an_agent_per_band_when_routing_is_set(self):
        self._routing({"store": "codex", "service": "gemini"})
        ready = self._next()["ready"]
        self.assertEqual(ready["store"][0]["agent"], "codex")
        self.assertEqual(ready["service"][0]["agent"], "gemini")

    def test_next_omits_the_key_entirely_without_a_routing_table(self):
        self.assertFalse(os.path.exists(paths.enforce_path(self.root)))
        self.assertNotIn("agent", json.dumps(self._next()))

    def test_next_omits_the_key_for_an_explicitly_empty_table(self):
        self._routing({})
        self.assertNotIn("agent", json.dumps(self._next()))

    def test_next_is_unchanged_between_no_table_and_an_empty_one(self):
        without = json.dumps(self._next(), sort_keys=True)
        self._routing({})
        self.assertEqual(json.dumps(self._next(), sort_keys=True), without)

    def test_next_leaves_an_unmapped_band_without_a_key_and_without_an_error(self):
        self._routing({"store": "codex"})          # service is not mapped
        ready = self._next()["ready"]
        self.assertEqual(ready["store"][0]["agent"], "codex")
        self.assertNotIn("agent", ready["service"][0])

    # ── doctor: drift, one class at a time ────────────────────────────────────

    def test_a_clean_store_reports_no_drift(self):
        self._claim("W01", "alpha")
        self.assertEqual(cli._claim_drift(self.root, self.bp), [])
        self.assertEqual(self._claims_problems(), [])

    def test_drift_a_claim_on_a_unit_that_is_not_in_progress(self):
        self._claim("W01", "alpha")
        worklist.set_status(self.wl, "W01", "done")   # closed without releasing
        drift = cli._claim_drift(self.root, self.bp)
        self.assertEqual(len(drift), 1, drift)
        self.assertIn("W01", drift[0])
        self.assertIn("done", drift[0])

    def test_drift_a_claim_for_a_unit_absent_from_the_worklist(self):
        claims.acquire(self.root, "W99", owner="alpha", band="service")
        drift = cli._claim_drift(self.root, self.bp)
        self.assertEqual(len(drift), 1, drift)
        self.assertIn("W99", drift[0])
        self.assertIn("not in the worklist", drift[0])

    def test_drift_an_in_progress_unit_with_no_claim(self):
        worklist.set_status(self.wl, "W02", "in_progress")
        drift = cli._claim_drift(self.root, self.bp)
        self.assertEqual(len(drift), 1, drift)
        self.assertIn("W02", drift[0])
        self.assertIn("nothing claims it", drift[0])

    def test_drift_two_live_claims_sharing_one_owner(self):
        self._claim("W01", "alpha")
        self._claim("W02", "alpha", force=True)
        drift = cli._claim_drift(self.root, self.bp)
        self.assertEqual(len(drift), 1, drift)
        self.assertIn("alpha", drift[0])
        self.assertIn("W01, W02", drift[0])
        # The point of reporting it: enforcement is silently off in this state.
        self.assertIsNone(gate.current_band(self.root, "alpha"))

    def test_doctor_surfaces_drift_and_fails(self):
        worklist.set_status(self.wl, "W02", "in_progress")
        code, payload = self._doctor()
        self.assertEqual(code, cli.FAIL)
        self.assertTrue(any("W02" in p for p in payload["problems"]))
        self.assertFalse(payload["ok"])

    def test_drift_reporting_never_rewrites_either_file(self):
        self._claim("W01", "alpha")
        worklist.set_status(self.wl, "W01", "done")
        before_wl = paths.read_text(self.wl)
        before_claim = paths.read_text(paths.claim_path(self.root, "W01"))
        cli._claim_drift(self.root, self.bp)
        self._doctor()
        self.assertEqual(paths.read_text(self.wl), before_wl)
        self.assertEqual(paths.read_text(paths.claim_path(self.root, "W01")), before_claim)


BAND_BODY_SENTINEL = "ZZ-BAND-BODY-MUST-NOT-LEAK-ZZ"

SENTINEL_CONTEXT = """# Project Context

## Stack

- Languages: Python

## [band:store]

- Detail: %(s)s

## [band:service]

- Detail: %(s)s

## [band:interface]

- Detail: %(s)s

## [band:verify]

- Unit test framework: `python3 -m unittest -q`
""" % {"s": BAND_BODY_SENTINEL}


class TestJournalCarriesNoBandBody(ClaimBase):
    """A journal line may name a band. It must never quote one.

    `resume` builds the session-start digest out of these lines and Claude Code
    injects that as model-visible context. A band body reaching the journal would
    therefore defeat `gate.pre_read` from the inside — the model would receive
    the very text the read gate exists to withhold.

    The ownership lines added by this feature — CLAIM, STEAL, FREED — are built
    out of a unit id, a status, a band *name*, and an owner. This pins that
    distinction: the name is expected in the line, the body must never be.

    (Worded to avoid opening a line with `from`: the CI stdlib guard greps
    line-by-line and cannot tell prose from an import.)
    """

    def setUp(self):
        super(TestJournalCarriesNoBandBody, self).setUp()
        paths.write_text(paths.context_path(self.root), SENTINEL_CONTEXT)

    def _details(self, kinds):
        return [e["detail"] for e in state.journal_entries(self.root)
                if e["kind"] in kinds]

    def test_the_fixture_really_carries_the_sentinel(self):
        """Without this the assertions below could pass on an empty band."""
        for band in ("store", "service", "interface"):
            self.assertIn(BAND_BODY_SENTINEL, context.extract(self.root, band))

    def test_the_band_name_is_reported(self):
        """And without this they could pass on an empty journal."""
        self._claim("W01", "alpha")
        self.assertIn("(store)", self._details({"CLAIM"})[0])

    def test_no_ownership_line_carries_a_band_body(self):
        self._claim("W01", "alpha")                 # CLAIM
        self._claim("W01", "beta", force=True)      # STEAL, then CLAIM
        self._close("W01", "gamma")                 # DONE, then FREED
        details = self._details({"CLAIM", "STEAL", "FREED", "DONE"})
        self.assertEqual(len(details), 5, details)
        for detail in details:
            self.assertNotIn(BAND_BODY_SENTINEL, detail)

    def test_no_journal_line_at_all_carries_a_band_body(self):
        self._claim("W01", "alpha")
        self._claim("W01", "beta", force=True)
        self._close("W01", "gamma")
        for entry in state.journal_entries(self.root):
            self.assertNotIn(BAND_BODY_SENTINEL, entry["detail"], entry)

    def test_the_resume_digest_stays_clean_too(self):
        """The digest is the line that actually reaches a model."""
        state.set_active(self.root, self.bp)
        self._claim("W01", "alpha")
        self._claim("W01", "beta", force=True)
        self.assertNotIn(BAND_BODY_SENTINEL, "\n".join(resume.lines(self.root)))


WRAPPED_WORKLIST = """## Units

### W01 — A check that does not fit on one line
- Band: store
- Blocked by: —
- Check: the first line of the check, which continues onto
  a second line and then onto
  a third line

### W02 — An ordinary one
- Band: service
- Blocked by: W01
- Check: returns 201
"""

WRAPPED_CHECK = ("the first line of the check, which continues onto "
                 "a second line and then onto a third line")


class TestWrappedUnitFields(Base):
    """A field whose value wraps is still one field.

    Both halves of this were broken together: the parser stopped at the first
    line, and writing a status inserted it after that same line — which for a
    wrapped value is the middle of the field, not the end. Using the tool on
    itself is what surfaced it: the first `bcx claim` of a blueprint whose checks
    wrapped corrupted that blueprint's own worklist.
    """

    def setUp(self):
        super(TestWrappedUnitFields, self).setUp()
        paths.write_text(self.wl, WRAPPED_WORKLIST)

    def _unit(self, uid="W01"):
        return next(u for u in worklist.parse(paths.read_text(self.wl)) if u["id"] == uid)

    def test_a_wrapped_value_is_read_whole(self):
        self.assertEqual(self._unit()["check"], WRAPPED_CHECK)

    def test_a_status_lands_after_the_whole_field(self):
        worklist.set_status(self.wl, "W01", "in_progress")
        text = paths.read_text(self.wl)
        self.assertLess(text.index("a third line"), text.index("- Status:"))
        self.assertEqual(self._unit()["check"], WRAPPED_CHECK)

    def test_the_continuation_lines_keep_their_order(self):
        worklist.set_status(self.wl, "W01", "in_progress")
        text = paths.read_text(self.wl)
        self.assertLess(text.index("a second line"), text.index("a third line"))

    def test_a_wrapped_reason_is_removed_whole(self):
        worklist.set_status(self.wl, "W01", "blocked",
                            "a reason that takes\n  more than one line")
        self.assertIn("more than one line", paths.read_text(self.wl))
        worklist.set_status(self.wl, "W01", "pending")
        text = paths.read_text(self.wl)
        self.assertNotIn("Reason", text)
        self.assertNotIn("more than one line", text)
        self.assertEqual(self._unit()["check"], WRAPPED_CHECK)

    def test_replacing_a_wrapped_value_orphans_nothing(self):
        worklist.set_status(self.wl, "W01", "in_progress")
        worklist.set_status(self.wl, "W01", "done")
        text = paths.read_text(self.wl)
        self.assertEqual(text.count("- Status:"), 1)
        self.assertEqual(self._unit()["check"], WRAPPED_CHECK)

    def test_the_neighbouring_unit_is_untouched(self):
        worklist.set_status(self.wl, "W01", "done")
        self.assertEqual(self._unit("W02")["check"], "returns 201")
        self.assertEqual(self._unit("W02")["blocked_by"], ["W01"])

    def test_the_file_stays_schedulable(self):
        for status in ("in_progress", "done"):
            worklist.set_status(self.wl, "W01", status)
        units = worklist.parse(paths.read_text(self.wl))
        self.assertEqual(worklist.validate(units), [])
        self.assertEqual([u["id"] for u in worklist.ready(units)], ["W02"])

    def test_an_indented_list_item_is_not_swallowed_as_a_continuation(self):
        paths.write_text(self.wl, "## Units\n\n### C1 — x\n- Band: store\n"
                                  "- Check: a check\n  - a nested bullet\n")
        self.assertEqual(self._unit("C1")["check"], "a check")

    def test_single_line_units_are_unaffected(self):
        paths.write_text(self.wl, WORKLIST)
        before = paths.read_text(self.wl)
        worklist.set_status(self.wl, "W01", "in_progress")
        worklist.set_status(self.wl, "W01", "pending")
        after = paths.read_text(self.wl)
        self.assertEqual(worklist.parse(after)[0]["check"], "migration applies")
        self.assertEqual(after.count("- Status:"), 1)
        self.assertIn("### W02 — Endpoint", after)
        self.assertEqual(before.count("- Check:"), after.count("- Check:"))


class TestVersionAndBuildStamp(unittest.TestCase):
    """`bcx --version` has to distinguish two copies, not just name a release.

    The runtime is copied into every project, so three installs can report the
    same number while one is months behind. The stamp is what actually answers
    "which copy is this", and it is written at install time because the runtime
    cannot ask git itself — from inside a target project, git would answer about
    the target's history, not the kit's.
    """

    def setUp(self):
        self.runtime = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.runtime, "bcx_lib"))
        self._real = paths.runtime_dir
        paths.runtime_dir = lambda: self.runtime

    def tearDown(self):
        paths.runtime_dir = self._real
        shutil.rmtree(self.runtime, ignore_errors=True)

    def _write(self, text):
        with open(os.path.join(self.runtime, paths.BUILD_STAMP), "w", encoding="utf-8") as fh:
            fh.write(text)

    def test_the_version_is_a_three_part_number(self):
        self.assertRegex(cli.__version__, r"^\d+\.\d+\.\d+$")

    def test_no_stamp_gives_the_number_alone(self):
        self.assertEqual(cli.version_string(), "bcx %s" % cli.__version__)

    def test_a_stamp_is_reported_beside_the_number(self):
        self._write("abc1234 2026-08-24\n")
        self.assertEqual(cli.version_string(),
                         "bcx %s (abc1234 2026-08-24)" % cli.__version__)

    def test_an_empty_stamp_is_treated_as_absent(self):
        self._write("   \n")
        self.assertEqual(cli.version_string(), "bcx %s" % cli.__version__)

    def test_an_unreadable_stamp_does_not_raise(self):
        os.makedirs(os.path.join(self.runtime, paths.BUILD_STAMP))  # a directory
        self.assertIsNone(paths.build_stamp())
        self.assertEqual(cli.version_string(), "bcx %s" % cli.__version__)

    def test_a_dirty_stamp_survives_verbatim(self):
        # bootstrap marks an install made from a tree with uncommitted changes.
        self._write("abc1234-dirty 2026-08-24\n")
        self.assertIn("-dirty", cli.version_string())

    def test_the_stamp_lives_outside_the_module_directory(self):
        # Inside bcx_lib/ it would read as a drifted module to `stale_runtime`.
        self.assertEqual(os.path.dirname(
            os.path.join(paths.runtime_dir(), paths.BUILD_STAMP)), self.runtime)
        self.assertFalse(paths.BUILD_STAMP.endswith(".py"))


if __name__ == "__main__":
    unittest.main()
