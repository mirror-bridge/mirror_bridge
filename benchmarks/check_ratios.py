#!/usr/bin/env python3
"""Gate mirror_bridge's runtime numbers against a baseline build of itself.

The benchmarks page is regenerated monthly, but nothing read it: a regression
could land and sit in a table for a month. This turns the same run into a
check.

Two distinct things, kept distinct on purpose:

  * **Regression** is a failure, and it is measured against mirror_bridge
    itself: the suite builds the benchmark module a second time from the
    commit named in gate_baseline.json and times both builds in the same job,
    interleaved, on the same machine. An operation that takes more than the
    tolerance longer at HEAD than at the baseline fails the build.

    It used to be measured against competitors: the ratio to pybind11 had a
    committed floor. That gate failed every run it was armed for without
    mirror_bridge changing, because such a ratio also moves when the runner's
    CPU changes and when the competitor ships a faster release (the ratio to
    pybind11 fell 22% across two refreshes while the ratio to nanobind
    held). "We got slower" and "they got faster" are indistinguishable in a
    ratio between the two, so the question is now asked of the only pair of
    numbers where everything but our own code is held constant.

  * **Being behind** is reported, not failed. Where a competitor is faster, the
    output says so and by how much. That is the honest form of "at least as
    fast as any alternative": a list of the operations where it is not yet
    true, rather than a claim that it is.

Absolute ns/op moves with the machine, so only same-run numbers are compared.
"""

import argparse
import json
import os
import re
import sys

HEAD = "mirror_bridge"
BASELINE = "mirror_bridge_baseline"
COMPETITORS = ["pybind11", "nanobind", "swig", "boost_python"]

# How far baseline_ns / head_ns may fall below 1.00 before it is a regression.
#
# Set from A/A runs: the whole suite with HEAD as its own baseline, so that
# every deviation is the instrument's and none is the code's. Three runs at
# the shipped protocol in the arm64 dev container, while another job was
# compiling on the same machine. Largest |baseline/head - 1| seen for each
# operation:
#
#     null_call          1.7%     string_get      2.4%     vector_set    0.6%
#     arithmetic_int     1.5%     string_set      0.5%     attr_get      0.9%
#     arithmetic_double  0.5%     vector_append   2.6%     attr_set      0.4%
#     string_concat      2.6%     vector_get      1.4%     construction  0.9%
#
# Worst 2.6%, root mean square 1.2%. Cut off after fewer rounds the same
# runs give 4.7% (5 rounds), 3.6% (8), 2.7% (12) and 2.6% (20). With a
# second benchmark deliberately running alongside, three more runs of twelve
# rounds: 3.1%.
#
# Not all of that is timing noise. string_concat and string_get read 1.7-2.6%
# slower in the baseline in every one of the first three runs, from the same
# bytes. The likeliest cause is that the two modules are loaded from paths of
# different length, which shifts where things land in memory: with the paths
# made equal in length, a run of eight rounds read 0.3% and 0.5%. A real
# baseline is a different binary and brings bias of that kind with it, so it
# is left in the calibration rather than engineered out.
#
# 8% is three times the worst reading. The room is for the runner, which is
# not that container: the single-pass protocol this suite used to have moved
# mirror_bridge's own numbers by up to 10% between runs there and by 14-25%
# on GitHub's. Until the gate has run on that hardware a few times, its noise
# under this protocol is an estimate.
#
# What that costs: a slowdown under 8% passes. A delay of about 2 ns put
# into the attribute getter on purpose was measured as 0.955x, with the other
# eleven operations between 0.984x and 1.032x, and passed; a larger one,
# 0.841x, failed and named attr_get alone. A slowdown that small is not
# forgiven, though: the baseline does not move by itself, so the next one is
# measured on top of it.
#
# To re-measure, point the baseline at HEAD's own tree and run the suite:
#     MB_GATE_BASELINE_ROOT=$PWD ./benchmarks/run_all_benchmarks.sh
DEFAULT_TOLERANCE = 0.08


def usable(ns):
    return isinstance(ns, (int, float)) and ns > 0


def measured(data, framework):
    """{operation: ns} for one framework, keeping only real measurements."""
    block = data.get(framework)
    if not isinstance(block, dict):
        return {}
    return {op: ns for op, ns in block.items() if usable(ns)}


def measured_rounds(rounds, framework, op):
    """One operation's reading in each round, or [] if the file has none."""
    block = rounds.get(framework)
    per_round = block.get(op) if isinstance(block, dict) else None
    if not isinstance(per_round, list):
        return []
    return [ns for ns in per_round if usable(ns)]


def ratios(data):
    """{operation: {competitor: competitor_ns / mirror_bridge_ns}}"""
    competitors = {fw: measured(data, fw) for fw in COMPETITORS}
    out = {}
    for op, mb_ns in measured(data, HEAD).items():
        row = {fw: ns[op] / float(mb_ns) for fw, ns in competitors.items() if op in ns}
        if row:
            out[op] = row
    return out


def describe_baseline(data):
    """(short name of what HEAD was compared against, why it is missing or None)"""
    recorded = (data.get("_meta") or {}).get("baseline") or {}
    commit = recorded.get("commit")
    if not isinstance(commit, str) or not commit:
        name = "the baseline"
    elif re.fullmatch("[0-9a-f]{40}", commit):
        name = "baseline %s" % commit[:12]
    else:
        # MB_GATE_BASELINE_ROOT: a local tree rather than a commit.
        name = "baseline (%s)" % commit
    if measured(data, BASELINE):
        return name, None
    return name, recorded.get("reason") or (
        "the results hold no '%s' numbers" % BASELINE)


def warn(title, message):
    print(message)
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print("::warning title=%s::%s" % (title, message.replace("\n", " ")))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results")
    ap.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE,
                    help="fraction baseline_ns / head_ns may fall below 1.00 "
                         "before it counts as a regression (default %.2f, "
                         "calibrated on A/A runs)" % DEFAULT_TOLERANCE)
    ap.add_argument("--require-baseline", action="store_true",
                    help="fail unless every operation HEAD measured was "
                         "compared against the baseline. Without it a run "
                         "that could not build or measure the baseline says "
                         "so and exits 0, which is right on a laptop and "
                         "wrong in CI")
    args = ap.parse_args()

    try:
        with open(args.results) as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("not a JSON object")
    except (OSError, ValueError) as why:
        sys.exit("cannot read %s: %s" % (args.results, why))

    head = measured(data, HEAD)
    if not head:
        sys.exit("no usable mirror_bridge numbers in %s" % args.results)

    name, missing_why = describe_baseline(data)
    base = measured(data, BASELINE)

    rounds = (data.get("_meta") or {}).get("rounds_ns")
    if not isinstance(rounds, dict):
        rounds = {}
    regressions, ungated = [], []
    gated = 0

    if missing_why is None:
        print("%-20s %12s %12s   baseline / head" % ("operation", "baseline", "head"))
        for op in sorted(head):
            if op not in base:
                ungated.append(op)
                continue
            gated += 1
            ratio = base[op] / head[op]
            regressed = ratio < 1.0 - args.tolerance
            print("%-20s %9.1f ns %9.1f ns   %.3fx%s" % (
                op, base[op], head[op], ratio, "   REGRESSED" if regressed else ""))
            if regressed:
                regressions.append((op, base[op], head[op], ratio))
        print("\ncompared %d of %d operations against %s, tolerance %.0f%%"
              % (gated, len(head), name, args.tolerance * 100))

    behind = [(op, fw, got) for op, row in sorted(ratios(data).items())
              for fw, got in sorted(row.items()) if got < 1.0]
    if behind:
        print("\nSlower than a competitor (reported, not a failure):")
        for op, fw, got in behind:
            print("  %-22s %-12s %.2fx  (%s is %.0f%% faster)" % (
                op, fw, got, fw, (1.0 / got - 1.0) * 100))
    else:
        print("\nNot slower than any competitor on any measured operation.")

    # A gate that compared nothing must not read like a gate that passed. There
    # are three ways to get there and each is said out loud: no baseline
    # numbers at all, a baseline with no operation in common with HEAD, and a
    # baseline that covers only some of them. The suite times the baseline with
    # HEAD's own operation list, so the last two mean something upstream broke.
    unarmed = None
    if missing_why is not None:
        unarmed = ("no operation was gated: %s was not measured (%s). Nothing "
                   "here says mirror_bridge did not regress." % (name, missing_why))
    elif gated == 0:
        unarmed = ("no operation was gated: %s and HEAD have no operation in "
                   "common, so 0 comparisons were made." % name)
    elif ungated:
        unarmed = ("not gated, because %s has no number for them: %s"
                   % (name, ", ".join(ungated)))
    if unarmed:
        print()
        warn("Regression gate did not cover every operation", unarmed)

    if regressions:
        print("\nREGRESSED beyond the %.0f%% tolerance (HEAD against %s, same job):"
              % (args.tolerance * 100, name))
        for op, base_ns, head_ns, ratio in regressions:
            print("  %-20s %.1f ns -> %.1f ns  (%.0f%% slower)" % (
                op, base_ns, head_ns, (head_ns / base_ns - 1.0) * 100))
            # One slow round is interference; every round slow is the code.
            for label, who in ((BASELINE, "baseline"), (HEAD, "head")):
                per_round = measured_rounds(rounds, label, op)
                if per_round:
                    print("      %-8s per round: %s" % (
                        who, " ".join("%.1f" % ns for ns in per_round)))
        print("\nIf the slowdown is real and accepted, move the baseline: put the "
              "commit that\naccepts it in benchmarks/gate_baseline.json. Never "
              "move it to make a red build green.")
        return 1

    if unarmed and args.require_baseline:
        return 1
    if gated:
        print("\nNo %soperation regressed." % ("gated " if unarmed else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
