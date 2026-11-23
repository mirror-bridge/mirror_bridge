#!/usr/bin/env python3
"""The runtime suite times HEAD and the baseline as two different modules.

run_runtime_benchmarks.py gives every framework its own interpreter and merges
what they report. The regression gate then divides the baseline's numbers by
HEAD's. Both builds are a module called `bench_mb`, told apart only by the
directory they are imported from, which leaves one mistake that would be
invisible: time HEAD's module under both labels, and the gate compares HEAD
with itself and passes for ever.

So this drives the real runner, child processes and all, against stand-in
modules written in Python -- the runner imports by name from a directory and
does not care that they are not compiled. A stand-in that is slow on one
operation has to come out slow under its own label and nowhere else, and a
baseline that is missing, broken or misplaced has to end up as a results file
the gate refuses, not as a silent comparison of something with itself.

MB_BENCH_SMOKE shrinks the iteration counts, so the timings here mean nothing
beyond "much slower" and nothing asserts more than that. No compiler needed.
"""
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
RUNNER = os.path.join(ROOT, "benchmarks", "runtime", "python", "run_runtime_benchmarks.py")
GATE = os.path.join(ROOT, "benchmarks", "check_ratios.py")

STAND_IN = textwrap.dedent("""
    import time

    class BenchmarkClass:
        def __init__(self):
            self.counter = 0
            self.data = []
            self.name = "bench"
        def null_call(self): {null_call}
        def add_int(self, x): return self.counter + x
        def multiply_double(self, x): return x * 2.0
        def concat_string(self, s): return self.name + s
        def get_string(self): return self.name
        def set_string(self, s): self.name = s
        def add_to_vector(self, x): self.data.append(x)
        def get_vector(self): return list(self.data)
        def set_vector(self, v): self.data = list(v)
""")

FAST = "pass"
SLOW = "time.sleep(0.0002)"
ROUNDS = 2


def write_module(directory, name, null_call=FAST, source=None):
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, name + ".py"), "w") as f:
        f.write(source if source is not None else STAND_IN.format(null_call=null_call))


class RuntimeProtocol(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.build = os.path.join(self.dir, "build")
        self.baseline = os.path.join(self.build, "gate_baseline")
        self.out = os.path.join(self.dir, "runtime_results.json")
        for name in ("bench_mb", "bench_pb", "bench_nb"):
            write_module(self.build, name)

    def run_suite(self, **extra_env):
        env = dict(os.environ,
                   MB_BENCH_BUILD=self.build,
                   MB_BENCH_BASELINE_BUILD=self.baseline,
                   MB_BENCH_RESULTS=self.out,
                   MB_BENCH_ROUNDS=str(ROUNDS),
                   MB_BENCH_SMOKE="1")
        env.pop("MB_BENCH_ONLY", None)
        env.update(extra_env)
        proc = subprocess.run([sys.executable, RUNNER, "run"],
                              capture_output=True, text=True, env=env)
        data = None
        if os.path.exists(self.out):
            with open(self.out) as f:
                data = json.load(f)
        return proc, data

    def gate(self, *flags):
        return subprocess.run([sys.executable, GATE, self.out, *flags],
                              capture_output=True, text=True)

    def test_head_and_baseline_are_both_measured_every_round(self):
        write_module(self.baseline, "bench_mb")
        proc, data = self.run_suite()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(data["_meta"]["baseline"]["measured"])
        self.assertEqual(sorted(data["mirror_bridge"]), sorted(data["mirror_bridge_baseline"]))
        for label in ("mirror_bridge", "mirror_bridge_baseline", "pybind11", "nanobind"):
            for op, per_round in data["_meta"]["rounds_ns"][label].items():
                self.assertEqual(len(per_round), ROUNDS, "%s %s" % (label, op))
                self.assertEqual(data[label][op], min(per_round),
                                 "the published number is not the fastest round")
        self.assertTrue(data["_meta"]["protocol"]["smoke"],
                        "a smoke run must be recognisable as one")
        # Which way the gate decides is not asserted: at smoke iteration counts
        # two identical stand-ins differ by more than any tolerance. That it
        # had a full set of pairs to decide on is the point.
        operations = len(data["mirror_bridge"])
        self.assertIn("compared %d of %d" % (operations, operations),
                      self.gate("--require-baseline").stdout)

    def test_each_label_is_timed_from_its_own_directory(self):
        """A slow HEAD must be slow as HEAD, and the baseline must not inherit it."""
        write_module(self.build, "bench_mb", null_call=SLOW)
        write_module(self.baseline, "bench_mb", null_call=FAST)
        proc, data = self.run_suite()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        head = data["mirror_bridge"]["null_call"]
        base = data["mirror_bridge_baseline"]["null_call"]
        self.assertGreater(head, base * 20,
                           "HEAD's slow null_call did not show up under HEAD's label")

        got = self.gate("--require-baseline")
        self.assertEqual(got.returncode, 1, got.stdout)
        verdict = got.stdout[got.stdout.index("REGRESSED beyond"):]
        self.assertIn("null_call", verdict)

    def test_a_slow_baseline_is_slow_as_the_baseline(self):
        write_module(self.build, "bench_mb", null_call=FAST)
        write_module(self.baseline, "bench_mb", null_call=SLOW)
        proc, data = self.run_suite()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertGreater(data["mirror_bridge_baseline"]["null_call"],
                           data["mirror_bridge"]["null_call"] * 20)

    def test_the_table_ignores_the_baseline(self):
        """It is the same library twice; a column for it would be noise."""
        write_module(self.baseline, "bench_mb")
        proc, _ = self.run_suite()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        page = subprocess.run(
            [sys.executable, os.path.join(ROOT, "benchmarks", "format_results.py"),
             self.out, "--fragment", "--strict"], capture_output=True, text=True)
        self.assertEqual(page.returncode, 0, page.stderr)
        self.assertNotIn("baseline", page.stdout)

    def test_no_baseline_module_still_publishes_and_the_gate_refuses(self):
        proc, data = self.run_suite()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("null_call", data["mirror_bridge"])
        self.assertNotIn("mirror_bridge_baseline", data)
        self.assertFalse(data["_meta"]["baseline"]["measured"])
        self.assertEqual(self.gate("--require-baseline").returncode, 1)
        self.assertEqual(self.gate().returncode, 0)

    def test_the_build_steps_reason_reaches_the_gate(self):
        os.makedirs(self.baseline)
        with open(os.path.join(self.baseline, "status.json"), "w") as f:
            json.dump({"commit": "ab" * 20, "reason": "did not compile with this toolchain"}, f)
        proc, data = self.run_suite()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(data["_meta"]["baseline"]["commit"], "ab" * 20)
        got = self.gate("--require-baseline")
        self.assertEqual(got.returncode, 1, got.stdout)
        self.assertIn("did not compile with this toolchain", got.stdout)
        self.assertIn("abababababab", got.stdout)

    def test_a_baseline_that_cannot_run_is_dropped_with_its_error(self):
        """For instance an operation added since: the old class has no such method."""
        broken = STAND_IN.format(null_call=FAST).replace("def add_int", "def add_integer")
        write_module(self.baseline, "bench_mb", source=broken)
        proc, data = self.run_suite()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertNotIn("mirror_bridge_baseline", data)
        self.assertNotIn("mirror_bridge_baseline", data["_meta"]["rounds_ns"])
        self.assertIn("add_int", data["_meta"]["baseline"]["reason"])
        self.assertEqual(self.gate("--require-baseline").returncode, 1)

    def test_a_module_that_prints_while_loading_does_not_derail_the_run(self):
        """The parent and each child talk over the child's stdout."""
        chatty = "print('hello from a module initialiser')\n" + STAND_IN.format(null_call=FAST)
        write_module(self.build, "bench_nb", source=chatty)
        write_module(self.baseline, "bench_mb")
        proc, data = self.run_suite()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(sorted(data["nanobind"]), sorted(data["mirror_bridge"]))

    def test_a_baseline_directory_that_is_heads_is_refused(self):
        proc, data = self.run_suite(MB_BENCH_BASELINE_BUILD=self.build)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertNotIn("mirror_bridge_baseline", data)
        self.assertEqual(self.gate("--require-baseline").returncode, 1)

    def test_a_missing_required_framework_fails_the_suite(self):
        os.unlink(os.path.join(self.build, "bench_pb.py"))
        proc, data = self.run_suite()
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIsNone(data, "a results file was written without pybind11 in it")


if __name__ == "__main__":
    unittest.main(verbosity=2)
