#include "lua/mirror_bridge_lua.hpp"
#include "multimap.hpp"

MIRROR_BRIDGE_LUA_MODULE(multimap_lua,
    mirror_bridge::lua::bind_class<mm::Request>(L, "Request");
)
