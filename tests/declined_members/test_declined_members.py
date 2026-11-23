#!/usr/bin/env python3
"""A data member with no conversion costs itself, not its class.

It used to cost the class. Under auto discovery one raw pointer field got the
whole class skipped, with every method it has: nineteen of Dear ImGui's
forty-three classes, and box2d's b2FixtureDef and b2JointDef.
"""

import os
import pickle
import subprocess
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'build'))

import declined_members as m


def public(obj):
    return sorted(n for n in dir(obj) if not n.startswith("_"))


print("Test 1: a class with a pointer member binds, without that member...")
f = m.FixtureDef()
assert public(f) == ["density", "friction", "has_shape", "is_sensor", "mass"], public(f)
assert f.friction == 0.25 and f.density == 1.0 and f.is_sensor is False
f.density = 3.0
assert f.mass() == 6.0
print("  ✓ three fields and two methods; shape and user_data are absent")

print("Test 2: repr shows what is there...")
assert repr(m.FixtureDef()) == "FixtureDef(friction=0.25, density=1.0, is_sensor=False)", repr(m.FixtureDef())
print("  ✓", repr(m.FixtureDef()))

print("Test 3: a function pointer and a pointer to member are left out the same way...")
io = m.IO()
assert public(io) == ["delta_time", "frame", "next_frame"], public(io)
assert io.next_frame() == 1 and io.frame == 1
print("  ✓ IO keeps delta_time, frame and its method")

print("Test 4: an inherited member with no conversion costs neither class...")
# Before, Derived bound and Base did not: the gate looked only at the members
# a class declares itself.
d = m.Derived()
assert d.own == 6 and d.total() == 11
assert m.Base().kept == 5
assert not hasattr(d, "raw") and not hasattr(m.Base(), "raw")
print("  ✓ Base and Derived both bind, without raw")

print("Test 5: a class left with no members still binds for what it does...")
h = m.Handles()
assert public(h) == ["count"] and h.count() == 2
assert repr(h) == "Handles()", repr(h)
print("  ✓ Handles has its method")

print("Test 6: [[=exclude{}]] on such a member satisfies the hand-written binder...")
# The module compiling is most of this test: bind_class's assertion told
# people to annotate the member and then did not read the annotation.
k = m.Marked()
assert public(k) == ["shown"] and k.shown == 1
print("  ✓ bind_class<Marked> compiled, and secret is not exposed")

print("Test 7: such a class works as a member, a borrowed pointer, a value and an argument...")
w = m.World()
assert isinstance(w.fixture(), m.FixtureDef)
w.fixture().friction = 0.5
assert w.copy().friction == 0.5, "the borrow did not write through"
assert getattr(w, "def").friction == 0.5, "the member view did not see it"
w.attach()
assert w.fixture().has_shape()
# The pointer travels with the C++ copy although Python cannot see it.
assert w.copy().has_shape(), "a copy lost the member Python does not carry"
c = w.copy()
c.density = 4.0
w.apply(c)
assert w.fixture().density == 4.0 and w.fixture().has_shape()
print("  ✓ and the unseen pointer survives every copy")

print("Test 8: it does not pickle, because the state would be missing a field...")
try:
    pickle.dumps(m.FixtureDef())
except TypeError:
    pass
else:
    raise AssertionError("pickled an object whose shape pointer the state cannot hold")
assert pickle.loads(pickle.dumps(m.Engine())).rpm == 900
print("  ✓ refused, where a class with every member carried round-trips")

print("Test 9: a pointer to a class of the C library is still not a borrow...")
log = m.Log()
assert public(log) == ["lines"], public(log)
print("  ✓ the two FILE* methods are absent, not present and raising")
# ...and nothing wider than FILE. `typedef struct _Item {...} Item;` has a
# reserved name too, and is an ordinary class of the library.
tray = m.Tray()
tray.get().x = 9
assert tray.item.x == 9, "the borrow of a typedef'd struct did not write through"
other = m.Item()
other.x = 4
tray.take(other)
assert tray.get().x == 4
print("  ✓ a struct named the C way is still borrowed and still taken by pointer")

print("Test 10: the members left out are named, when asked...")
here = os.path.dirname(os.path.abspath(__file__))
build = os.path.join(here, "..", "..", "build")
code = "import sys; sys.path.insert(0, %r); import declined_members" % build

quiet = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                       env={k: v for k, v in os.environ.items()
                            if k != "MIRROR_BRIDGE_REPORT_DECLINED"})
assert "skipped member" not in quiet.stderr, quiet.stderr

loud = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                      env=dict(os.environ, MIRROR_BRIDGE_REPORT_DECLINED="1"))
for name in ("FixtureDef::shape", "FixtureDef::user_data", "IO::set_clipboard",
             "IO::handler", "Base::raw", "Handles::first", "Handles::second",
             "Handles::registry"):
    assert "skipped member '%s'" % name in loud.stderr, \
        "%s was left out and not named:\n%s" % (name, loud.stderr)
# Someone asked for that one to be left out; reporting it would be noise.
assert "Marked::secret" not in loud.stderr, loud.stderr
assert "skipped method 'Log::handle'" in loud.stderr and "skipped method 'Log::attach'" in loud.stderr
print("  ✓ quiet by default, seven members and a static named, the annotated one not among them")

print("\nAll declined-member tests passed!")
