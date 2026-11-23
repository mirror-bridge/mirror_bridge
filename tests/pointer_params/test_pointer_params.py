#!/usr/bin/env python3
"""A pointer parameter takes the object a wrapper already holds.

box2d's `b2World::CreateBody(const b2BodyDef* def)` and tinyxml2's
`XMLNode::InsertEndChild(XMLNode* addThis)` are how those libraries are
driven, and a method with a pointer parameter used to be refused outright.
The argument is the wrapper's own C++ object, passed by address exactly as a
reference parameter always was.

What a pointer adds over a reference is that it can be null and that it can
be an array, and most of this file is about those two: None is passed as
nullptr only where the header gives the parameter a default, and a pointer
declared beside an element count is not bound at all.
"""

import os
import subprocess
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'build'))

import pointer_params as p


def refused(call):
    try:
        call()
    except TypeError:
        return True
    return False


print("Test 1: a const pointer in, a borrowed pointer out...")
world = p.World()
definition = p.BodyDef()
definition.x = 3.0
definition.kind = 5
body = world.CreateBody(definition)
assert type(body) is p.Body
assert (body.x(), body.kind()) == (3.0, 5)
assert world.body_count() == 1
print("  ok")

print("Test 2: the callee receives the wrapper's own object, not a copy...")
assert world.index_of(body) == 0, "the address did not survive the round trip"
world.nudge(body, 1.5)
assert body.x() == 4.5, "a write through the pointer did not reach the Python object"
vec = p.Vec2()
vec.x, vec.y = 2.0, 1.0
world.scale(vec, 10)
assert (vec.x, vec.y) == (20.0, 10.0), "a write through the pointer went to a copy"
print("  ok")

print("Test 3: passing an object does not leak a reference to it...")
before = sys.getrefcount(body)
for _ in range(1000):
    world.index_of(body)
    world.kind_or(body)
assert sys.getrefcount(body) == before
print("  ok")

print("Test 4: a derived object is adjusted to the base the callee asked for...")
assert world.area_of(p.Circle()) == 3.0
square = p.Square()
# Shape is Square's second base. Unadjusted, this reads an int as a vtable.
assert world.area_of(square) == 4.0
print("  ok")

print("Test 5: None is nullptr only where the header defaults the parameter...")
assert world.kind_or() == -1
assert world.kind_or(None) == -1
assert world.kind_or(body) == 5
assert world.kind_or(body=None, fallback=9) == 9
assert world.kind_or(None, 4) == 4
# kind_of dereferences without a check. A TypeError here is the whole point:
# the alternative is a segfault inside the library.
assert refused(lambda: world.kind_of(None))
assert refused(lambda: world.CreateBody(None))
assert world.kind_of(body) == 5
print("  ok")

print("Test 6: only an object of the right class is accepted...")
assert refused(lambda: world.kind_of(definition))
assert refused(lambda: world.kind_of(3))
assert refused(lambda: world.kind_of("body"))
assert refused(lambda: world.area_of(body))
assert refused(lambda: world.CreateBody(vec))


class PyDef(p.BodyDef):
    pass


sub = PyDef()
sub.kind = 8
assert world.CreateBody(sub).kind() == 8, "a Python subclass is still the C++ class"
print("  ok")

print("Test 7: one object beside an integer that is not a count still binds...")
assert world.x_times(vec, 3) == 60.0
print("  ok")

print("Test 8: a pointer beside an element count is an array, and is not bound...")
for name in ("sum_x", "sum_leading", "sum_unnamed", "sum_sized"):
    assert not hasattr(p.World, name), f"World.{name} would read past a single object"
print("  ok")

print("Test 9: the shapes that stay refused cost only themselves...")
for name in ("find", "take_opaque", "take_string", "take_int", "take_pointers"):
    assert not hasattr(p.World, name), f"World.{name} should not be bound"
assert world.name_length("abc") == 3, "const char* is a string, as before"
assert not hasattr(p, "free_x"), "a free function has no pointer parameters yet"
# Joint(Body*, Body*) keeps its arguments; only the default constructor binds.
assert p.Joint().ends() == 0
assert refused(lambda: p.Joint(body, body))
print("  ok")

print("Test 10: an overload that was bound before keeps its calls...")
# which(Body*) is declared first and returns 2; which(const Body&) returns 1
# and is the one every call reached before pointer parameters existed.
assert world.which(body) == 1
print("  ok")

print("Test 11: a static method takes a pointer the same way...")
assert p.World.double_x(vec) == 40.0
assert refused(lambda: p.World.double_x(None))
print("  ok")

print("Test 12: the stub says what the runtime does...")
stub = p.__mirror_bridge_stubs__()
assert "def CreateBody(self, def_: BodyDef, /) -> Body | None: ..." in stub, stub
assert "def kind_of(self, body: Body) -> int: ..." in stub
assert "def kind_or(self, body: Body | None = ..., fallback: int = ...) -> int: ..." in stub
assert "sum_x" not in stub
print("  ok")

print("Test 13: the declined report names the array rule...")
report = subprocess.run(
    [sys.executable, "-c",
     "import sys; sys.path.append(%r); import pointer_params" % sys.path[-1]],
    env=dict(os.environ, MIRROR_BRIDGE_REPORT_DECLINED="1"),
    capture_output=True, text=True, check=True)
declined = report.stdout + report.stderr
assert "skipped method 'World::sum_x' (it takes a pointer beside an element count" in declined, declined
assert "World::CreateBody" not in declined
print("  ok")

print("Test 14: a method that returns its pointer argument returns that object...")
# The world does not own `vec`, so a borrow pinned to the world would dangle
# once `vec` was collected. The caller gets its own object back instead.
assert world.same(vec) is vec
fresh = p.Vec2()
fresh.x = 6.0
kept = world.same(fresh)
identity = id(fresh)
del fresh
assert id(kept) == identity and kept.x == 6.0
print("  ok")

print("Test 15: the owner frees what it was asked to free...")
world.DestroyBody(body)
assert world.body_count() == 1    # the one made from the Python subclass
print("  ok")

print("\nAll pointer parameter tests passed.")
