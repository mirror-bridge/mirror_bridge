#!/usr/bin/env python3
"""
Runtime Performance Benchmarks for Python Bindings
Compares Mirror Bridge, pybind11, nanobind, SWIG and Boost.Python, one
operation at a time, and measures Mirror Bridge against a baseline build of
itself for the regression gate in benchmarks/check_ratios.py.

How a number is taken, and why it is not simply "time each framework once":

  * One interpreter per framework. Timing them one after another in a single
    process made each reading depend on what ran before it: the heap, the
    allocator's arenas and the type cache all carry over. The trading suite
    measured that at up to 30% on the framework timed third.

  * The frameworks take turns, one sample each. All of a round's processes
    are alive at once and only one is ever running, so an operation is timed
    in every framework within a fraction of a second. A machine's speed
    changes from moment to moment (frequency scaling, a neighbour waking up);
    time framework A for a while and then B, and that change is reported as a
    difference between A and B. See wait_for_turn().

  * Several rounds, each with fresh processes, in alternating order. A
    process is one draw of address-space layout and allocator state, and
    only another process is another draw.

  * The minimum, per operation, over every sample of every round.
    Interference can only make a sample slower, so the fastest one is the
    best estimate of what the code costs. The median of five that this file
    used to report moved by 14-25% between two runs of identical code.

  * The collector is off while a sample is timed, so a collection triggered
    by one framework's garbage is not billed to the next sample.
"""

import gc
import importlib
import importlib.machinery
import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD_DIR = os.path.abspath(os.environ.get(
    "MB_BENCH_BUILD", os.path.join(HERE, '..', '..', '..', 'build')))
# The baseline is the same module under the same name (its init symbol is
# PyInit_bench_mb, like HEAD's), so it can only be told apart by where it is
# loaded from. run_all_benchmarks.sh builds it here.
BASELINE_BUILD = os.path.abspath(os.environ.get(
    "MB_BENCH_BASELINE_BUILD", os.path.join(BUILD_DIR, 'gate_baseline')))

# Iterations per timed sample. Sized so that a sample lasts tens of
# milliseconds: long enough that the timer and the loop setup are noise,
# short enough that some sample in a round usually runs without being
# interrupted, which is the one the minimum keeps. The string, vector and
# construction counts were first set lower, and those were the operations
# whose A/A readings disagreed most.
ITERATIONS = {
    'null_call': 1_000_000,
    'arithmetic': 1_000_000,
    'string': 500_000,
    'vector': 100_000,
    'attribute': 1_000_000,
    'construction': 500_000,
}

# Samples per operation inside one process, and processes per framework.
#
# ROUNDS is what buys stability: a process is one draw of address-space
# layout and allocator state, and only another process is another draw. With
# HEAD as its own baseline, the worst disagreement on any operation was 4.7%
# using the first five rounds, 3.6% using eight, 2.7% using twelve and 2.6%
# using all twenty (dev container, three runs; the per-operation numbers are
# next to the gate's tolerance in check_ratios.py).
#
# Twelve would do there. Twenty is for the runner, which is the noisier
# machine: the single pass this replaced varied by 10% between runs in that
# container and by 14-25% on GitHub's.
#
# Cost: twenty rounds of mirror_bridge, its baseline, pybind11, nanobind, SWIG
# and the harness floor took 4.6 minutes in the dev container, where a null
# call is 35 ns. The runner that published the 2026-10 table measured 74 ns
# for the same call, which puts this at about ten minutes there, against
# four and a half for the single pass it replaced.
#
# Re-measure before lowering anything here: the tolerance rests on it.
REPEATS = 5
ROUNDS = int(os.environ.get("MB_BENCH_ROUNDS", "20"))

# For exercising the plumbing (tests/benchmark_table/ does). The numbers a
# smoke run produces mean nothing, and the results file says it was one.
SMOKE = os.environ.get("MB_BENCH_SMOKE") == "1"
if SMOKE:
    ITERATIONS = {k: max(10, v // 2000) for k, v in ITERATIONS.items()}

HEAD = "mirror_bridge"
BASELINE = "mirror_bridge_baseline"
FLOOR = "_floor"

# label -> (module, directory it must be imported from)
TARGETS = {
    HEAD: ("bench_mb", BUILD_DIR),
    BASELINE: ("bench_mb", BASELINE_BUILD),
    "pybind11": ("bench_pb", BUILD_DIR),
    "nanobind": ("bench_nb", BUILD_DIR),
    "swig": ("bench_swig", BUILD_DIR),
    "boost_python": ("bench_bp", BUILD_DIR),
}
# Without these three there is no table to publish, so their absence is an
# error. The others are recorded only if they ran: a zero-filled placeholder
# would masquerade as a measurement in the saved JSON.
REQUIRED = (HEAD, "pybind11", "nanobind")

EXIT_NOT_IMPORTABLE = 3


# Set in a child process: the two ends of its conversation with the parent.
# None when this file is used on its own, and then nothing waits for anything.
_turn_requests = None
_turn_replies = None


def wait_for_turn():
    """Park until the parent says this process may take its next sample.

    This is what interleaves the frameworks sample by sample rather than
    process by process. Every target of a round is alive at once, each in its
    own interpreter, and exactly one of them is running: the parent hands the
    turn round the ring, one sample each. So the readings that get compared
    -- an operation at HEAD and the same operation at the baseline, above all
    -- are taken a few tens of milliseconds apart instead of seconds apart.

    The distance matters on a machine that is busy with something else.
    Measured with HEAD as its own baseline while another benchmark ran
    alongside: timed one process after the other, the two disagreed by a
    median of 2.3% per round and operation (7.2% at the ninetieth
    percentile), and in one run by 7% on one operation even after the fastest
    of twelve rounds was taken. Taking turns, 1.5% and 4.6%.
    """
    if _turn_requests is None:
        return
    _turn_replies.write("parked\n")
    _turn_replies.flush()
    if not _turn_requests.readline():
        raise SystemExit("the parent went away")


def benchmark(name, func, iterations):
    """Fastest ns per call over REPEATS samples, after a discarded warmup."""
    for _ in range(min(1000, iterations // 10)):
        func()

    best = None
    for _ in range(REPEATS):
        wait_for_turn()
        gc.collect()
        gc.disable()
        try:
            start = time.perf_counter()
            for _ in range(iterations):
                func()
            elapsed = time.perf_counter() - start
        finally:
            gc.enable()
        ns = elapsed * 1e9 / iterations
        if best is None or ns < best:
            best = ns
    return best

def measure_harness_floor():
    """What benchmark() costs before any binding code runs.

    Every number this suite publishes is `benchmark(name, lambda: ..., n)`,
    and benchmark calls func() in a Python loop. So each one carries a loop
    iteration plus a full Python function call on top of the operation. That
    constant is the same for all four frameworks, which means it does not
    cancel in a ratio -- it pushes every ratio toward 1.00. Publishing it is
    what lets a reader tell a 2% tie from a measurement artifact.

    Two floors, because one is not enough to correct with:
      empty      an empty lambda: the loop and the call, nothing else.
      c_call     the cheapest real C method call CPython can make, a
                 METH_NOARGS builtin. The gap between this and `empty` is
                 what any binding layer has to beat, and it is not zero.

    Kept out of the per-framework results on purpose: check_ratios.py treats
    every key in there as an operation to gate and to compare, and the floor
    is a property of the harness and the machine rather than of any
    framework. It is measured the way the frameworks are -- its own process,
    once per round -- so that it is a floor under the same protocol.
    """
    one = 1
    return {
        "empty": benchmark("floor_empty", lambda: None, ITERATIONS["null_call"]),
        "c_call": benchmark("floor_c_call", lambda: one.bit_length(),
                            ITERATIONS["null_call"]),
    }


def run_benchmarks(module_name, obj_class):
    """Run all benchmarks on a module"""
    results = {}

    # Create test object
    obj = obj_class()

    # 1. Null call overhead
    results['null_call'] = benchmark(
        'null_call',
        lambda: obj.null_call(),
        ITERATIONS['null_call']
    )

    # 2. Arithmetic - int
    results['arithmetic_int'] = benchmark(
        'arithmetic_int',
        lambda: obj.add_int(42),
        ITERATIONS['arithmetic']
    )

    # 3. Arithmetic - double
    results['arithmetic_double'] = benchmark(
        'arithmetic_double',
        lambda: obj.multiply_double(3.14),
        ITERATIONS['arithmetic']
    )

    # 4. String operations - concatenate
    results['string_concat'] = benchmark(
        'string_concat',
        lambda: obj.concat_string("_test"),
        ITERATIONS['string']
    )

    # 5. String operations - get
    results['string_get'] = benchmark(
        'string_get',
        lambda: obj.get_string(),
        ITERATIONS['string']
    )

    # 6. String operations - set
    results['string_set'] = benchmark(
        'string_set',
        lambda: obj.set_string("benchmark"),
        ITERATIONS['string']
    )

    # 7. Vector operations - append
    try:
        obj.data = []  # Reset (works for pybind11/nanobind/Mirror Bridge)
    except (TypeError, AttributeError):
        # SWIG doesn't support direct assignment, use method instead
        obj.set_vector([])
    results['vector_append'] = benchmark(
        'vector_append',
        lambda: obj.add_to_vector(1.0),
        ITERATIONS['vector']
    )

    # 8. Vector operations - get
    try:
        obj.data = [1.0] * 100  # Works for pybind11/nanobind/Mirror Bridge
    except (TypeError, AttributeError):
        # SWIG doesn't support direct assignment
        obj.set_vector([1.0] * 100)
    results['vector_get'] = benchmark(
        'vector_get',
        lambda: obj.get_vector(),
        ITERATIONS['vector']
    )

    # 9. Vector operations - set
    test_vec = [1.0, 2.0, 3.0, 4.0, 5.0]
    results['vector_set'] = benchmark(
        'vector_set',
        lambda: obj.set_vector(test_vec),
        ITERATIONS['vector']
    )

    # 10. Attribute access - get
    results['attr_get'] = benchmark(
        'attr_get',
        lambda: obj.counter,
        ITERATIONS['attribute']
    )

    # 11. Attribute access - set
    #
    # Assigns a constant. The previous version incremented a list element and
    # read it back on every iteration -- `obj.counter = counter[0];
    # counter[0] += 1` -- so a list subscript load, a subscript store and an
    # int add were inside the number published as "Attribute write". Measured
    # at roughly a third of it. The written value does not change what a
    # setter costs: there is no caching on the way in.
    def set_attr():
        obj.counter = 1
    results['attr_set'] = benchmark(
        'attr_set',
        set_attr,
        ITERATIONS['attribute']
    )

    # 12. Object construction
    results['construction'] = benchmark(
        'construction',
        lambda: obj_class(),
        ITERATIONS['construction']
    )

    return results

def format_time(ns):
    """Format time in appropriate unit"""
    if ns < 1000:
        return f"{ns:.1f} ns"
    elif ns < 1_000_000:
        return f"{ns/1000:.1f} µs"
    else:
        return f"{ns/1_000_000:.1f} ms"

def print_results(results_mb, results_pb, results_nb, results_swig, results_bp):
    """Print comparison table"""
    benchmarks = [
        ('Null call', 'null_call'),
        ('Add int', 'arithmetic_int'),
        ('Multiply double', 'arithmetic_double'),
        ('Concat string', 'string_concat'),
        ('Get string', 'string_get'),
        ('Set string', 'string_set'),
        ('Vector append', 'vector_append'),
        ('Vector get', 'vector_get'),
        ('Vector set', 'vector_set'),
        ('Attr get', 'attr_get'),
        ('Attr set', 'attr_set'),
        ('Construction', 'construction'),
    ]

    print("\n" + "="*120)
    print(" Runtime Performance Benchmarks (lower is better)")
    print("="*120)
    print(f"\n{'Benchmark':<20} {'MB':<12} {'pybind11':<12} {'nanobind':<12} {'SWIG':<12} {'Boost.Py':<12} {'vs pb11':<10}")
    print("-"*120)

    for name, key in benchmarks:
        mb = results_mb[key]
        pb = results_pb[key]
        nb = results_nb[key]
        sw = results_swig[key] if results_swig else None
        bp = results_bp[key] if results_bp else None
        ratio_pb = mb / pb if pb > 0 else 0
        marker = "✓" if ratio_pb <= 1.1 else ("⚠" if ratio_pb <= 1.5 else "✗")

        swig_str = format_time(sw) if sw else "N/A"
        bp_str = format_time(bp) if bp else "N/A"

        print(f"{name:<20} {format_time(mb):<12} {format_time(pb):<12} {format_time(nb):<12} {swig_str:<12} {bp_str:<12} {ratio_pb:.2f}x {marker}")

    print("\n" + "="*120)
    print("Legend: ✓ within 10%  |  ⚠ within 50%  |  ✗ slower than 50%  |  N/A = not available")
    print("="*120)


def time_one_target(label):
    """Child process: time a single target, one sample per turn it is given."""
    global _turn_requests, _turn_replies
    # The parent reads this process's stdout a line at a time, so keep it for
    # that conversation and send anything a module prints while loading to
    # stderr instead.
    _turn_replies = os.fdopen(os.dup(1), "w")
    os.dup2(2, 1)
    _turn_requests = sys.stdin

    if label == FLOOR:
        numbers = measure_harness_floor()
    else:
        module_name, where = TARGETS[label]
        sys.path.insert(0, where)
        try:
            module = importlib.import_module(module_name)
        except ImportError as why:
            print(f"{module_name} is not importable from {where}: {why}", file=sys.stderr)
            return EXIT_NOT_IMPORTABLE

        # HEAD and the baseline are both `bench_mb`. If the baseline's
        # directory held no module and the import fell through to HEAD's, the
        # gate would compare HEAD with itself and pass forever, so check which
        # file answered.
        if module_name == "bench_mb":
            loaded_from = os.path.dirname(os.path.realpath(module.__file__))
            if loaded_from != os.path.realpath(where):
                print(f"{label}: bench_mb was imported from {loaded_from}, "
                      f"not from {where}", file=sys.stderr)
                return 1

        numbers = run_benchmarks(module_name, module.BenchmarkClass)

    _turn_replies.write("done " + json.dumps(numbers) + "\n")
    _turn_replies.flush()
    return 0


class Child:
    """One target in a fresh interpreter, advanced one sample at a time."""

    def __init__(self, label):
        self.label = label
        # A file rather than a pipe: nobody reads stderr until the child has
        # exited, and a full pipe would block it in the middle of a sample.
        self.stderr = tempfile.TemporaryFile(mode="w+")
        self.proc = subprocess.Popen(
            [sys.executable, os.path.abspath(__file__), "run"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr,
            text=True, env=dict(os.environ, MB_BENCH_ONLY=label))
        self.numbers = None

    def next_line(self):
        """Read the child's next message: True if it parked, False if it is finished.

        A child that exits without reporting leaves `numbers` as None.
        """
        line = self.proc.stdout.readline()
        if line.startswith("parked"):
            return True
        if line.startswith("done "):
            try:
                self.numbers = json.loads(line[len("done "):])
            except ValueError:
                pass
        return False

    def take_a_turn(self):
        """Let the parked child take one sample; True if it parked again."""
        try:
            self.proc.stdin.write("go\n")
            self.proc.stdin.flush()
        except OSError:
            return False
        return self.next_line()

    def finish(self):
        """Reap the child. Returns (exit code, numbers, stderr)."""
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        rc = self.proc.wait()
        self.proc.stdout.close()
        self.stderr.seek(0)
        err = self.stderr.read().strip()
        self.stderr.close()
        if rc == 0 and self.numbers is None:
            rc, err = 1, "exited without reporting any numbers. " + err
        return rc, self.numbers, err


def run_round(order):
    """Time every target in `order` once. Returns {label: (exit code, numbers, stderr)}.

    All of them are started first and left to import their module and park,
    so that no process is still loading while another is being timed. Then
    the turn goes round in `order` until each has finished; see
    wait_for_turn() for why it is one sample at a time.
    """
    children = [Child(label) for label in order]
    running = [child for child in children if child.next_line()]
    while running:
        running = [child for child in running if child.take_a_turn()]
    return {child.label: child.finish() for child in children}


def fastest(rounds):
    """{operation: [ns per round]} -> {operation: fastest ns}"""
    return {op: min(samples) for op, samples in rounds.items()}


def baseline_status():
    """What run_all_benchmarks.sh recorded about the baseline build, if anything.

    Returns (commit, reason it cannot be measured or None).
    """
    recorded = {}
    try:
        with open(os.path.join(BASELINE_BUILD, "status.json")) as f:
            recorded = json.load(f)
    except (OSError, ValueError):
        pass
    commit = recorded.get("commit")
    if BASELINE_BUILD == BUILD_DIR:
        return commit, "the baseline directory is HEAD's build directory"
    module_name = TARGETS[BASELINE][0]
    if importlib.machinery.PathFinder.find_spec(module_name, [BASELINE_BUILD]) is None:
        return commit, recorded.get("reason") or (
            "no baseline module was built in %s" % BASELINE_BUILD)
    return commit, None


def run_all():
    baseline_commit, baseline_problem = baseline_status()

    active = [HEAD]
    if baseline_problem is None:
        # Next to HEAD in the ring, so the two samples the gate divides are
        # taken one straight after the other.
        active.append(BASELINE)
    else:
        print(f"Baseline will not be measured: {baseline_problem}")
    active += ["pybind11", "nanobind", "swig", "boost_python", FLOOR]

    samples = {}  # label -> operation -> [ns, one per round]
    started = time.time()
    for rnd in range(ROUNDS):
        order = list(active) if rnd % 2 == 0 else list(reversed(active))
        print(f"Round {rnd + 1}/{ROUNDS}: " + ", ".join(order), flush=True)
        for label, (rc, numbers, err) in run_round(order).items():
            if rc == 0:
                for op, ns in numbers.items():
                    samples.setdefault(label, {}).setdefault(op, []).append(ns)
                continue

            if label == BASELINE:
                # A baseline that cannot be measured must not stop the table
                # from being published; the gate is what fails for it. Drop
                # the rounds already taken too: the tolerance was calibrated
                # on full runs.
                baseline_problem = "the baseline module did not run: " + (
                    err.splitlines()[-1] if err else "exit code %d" % rc)
                print(f"  {baseline_problem}")
                active.remove(BASELINE)
                samples.pop(BASELINE, None)
            elif label not in REQUIRED and label != FLOOR \
                    and rnd == 0 and rc == EXIT_NOT_IMPORTABLE:
                print(f"  {label} module not available, skipping...")
                active.remove(label)
            else:
                print(f"Error: {label} failed in round {rnd + 1}: {err}")
                if rc == EXIT_NOT_IMPORTABLE:
                    print("Please run the compile-time benchmarks first to build the modules.")
                sys.exit(1)

    merged = {label: fastest(rounds) for label, rounds in samples.items()}
    floor = merged.pop(FLOOR)

    print_results(merged[HEAD], merged["pybind11"], merged["nanobind"],
                  merged.get("swig"), merged.get("boost_python"))
    print("Harness floor: empty lambda %.1f ns, cheapest C call %.1f ns"
          % (floor["empty"], floor["c_call"]))

    baseline = {"commit": baseline_commit, "measured": BASELINE in merged}
    if baseline_problem is not None:
        baseline["reason"] = baseline_problem

    payload = {
        '_meta': {
            'harness_floor_ns': floor,
            'protocol': {
                'rounds': ROUNDS,
                'repeats': REPEATS,
                'iterations': ITERATIONS,
                'smoke': SMOKE,
                'seconds': round(time.time() - started, 1),
            },
            'baseline': baseline,
            # Every round's reading, not only the fastest: when the gate
            # fires, this is what shows whether one round or all of them
            # were slow.
            'rounds_ns': {label: rounds for label, rounds in samples.items()
                          if label != FLOOR},
        },
    }
    for label in TARGETS:
        if label in merged:
            payload[label] = merged[label]

    out = os.environ.get("MB_BENCH_RESULTS", os.path.join(HERE, 'runtime_results.json'))
    with open(out, 'w') as f:
        json.dump(payload, f, indent=2)
    print(f"\nResults saved to {out}")
    return 0


if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] != 'run':
        print("Usage: python3 run_runtime_benchmarks.py run")
        print("  MB_BENCH_ROUNDS=N  processes per framework (default %d)" % ROUNDS)
        sys.exit(1)

    only = os.environ.get("MB_BENCH_ONLY")
    sys.exit(time_one_target(only) if only else run_all())
