#!/usr/bin/env python3
"""The regression gate compares mirror_bridge with itself, and says when it did not.

benchmarks/check_ratios.py turns the benchmark run into a check. The suite
times two builds of the benchmark module in the same job -- HEAD, and the
commit named in benchmarks/gate_baseline.json -- and the gate fails when an
operation is slower at HEAD by more than its tolerance.

It used to compare against competitors instead: a committed floor under the
ratio to pybind11. That failed on every run without mirror_bridge changing,
because the ratio to a competitor moves with the runner's CPU and with the
competitor's releases. So two things are pinned here that were not before:

  * a competitor getting faster, or being faster, is never a failure
  * a slowdown of mirror_bridge against its own baseline always is

And one thing is kept from the old gate, because it was learned the hard way:
a run that compared nothing must not read like a run that passed. There are
several routes to comparing nothing -- no baseline numbers, a baseline that
could not be built, a baseline with no operation in common, a baseline that
covers only some operations -- and --require-baseline, which CI passes, has to
fail on each of them.

No compiler and no benchmark run needed.
"""
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
GATE = os.path.join(ROOT, "benchmarks", "check_ratios.py")
POINTER = os.path.join(ROOT, "benchmarks", "gate_baseline.json")
WORKFLOW = os.path.join(ROOT, ".github", "workflows", "benchmarks.yml")

OPERATIONS = ["null_call", "arithmetic_int", "vector_get", "attr_get", "construction"]
COMMIT = "0123456789abcdef0123456789abcdef01234567"


def _tolerance():
    """The shipped tolerance, read from the gate rather than copied here."""
    spec = importlib.util.spec_from_file_location("gate_probe", GATE)
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    return gate.DEFAULT_TOLERANCE


TOLERANCE = _tolerance()


def results(head_ns=50.0, baseline_ns=50.0, competitor_ns=140.0, slow=None):
    """A results file as the runner writes it. `slow` maps operation -> factor
    applied to HEAD only, which is what a regression looks like."""
    head = {op: head_ns * (slow or {}).get(op, 1.0) for op in OPERATIONS}
    data = {
        "_meta": {"baseline": {"commit": COMMIT, "measured": baseline_ns is not None}},
        "mirror_bridge": head,
        "pybind11": {op: competitor_ns for op in OPERATIONS},
        "nanobind": {op: head_ns * 1.1 for op in OPERATIONS},
    }
    if baseline_ns is not None:
        data["mirror_bridge_baseline"] = {op: baseline_ns for op in OPERATIONS}
    return data


class RegressionGate(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def gate(self, data, *flags, env=None):
        path = os.path.join(self.dir, "results.json")
        with open(path, "w") as f:
            if isinstance(data, str):
                f.write(data)
            else:
                json.dump(data, f)
        run_env = dict(os.environ)
        run_env.pop("GITHUB_ACTIONS", None)
        run_env.update(env or {})
        return subprocess.run([sys.executable, GATE, path, *flags],
                              capture_output=True, text=True, env=run_env)

    # --- it passes when it should -----------------------------------------

    def test_head_matching_its_baseline_passes(self):
        got = self.gate(results(), "--require-baseline")
        self.assertEqual(got.returncode, 0, got.stdout)
        self.assertIn("compared %d of %d" % (len(OPERATIONS), len(OPERATIONS)), got.stdout)
        self.assertIn(COMMIT[:12], got.stdout)
        self.assertIn("No operation regressed", got.stdout)

    def test_an_improvement_passes(self):
        got = self.gate(results(head_ns=30.0), "--require-baseline")
        self.assertEqual(got.returncode, 0, got.stdout)

    def test_a_slowdown_inside_the_tolerance_passes(self):
        # baseline/head sits just above 1 - tolerance.
        factor = 1.0 / (1.0 - TOLERANCE * 0.8)
        got = self.gate(results(slow={"attr_get": factor}), "--require-baseline")
        self.assertEqual(got.returncode, 0, got.stdout)

    # --- it fails when it should ------------------------------------------

    def test_a_slowdown_past_the_tolerance_fails_and_names_the_operation(self):
        factor = 1.0 / (1.0 - TOLERANCE * 1.2)
        got = self.gate(results(slow={"attr_get": factor}), "--require-baseline")
        self.assertEqual(got.returncode, 1, got.stdout)
        verdict = got.stdout[got.stdout.index("REGRESSED beyond"):]
        self.assertIn("attr_get", verdict)
        for untouched in set(OPERATIONS) - {"attr_get"}:
            self.assertNotIn(untouched, verdict)

    def test_a_regression_fails_without_the_strict_flag_too(self):
        got = self.gate(results(slow={"construction": 1.5}))
        self.assertEqual(got.returncode, 1, got.stdout)
        self.assertIn("REGRESSED", got.stdout)

    def test_a_regression_shows_every_round_of_both_builds(self):
        """One slow round is the machine; all of them slow is the code."""
        data = results(slow={"null_call": 1.5})
        data["_meta"]["rounds_ns"] = {
            "mirror_bridge": {"null_call": [76.5, 75.0, 75.3]},
            "mirror_bridge_baseline": {"null_call": [50.0, 51.5, 50.3]},
        }
        got = self.gate(data, "--require-baseline")
        self.assertEqual(got.returncode, 1, got.stdout)
        self.assertIn("76.5 75.0 75.3", got.stdout)
        self.assertIn("50.0 51.5 50.3", got.stdout)

    # --- competitors are reported, never gated ----------------------------

    def test_a_competitor_getting_faster_is_not_a_regression(self):
        """The whole reason the gate stopped comparing against competitors."""
        got = self.gate(results(competitor_ns=70.0), "--require-baseline")
        self.assertEqual(got.returncode, 0, got.stdout)

    def test_being_slower_than_a_competitor_is_reported_not_failed(self):
        got = self.gate(results(head_ns=200.0, baseline_ns=200.0, competitor_ns=140.0),
                        "--require-baseline")
        self.assertEqual(got.returncode, 0, got.stdout)
        self.assertIn("Slower than a competitor", got.stdout)
        self.assertIn("pybind11", got.stdout)

    def test_the_baseline_is_not_listed_as_a_competitor(self):
        got = self.gate(results(head_ns=60.0, baseline_ns=57.0), "--require-baseline")
        self.assertEqual(got.returncode, 0, got.stdout)
        self.assertNotIn("Slower than a competitor", got.stdout)

    # --- comparing nothing is not passing ---------------------------------

    def test_no_baseline_numbers_fail_under_require_baseline(self):
        got = self.gate(results(baseline_ns=None), "--require-baseline")
        self.assertEqual(got.returncode, 1, got.stdout)
        self.assertIn("no operation was gated", got.stdout)
        self.assertNotIn("No operation regressed", got.stdout)

    def test_no_baseline_numbers_without_the_flag_exit_zero_but_say_so(self):
        got = self.gate(results(baseline_ns=None))
        self.assertEqual(got.returncode, 0, got.stdout)
        self.assertIn("no operation was gated", got.stdout)
        self.assertNotIn("No operation regressed", got.stdout)

    def test_the_reason_the_baseline_is_missing_is_printed(self):
        data = results(baseline_ns=None)
        data["_meta"]["baseline"]["reason"] = "commit could not be fetched from origin"
        got = self.gate(data, "--require-baseline")
        self.assertEqual(got.returncode, 1, got.stdout)
        self.assertIn("commit could not be fetched from origin", got.stdout)
        self.assertIn(COMMIT[:12], got.stdout)

    def test_a_null_empty_or_zeroed_baseline_does_not_pass(self):
        for broken in (None, {}, [], {op: 0 for op in OPERATIONS},
                       {op: None for op in OPERATIONS}):
            data = results()
            data["mirror_bridge_baseline"] = broken
            got = self.gate(data, "--require-baseline")
            self.assertEqual(got.returncode, 1, "%r passed:\n%s" % (broken, got.stdout))
            self.assertNotIn("Traceback", got.stderr)
            self.assertNotIn("No operation regressed", got.stdout)

    def test_a_baseline_with_nothing_in_common_does_not_pass(self):
        data = results()
        data["mirror_bridge_baseline"] = {"attribute_get": 50.0, "vector_sum": 50.0}
        got = self.gate(data, "--require-baseline")
        self.assertEqual(got.returncode, 1, got.stdout)
        self.assertIn("compared 0 of %d" % len(OPERATIONS), got.stdout)
        self.assertIn("no operation was gated", got.stdout)

    def test_an_operation_the_baseline_lacks_is_named_and_fails_strict(self):
        data = results()
        del data["mirror_bridge_baseline"]["vector_get"]
        strict = self.gate(data, "--require-baseline")
        self.assertEqual(strict.returncode, 1, strict.stdout)
        self.assertIn("not gated", strict.stdout)
        self.assertIn("vector_get", strict.stdout)
        self.assertNotIn("No operation regressed", strict.stdout)

        lenient = self.gate(data)
        self.assertEqual(lenient.returncode, 0, lenient.stdout)
        self.assertIn("vector_get", lenient.stdout)
        self.assertNotIn("No operation regressed", lenient.stdout)

    def test_an_unarmed_gate_raises_a_workflow_warning(self):
        got = self.gate(results(baseline_ns=None), "--require-baseline",
                        env={"GITHUB_ACTIONS": "true"})
        self.assertIn("::warning", got.stdout)

    # --- bad input ----------------------------------------------------------

    def test_a_corrupt_results_file_says_so_rather_than_tracebacking(self):
        got = self.gate("this is not json", "--require-baseline")
        self.assertNotEqual(got.returncode, 0)
        self.assertNotIn("Traceback", got.stderr)
        self.assertIn("cannot read", got.stderr)

    def test_results_without_mirror_bridge_numbers_do_not_pass(self):
        data = results()
        del data["mirror_bridge"]
        got = self.gate(data, "--require-baseline")
        self.assertNotEqual(got.returncode, 0)
        self.assertNotIn("Traceback", got.stderr)


class BaselinePointer(unittest.TestCase):
    def test_the_committed_baseline_is_a_full_commit_id(self):
        """The suite fetches it by SHA, and a server only answers a full one."""
        with open(POINTER) as f:
            commit = json.load(f)["commit"]
        self.assertRegex(commit, r"\A[0-9a-f]{40}\Z")

    def test_ci_runs_the_gate_strict(self):
        """Without the flag, a baseline that failed to build is a green job."""
        with open(WORKFLOW) as f:
            workflow = f.read()
        calls = re.findall(r"python3 benchmarks/check_ratios\.py(?:[^\n]*\\\n)*[^\n]*", workflow)
        self.assertTrue(calls, "the workflow no longer runs check_ratios.py")
        for call in calls:
            self.assertIn("--require-baseline", call)


if __name__ == "__main__":
    unittest.main(verbosity=2)
