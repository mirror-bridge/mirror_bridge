#!/usr/bin/env python3
"""A pointer an instance method returns is the library's own object, borrowed.

A factory-style C++ API hands its central class out by raw pointer and frees
it itself: tinyxml2's XMLElement, box2d's b2Body. Pointer returns used to be
refused wholesale, because a `T*` does not say who owns the T, so those
classes had no way to reach Python at all.

One shape is answered from the signature alone: a `T*` returned by an instance
method is a borrow. The wrapper points at the library's object, frees nothing,
and keeps the receiver's owner alive. Everything else about a pointer return
stays refused, and half of this file is about that half.

`Tally` counts every Node and Item constructed and destroyed, which is what
lets these tests assert the thing that matters: a borrow destroys nothing.
"""

import gc
import os
import subprocess
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'build'))

import borrowed_returns as b


def settle():
    gc.collect()
    b.Tally.reset()


print("Test 1: a borrow destroys nothing, ever...")
settle()
reg = b.Registry()
reg.add(1, 2.0)
after_add = (b.Tally.alive(), b.Tally.freed())
item = reg.get(1)
assert type(item) is b.Item, type(item)
assert (b.Tally.alive(), b.Tally.freed()) == after_add, "taking a borrow built or freed an Item"
del item
gc.collect()
assert (b.Tally.alive(), b.Tally.freed()) == after_add, "dropping a borrow freed the registry's Item"
print("  ✓ live and destroyed counts do not move")

print("Test 2: a write through the borrow lands in the owner...")
reg.add(2, 3.0)
reg.get(1).scale(10.0)
assert reg.total() == 23.0, reg.total()
held = reg.get(2)
held.weight = 1.0
assert reg.total() == 21.0, reg.total()
print("  ✓ reg.get(1).scale(10) changed the registry's own Item")

print("Test 3: a null pointer is None...")
assert reg.get(99) is None
tree = b.Tree()
assert tree.root() is None
assert tree.find(1) is None
print("  ✓ get/root/find on a miss")

print("Test 4: references balance over many borrows...")
before = sys.getrefcount(reg)
for _ in range(1000):
    reg.get(1)
    reg.get(99)
gc.collect()
assert sys.getrefcount(reg) == before, (sys.getrefcount(reg), before)
print("  ✓ 1000 borrows leave the owner's refcount where it was")

print("Test 5: a borrow keeps its owner alive...")
settle()
node = b.Tree().create(5)          # the Tree has no other reference
gc.collect()
assert b.Tally.alive() == 1, "the Tree died under a live borrow"
assert node.value() == 5
node.set_value(6)
assert node.value() == 6
del node
gc.collect()
assert (b.Tally.alive(), b.Tally.freed()) == (0, 1), (b.Tally.alive(), b.Tally.freed())
print("  ✓ the Tree is freed when the last borrow goes, and not before")

print("Test 6: a walk pins the owner once per wrapper, not once per step...")
settle()
tree = b.Tree()
base = sys.getrefcount(tree)
child = tree.create(1)
assert sys.getrefcount(tree) == base + 1
grandchild = child.add_child(2)
great = grandchild.add_child(3)
deep = great.add_child(4)
# Four live wrappers, four references -- each to the Tree, none to a Node
# that was only passed through.
assert sys.getrefcount(tree) == base + 4, (sys.getrefcount(tree), base)
del child, grandchild, great
gc.collect()
assert sys.getrefcount(tree) == base + 1, "an intermediate wrapper was kept alive by the chain"
assert deep.value() == 4
del tree
gc.collect()
assert deep.value() == 4, "the deepest borrow lost its owner"
assert b.Tally.alive() == 4
del deep
gc.collect()
assert b.Tally.alive() == 0
print("  ✓ four levels down holds the Tree directly")

print("Test 7: a class nobody outside may destroy is bound, and only borrowed...")
settle()
tree = b.Tree()
first = tree.create(10)
second = tree.create(20)
assert type(first) is b.Node
assert first.next().value() == 20
assert second.next() is None
assert tree.find(20).value() == 20
assert tree.size() == 2
for make, cls in ((lambda: b.Node(), "Node"), (lambda: b.Counted(3), "Counted")):
    try:
        make()
    except TypeError as e:
        assert "destructor is not accessible" in str(e), str(e)
        assert cls in str(e), str(e)
    else:
        raise AssertionError(f"{cls}() built an object nothing could free")
# Counted has a public constructor. It is refused all the same: `new` would
# compile, and the object could never be freed.
assert reg.counted().value() == 9
print("  ✓ Node and Counted bind, work, and refuse construction")

print("Test 8: an object that already has a wrapper gets that wrapper back...")
assert first.tree() is tree
assert first.add_child(11).tree() is tree
# A method that returns `this` so calls can be chained.
assert first.bump() is first
assert first.bump().bump().value() == 13


# ...and a Python subclass stays one through the chain.
class Tagged(b.Item):
    pass


tagged = Tagged()
assert tagged.self() is tagged
assert type(tagged.self()) is Tagged
del tagged
print("  ✓ node.tree() is tree, node.bump() is node, and a subclass stays a subclass")

print("Test 9: a const pointer is not bound...")
# A wrapper is a mutable handle. Borrowing through `const Item*` would let
# Python write to what C++ declared read-only, and copying would silently
# swap the library's object for a snapshot of it.
assert not hasattr(reg, "peek"), "const Item* peek() was bound"
print("  ✓ Registry.peek is absent")

print("Test 10: a const/non-const pair is reached through its non-const half...")
# `at` declares the const overload first and `front` the non-const one. Only
# the non-const one can cross, so the declaration order does not matter.
settle()
reg = b.Registry()
reg.add(1, 2.0)
reg.add(2, 3.0)
reg.at(0).weight = 10.0
assert reg.total() == 13.0, reg.total()
reg.front().weight = 20.0
assert reg.total() == 23.0, reg.total()
print("  ✓ at() and front() both reach the registry's Item")

print("Test 11: with no receiver there is nothing to borrow from...")
assert not hasattr(b.Registry, "shared_default"), "a static T* was bound"
assert not hasattr(b.Registry, "default_item"), "a static const T* was bound"
assert not hasattr(b, "global_item"), "a free function returning T* was bound"
assert not hasattr(b, "global_default"), "a free function returning const T* was bound"
print("  ✓ static methods and free functions returning a pointer stay unbound")

print("Test 12: a pointer that names nothing wrappable stays unbound...")
for name in ("handle", "slots", "raw_counter", "holder", "last_error", "raw_root",
             "all_items"):
    assert not hasattr(reg, name), f"Registry.{name} was bound"
print("  ✓ incomplete pointee, T**, int*, Holder<Opaque>*, std::error_code*,")
print("    a struct of raw pointers, and std::vector<Item*>")

print("Test 13: a pointer to a class no module binds is refused by name...")
try:
    reg.unbound()
except TypeError as e:
    assert "borrowed::Unbound" in str(e), str(e)
else:
    raise AssertionError("a pointer to an unbound class crossed")
print("  ✓ TypeError names borrowed::Unbound")

print("Test 14: the stub admits the None...")
stub = b.__mirror_bridge_stubs__()
for line in ("def create(self, v: int) -> Node | None: ...",
             "def get(self, id: int) -> Item | None: ...",
             "def tree(self) -> Tree | None: ...",
             "def at(self, index: int) -> Item | None: ..."):
    assert line in stub, f"missing from the stub: {line}"
# One `next` and one `at`: the const half of each pair is not a second overload.
assert stub.count("def next(self)") == 1, stub
assert stub.count("def at(self, index: int)") == 1, stub
assert "def peek" not in stub
print("  ✓ pointer returns are typed `T | None`")

print("Test 15: what was declined is reported, and half of a pair is not...")
env = dict(os.environ, MIRROR_BRIDGE_REPORT_DECLINED="1")
probe = subprocess.run(
    [sys.executable, "-c",
     "import sys; sys.path.append(sys.argv[1]); import borrowed_returns",
     os.path.join(os.path.dirname(__file__), '..', '..', 'build')],
    env=env, capture_output=True, text=True)
assert probe.returncode == 0, probe.stderr
for name in ("Registry::handle", "Registry::slots", "Registry::raw_counter",
             "Registry::peek", "Registry::end"):
    assert f"skipped method '{name}'" in probe.stderr, (name, probe.stderr)
# `const Node* next() const` cannot cross and `Node* next()` can. The name is
# in the module, so a line saying it was skipped would report a loss that did
# not happen -- eighty of them for tinyxml2's XMLElement.
for name in ("Node::next", "Registry::at", "Registry::front", "Registry::get"):
    assert f"skipped method '{name}'" not in probe.stderr, (name, probe.stderr)
print("  ✓ declined methods are named; no line for next/at/front")

print("Test 16: an iterator is a position, not an object...")
# end() points one past the last Item, at `canary_`. Wrapping it handed Python
# a writable Item over memory that is not one.
for name in ("begin", "end", "data"):
    assert not hasattr(reg, name), f"Registry.{name} was bound as a borrow"
assert reg.canary() == 0x5afe
print("  ✓ begin/end/data are declined")

print("Test 17: a class that names itself by value costs those methods only...")
# Sealed has a protected destructor and methods that return or take a Sealed
# by value. A member may do that; the binding may not, because receiving the
# value means destroying it. Each used to be a compile error for the module.
sealed = reg.sealed()
assert type(sealed) is b.Sealed
assert sealed.value() == 4
for name in ("scaled", "absorb", "sink", "maybe", "all", "owned", "make", "kids"):
    assert not hasattr(b.Sealed, name), f"Sealed.{name} was bound"
try:
    sealed + sealed
except TypeError:
    pass
else:
    raise AssertionError("operator+ returning a Sealed by value was bound")
print("  ✓ Sealed binds with value(); eight methods and two operators are declined")

print("Test 18: a trampoline does not make an unfreeable class constructible...")
# The trampoline is destructible, so building one compiles. The wrapper knows
# it only as a Listener and could never free it: this used to construct, mark
# the object as owned, and leak it on every collection.
settle()


class Loud(b.Listener):
    def on_event(self, x):
        return x * 2


for make in (b.Listener, Loud):
    try:
        make()
    except TypeError as e:
        assert "destructor is not accessible" in str(e), str(e)
    else:
        raise AssertionError(f"{make.__name__}() built an object nothing could free")
assert b.Tally.alive() == 0, "a refused construction still built a Listener"
print("  ✓ Listener() and a Python subclass of it are both refused")

print("Test 19: a pointer to the ARGUMENT is kept valid by the argument...")
# `Item* same(Item& item) { return &item; }` returns the caller's own object.
# Pinning the registry would leave the result dangling as soon as the
# argument's Python object went away, which for a temporary is at once.
settle()
reg = b.Registry()
item = b.Item()
assert reg.same(item) is item, "the caller's own object came back as a second wrapper"
del item

settle()
result = reg.same(b.Item())
gc.collect()
assert b.Tally.freed() == 0, "the argument was destroyed while a wrapper still points at it"
del result
gc.collect()
assert b.Tally.freed() == 1, "the argument was never released"

# A part of the argument: the borrow has to hold the whole Crate.
settle()
second = reg.second_of(b.Crate())
gc.collect()
assert b.Tally.freed() == 0, "the Crate was destroyed under a borrow of its member"
second.id = 5
assert second.id == 5
del second
gc.collect()
assert b.Tally.freed() == 2, "the Crate and its two Items were never released"
print("  ✓ the argument is returned as itself, and outlives a borrow of its member")

print("Test 20: an overload that was bound before keeps its calls...")
# In each pair the pointer-returning overload is declared first and would
# accept the same argument. Only the second could be bound before a pointer
# return could cross, so these calls must still reach it.
reg = b.Registry()
reg.add(3, 1.0)
assert reg.pick(3) == 30, reg.pick(3)
assert reg.flag(True) is False
assert reg.named("x") == "str:x"
# The pointer overload is still there for a call only it can take.
assert type(reg.pick(3.0)) is b.Item
print("  ✓ pick(int), flag(bool) and named(str) are the overloads they always were")

print("Test 21: a handle that names an unfreeable class is still an ordinary value...")
# Ref<Pinned> holds a Pinned* and is destructible. Treating it like
# optional<Pinned> took away every method that passed or returned one.
vault = b.Vault()
assert vault.root().value() == 11
assert vault.use(vault.root()) == 12
assert b.use_pinned(b.make_pinned()) == 13
assert hasattr(b.Vault, "shared"), "a shared_ptr to an unfreeable class is still a shared_ptr"
print("  ✓ methods and functions passing Ref<Pinned> are bound and work")

print("Test 22: shapes that cannot be bound cost only themselves...")
# A template declared and never defined, by pointer and by value.
opener = b.Opener()
assert opener.n() == 1
for name in ("open", "close", "finish"):
    assert not hasattr(b.Opener, name), f"Opener.{name} names an undefined template"
# A raw pointer nested in a pair, optional, tuple, map, array or callback.
for name in ("visit", "insert", "maybe", "tagged", "by_name", "both"):
    assert not hasattr(b.Node, name), f"Node.{name} has no conversion and was bound"
# A method that can only be called on an rvalue.
for name in ("take", "drain"):
    assert not hasattr(b.Registry, name), f"Registry.{name} is &&-qualified"
# A class with raw pointers in its data members.
assert not hasattr(b, "PointerBag")
print("  ✓ each is declined, and its class and module are intact")

print("\nAll borrowed-return tests passed.")
