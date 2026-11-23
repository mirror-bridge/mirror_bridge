#!/usr/bin/env python3
"""std::multimap and std::unordered_multimap cross as a list of pairs.

A class holding either one failed its whole module to compile, in every
backend. cpp-httplib's Headers is an unordered_multimap.
"""

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'build'))

import multimap as m

print("Test 1: a multimap member reads as a list of (key, value) pairs, repeats kept...")
r = m.Request()
assert r.params == [("a", "1"), ("a", "2"), ("b", "3")], r.params
assert r.counts == []
print("  ✓", r.params)

print("Test 2: and is written from one...")
r.params = [("x", "1"), ("x", "2")]
assert r.params == [("x", "1"), ("x", "2")] and r.param_count() == 2
r.counts = [("hit", 1), ("hit", 2), ("miss", 0)]
assert r.count_of("hit") == 2 and r.count_of("miss") == 1
assert sorted(r.counts) == [("hit", 1), ("hit", 2), ("miss", 0)]
print("  ✓ both kinds, with a repeated key")

print("Test 3: a dict is accepted for the one-value-per-key case...")
r.params = {"k": "v", "j": "w"}
assert r.params == [("j", "w"), ("k", "v")], r.params
r.params = []
assert r.param_count() == 0
print("  ✓ a dict, and an empty list")

print("Test 4: a value that is not pairs of the right types is refused whole...")
r.params = [("keep", "me")]
for bad in ([("x", 1)], [("only-one",)], [("a", "b"), ("c", 3)], "text", 5, None):
    try:
        r.params = bad
    except TypeError:
        pass
    else:
        raise AssertionError("multimap<string, string> accepted %r" % (bad,))
assert r.params == [("keep", "me")], "a refused assignment changed the member: %r" % r.params
print("  ✓ TypeError each time, and the member is as it was")

print("Test 5: as a return and as a parameter...")
r.replace([("p", "q"), ("p", "r")])
assert r.all() == [("p", "q"), ("p", "r")]
r.replace({"solo": "1"})
assert r.all() == [("solo", "1")]
print("  ✓ replace() takes pairs or a dict, all() returns pairs")

print("\nAll multimap tests passed!")
