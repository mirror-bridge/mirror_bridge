local m = require("array_members_lua")

print("=== C array members, Lua ===")

local label = m.Label()
assert(label.name == "abc", "a char buffer should read as its string, got " .. tostring(label.name))
label.name = "hello"
assert(label.name == "hello" and label:length() == 5, "and C++ should see what was written")
print("  ok  a char buffer is a string in both directions")

label.name = string.rep("x", 15)
assert(label:length() == 15, "fifteen bytes and a terminator fit char[16]")
local ok, err = pcall(function() label.name = string.rep("y", 16) end)
assert(not ok, "sixteen bytes and a terminator do not fit char[16]")
assert(tostring(err):find("16 bytes") and tostring(err):find("char%[16%]"),
       "the error should give both sizes: " .. tostring(err))
assert(label.name == string.rep("x", 15), "a refused write must leave the buffer alone")
print("  ok  a string that does not fit is refused by size, not truncated")

label.name = "a-longer-value"
label.name = "z"
assert(label.name == "z" and label:tail_is_clear(), "a shorter value leaves no tail behind")
print("  ok  the tail is zeroed")

for _, bad in ipairs({5, true, {}}) do
    local ok2 = pcall(function() label.name = bad end)
    assert(not ok2, "char[16] accepted a " .. type(bad))
end
assert(label.name == "z", "a number is not turned into a string on the way in")
print("  ok  only a string is accepted")

assert(m.Brimful().tag == "abcd", "a buffer with no terminator is read to its end and no further")
print("  ok  an unterminated buffer stops at its extent")

local tint = m.Tint()
assert(#tint.rgba == 4 and tint.rgba[1] == 1.0 and tint.rgba[2] == 0.0 and tint.rgba[4] == 1.0,
       "float[4] should read as a table of four")
tint.rgba = {0.5, 0.5, 0.5, 0.5}
assert(tint:sum() == 2.0, "and C++ should see a table written to it")
assert(tint.channels[1] == 255 and tint.channels[2] == 128 and #tint.channels == 3,
       "unsigned char[3] is three numbers, not text")
print("  ok  a numeric array is a table in both directions")

local ok3 = pcall(function() tint.rgba = {1.0, 2.0} end)
assert(not ok3, "float[4] accepted two elements")
local ok4 = pcall(function() tint.rgba = {9.0, 9.0, "x", 9.0} end)
assert(not ok4, "float[4] accepted a string element")
assert(tint:sum() == 2.0, "a table that fails half way must not be half written")
print("  ok  wrong length and wrong element are refused, with nothing written")

local grid = m.Grid()
assert(grid.cells[2][3] == 6 and #grid.cells == 2 and #grid.cells[1] == 3, "int[2][3] is a table of tables")
assert(grid.rows[1] == "ab" and grid.rows[2] == "cd", "char[2][8] is a table of strings")
grid.rows = {"x", "seven77"}
assert(grid.rows[2] == "seven77" and grid:second_row_length() == 7)
grid.cells = {{1, 1, 1}, {1, 1, 1}}
assert(grid:total() == 6)
local ok5 = pcall(function() grid.rows = {"q", "eight888"} end)
assert(not ok5 and grid.rows[1] == "x", "a row that does not fit refuses the whole assignment")
print("  ok  nested arrays, of numbers and of char buffers")

local ok6, err6 = pcall(function() label.name = "ab\0cd" end)
assert(not ok6 and tostring(err6):find("NUL"), "a string with a NUL inside is refused by name: " .. tostring(err6))
print("  ok  an embedded NUL is refused, not stored and read back short")

local huge = m.Huge()
local samples = {}
for i = 1, 1500000 do samples[i] = 1.5 end
huge.samples = samples
assert(huge:last() == 1.5, "a member too large for the stack is assigned")
assert(not pcall(function() huge.samples = {1.0, 2.0} end))
assert(huge:last() == 1.5)
print("  ok  twelve megabytes written without overflowing the stack")

local names = m.Names()
assert(names.names[1] == "first" and names.names[2] == "second")
assert(not pcall(function() names.names = {"a", "b"} end),
       "an array of const char* must not keep pointers into Lua strings")
assert(names.names[1] == "first")
print("  ok  an array of const char* reads and refuses assignment")

print("PASS: C array members (Lua)")
