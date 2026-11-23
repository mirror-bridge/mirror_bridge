local m = require("multimap_lua")

print("=== multimap members, Lua ===")

local r = m.Request()
assert(#r.params == 3 and r.params[1][1] == "a" and r.params[1][2] == "1"
       and r.params[2][1] == "a" and r.params[3][1] == "b",
       "a multimap reads as an array of {key, value} pairs with repeats kept")
print("  ok  reads as an array of pairs")

r.params = {{"x", "1"}, {"x", "2"}}
assert(r:param_count() == 2 and r.params[2][2] == "2")
r.counts = {{"hit", 1}, {"hit", 2}, {"miss", 0}}
assert(r:count_of("hit") == 2 and r:count_of("miss") == 1)
print("  ok  written from an array of pairs, both kinds, with a repeated key")

r.params = {k = "v"}
assert(r:param_count() == 1 and r.params[1][1] == "k" and r.params[1][2] == "v")
r.params = {}
assert(r:param_count() == 0)
print("  ok  a key = value table is accepted, and so is an empty one")

r.params = {{"keep", "me"}}
for _, bad in ipairs({ {{"x"}}, {{"x", {}}}, {{"a", "b"}, {"c"}} }) do
    assert(not pcall(function() r.params = bad end), "a malformed table was accepted")
end
assert(not pcall(function() r.params = "text" end))
assert(r:param_count() == 1 and r.params[1][1] == "keep", "a refused assignment changed the member")
print("  ok  a malformed value is refused whole")

r:replace({{"p", "q"}, {"p", "r"}})
assert(#r:all() == 2 and r:all()[2][2] == "r")
print("  ok  as a parameter and as a return")

print("PASS: multimap members (Lua)")
