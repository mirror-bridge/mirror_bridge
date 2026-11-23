#include "lua/mirror_bridge_lua.hpp"
#include "declined_methods.hpp"

MIRROR_BRIDGE_LUA_MODULE(declined_methods_lua,
    mirror_bridge::lua::bind_class<dmeth::Item>(L, "Item");
    mirror_bridge::lua::bind_class<dmeth::Shelf>(L, "Shelf");
)
