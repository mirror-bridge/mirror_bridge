#!/usr/bin/env python3
"""C array data members: a char buffer is a str, any other array is a list.

`char name[16]` passed the member gate (char converts) and had no conversion,
so one such member failed the whole module to compile. Dear ImGui has two:
ImGuiTextFilter::InputBuf[256] and the static ImGuiTextBuffer::EmptyString[1].
"""

import os
import pickle
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'build'))

import array_members as m

print("Test 1: a char buffer reads as the string it holds...")
label = m.Label()
assert label.name == "abc", repr(label.name)
assert isinstance(label.name, str)
print("  ✓ name == 'abc'")

print("Test 2: and is written from a str, which C++ then sees...")
label.name = "hello"
assert label.name == "hello"
assert label.length() == 5, label.length()
print("  ✓ written, and strlen agrees")

print("Test 3: a value that fills the buffer exactly fits; one byte more does not...")
label.name = "x" * 15
assert label.name == "x" * 15 and label.length() == 15
try:
    label.name = "y" * 16
except ValueError as e:
    assert "16 bytes" in str(e) and "char[16]" in str(e), str(e)
else:
    raise AssertionError("16 bytes and a terminator were accepted by char[16]")
assert label.name == "x" * 15, "a refused write changed the buffer: %r" % label.name
print("  ✓ 15 accepted, 16 refused by size, nothing truncated")

print("Test 4: the limit is in bytes, not in characters...")
try:
    label.name = "é" * 8
except ValueError as e:
    assert "16 bytes" in str(e), str(e)
else:
    raise AssertionError("eight two-byte characters were accepted by char[16]")
label.name = "é" * 7
assert label.name == "é" * 7 and label.length() == 14
print("  ✓ eight two-byte characters refused, seven accepted")

print("Test 5: a shorter value leaves nothing of the longer one behind...")
label.name = "a-longer-value"
label.name = "z"
assert label.name == "z" and label.tail_is_clear()
label.name = ""
assert label.name == "" and label.length() == 0
print("  ✓ the tail is zeroed")

print("Test 6: only a str is accepted...")
for bad in (5, None, ["a", "b"], b"bytes"):
    try:
        label.name = bad
    except TypeError:
        pass
    else:
        raise AssertionError("char[16] accepted %r" % (bad,))
assert label.name == ""
print("  ✓ int, None, list and bytes are TypeErrors")

print("Test 7: a buffer with no terminator is read to its end and no further...")
assert m.Brimful().tag == "abcd", repr(m.Brimful().tag)
print("  ✓ 'abcd', without the neighbouring member")

print("Test 8: bytes that are not UTF-8 read without raising...")
label.corrupt()
assert label.name == "�k", repr(label.name)
assert "Label" in repr(label)
print("  ✓ U+FFFD stands in, and repr still works")

print("Test 9: a numeric array is still a list, exact length required...")
tint = m.Tint()
assert tint.rgba == [1.0, 0.0, 0.0, 1.0], tint.rgba
tint.rgba = [0.5, 0.5, 0.5, 0.5]
assert tint.sum() == 2.0
for bad in ([1.0, 2.0], [9.0, 9.0, "x", 9.0]):
    try:
        tint.rgba = bad
    except TypeError:
        pass
    else:
        raise AssertionError("float[4] accepted %r" % (bad,))
assert tint.sum() == 2.0, "a list that failed half way was half written"
assert tint.channels == [255, 128, 0], tint.channels
print("  ✓ read, written, wrong length and wrong element refused with nothing written")
print("  ✓ unsigned char[3] is three numbers, not text")

print("Test 10: nested arrays, of numbers and of char buffers...")
grid = m.Grid()
assert grid.cells == [[1, 2, 3], [4, 5, 6]], grid.cells
assert grid.rows == ["ab", "cd"], grid.rows
grid.rows = ["x", "seven77"]
assert grid.rows == ["x", "seven77"] and grid.second_row_length() == 7
try:
    grid.rows = ["q", "eight888"]
except ValueError as e:
    assert "char[8]" in str(e), str(e)
else:
    raise AssertionError("eight bytes and a terminator were accepted by char[8]")
assert grid.rows == ["x", "seven77"], "a row that does not fit must refuse the whole assignment"
grid.cells = [[1, 1, 1], [1, 1, 1]]
assert grid.total() == 6
print("  ✓ int[2][3] is a list of lists, char[2][8] a list of str")

print("Test 11: static array members are class attributes...")
assert m.Constants.kName == "mirror", repr(m.Constants.kName)
assert m.Constants.kIdentity == [1.0, 0.0, 0.0, 1.0]
assert m.Constants.kAnswer == 42
print("  ✓ static char[8] is a str, static float[4] a list")

print("Test 12: a static member with no conversion costs only itself...")
assert not hasattr(m.Constants, "shared")
assert m.Constants().value == 1
print("  ✓ the int* static is absent, the class and its other statics are not")

print("Test 13: a char buffer survives pickling...")
label = m.Label()
label.name = "pickled"
label.id = 3
copy = pickle.loads(pickle.dumps(label))
assert copy.name == "pickled" and copy.id == 3, (copy.name, copy.id)
print("  ✓ round trip")

print("\nAll array-member tests passed!")
