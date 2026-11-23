local m = require("declined_methods_lua")

print("=== a method that cannot be called costs itself, Lua ===")

-- The module loading at all is the first assertion: any one of the methods
-- below used to be a compile error for both classes.
local shelf = m.Shelf()
local item = m.Item()
item.value = 5
shelf:put(item)
assert(shelf:size() == 1 and shelf:first().value == 5 and shelf:label() == "shelf")
assert(m.Shelf.capacity() == 8)
print("  ok  the methods that can be called are bound")

for _, name in ipairs({"find", "peek", "adopt", "release", "fill", "each", "all", "weigh"}) do
    assert(shelf[name] == nil, name .. " cannot be called from Lua and was offered")
end
assert(m.Shelf.shared == nil, "a static method returning a pointer was offered")
print("  ok  eight methods and one static method are absent")

assert(shelf:pick(3) == 3, "the callable overload should be reachable behind the one that is not")
assert(shelf:take(3) == 4)
print("  ok  an overload that cannot be called does not hide one that can")

-- Named when asked, in the line shape the Python backend prints. The child
-- inherits LUA_CPATH, so it loads the same module.
local child = io.popen(
    "MIRROR_BRIDGE_REPORT_DECLINED=1 lua5.4 -e 'require(\"declined_methods_lua\")' 2>&1")
local said = child:read("a")
child:close()
for _, name in ipairs({"find", "peek", "adopt", "release", "fill", "each", "all", "weigh",
                       "shared", "pick", "take"}) do
    assert(said:find("skipped method 'Shelf::" .. name .. "'", 1, true),
           name .. " was left out and not named:\n" .. said)
end
assert(said:find("the return type has no conversion to Lua", 1, true))
assert(said:find("a parameter has no conversion from Lua", 1, true))
assert(not said:find("Shelf::size", 1, true), "a bound method was reported as left out")

local quiet = io.popen("lua5.4 -e 'require(\"declined_methods_lua\")' 2>&1")
local nothing = quiet:read("a")
quiet:close()
assert(not nothing:find("skipped", 1, true), "a plain load printed the list:\n" .. nothing)
print("  ok  quiet by default, and each one is named with its reason when asked")

print("PASS: declined methods (Lua)")
