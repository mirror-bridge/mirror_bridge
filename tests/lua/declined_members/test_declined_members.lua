local m = require("declined_members_lua")

print("=== a member with no conversion costs itself, Lua ===")

local f = m.FixtureDef()
assert(f.friction == 0.25 and f.density == 1.0 and f.is_sensor == false,
       "the fields that convert should read")
f.density = 3.0
assert(f:mass() == 6.0, "and write, and a method should see it")
assert(f.shape == nil, "the pointer member is not a field")
local ok, err = pcall(function() f.user_data = 1 end)
assert(not ok and tostring(err):find("user_data"), "writing it is refused by name: " .. tostring(err))
print("  ok  a class with a pointer member binds without that member")

local io = m.IO()
assert(io.delta_time == 0.5 and io:next_frame() == 1 and io.frame == 1)
assert(io.set_clipboard == nil and io.handler == nil)
print("  ok  a function pointer and a pointer to member are left out the same way")

local d = m.Derived()
assert(d.own == 6 and d:total() == 11 and d.raw == nil)
assert(m.Base().kept == 5 and m.Base().raw == nil)
print("  ok  an inherited member with no conversion costs neither class")

assert(m.Handles():count() == 2)
print("  ok  a class left with no fields still binds for what it does")

local w = m.World()
w:attach()
local c = w:copy()
assert(c:has_shape(), "a copy must keep the member Lua does not carry")
c.density = 4.0
w:apply(c)
assert(w:copy().density == 4.0 and w:copy():has_shape())
w:apply({friction = 0.5})
assert(w:copy().friction == 0.5, "a table still converts to the class, field by field")
assert(w.def.friction == 0.5, "and the class still reads as a member")
print("  ok  such a class works as a member, a value, an argument and a table")

print("PASS: declined members (Lua)")
