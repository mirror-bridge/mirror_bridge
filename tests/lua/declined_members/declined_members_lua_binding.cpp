#include "lua/mirror_bridge_lua.hpp"
#include "declined_members.hpp"

// bind_class_when_bindable is what `mirror_bridge generate` emits. With
// bind_class, any one of these classes is a static_assert for the module.
MIRROR_BRIDGE_LUA_MODULE(declined_members_lua,
    mirror_bridge::lua::bind_class_when_bindable<dm::Engine>(L, "Engine");
    mirror_bridge::lua::bind_class_when_bindable<dm::FixtureDef>(L, "FixtureDef");
    mirror_bridge::lua::bind_class_when_bindable<dm::IO>(L, "IO");
    mirror_bridge::lua::bind_class_when_bindable<dm::Base>(L, "Base");
    mirror_bridge::lua::bind_class_when_bindable<dm::Derived>(L, "Derived");
    mirror_bridge::lua::bind_class_when_bindable<dm::Handles>(L, "Handles");
    mirror_bridge::lua::bind_class_when_bindable<dm::World>(L, "World");
)
