#include "lua/mirror_bridge_lua.hpp"
#include "array_members.hpp"

// A class with any C array member used to take the whole Lua module down at
// compile time: the member gate accepted it and no to_lua or from_lua did.
MIRROR_BRIDGE_LUA_MODULE(array_members_lua,
    mirror_bridge::lua::bind_class<arr::Label>(L, "Label");
    mirror_bridge::lua::bind_class<arr::Brimful>(L, "Brimful");
    mirror_bridge::lua::bind_class<arr::Tint>(L, "Tint");
    mirror_bridge::lua::bind_class<arr::Grid>(L, "Grid");
    mirror_bridge::lua::bind_class<arr::Huge>(L, "Huge");
    mirror_bridge::lua::bind_class<arr::Names>(L, "Names");
)
