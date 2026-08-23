"""Regression tests for the buildcli runtime.

Run from the runtime directory:
    python3 -m unittest discover -s tests -q
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bcli import context, gate, paths, state, verify, worklist  # noqa: E402

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


if __name__ == "__main__":
    unittest.main()
