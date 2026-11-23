#include "javascript/mirror_bridge_javascript.hpp"
#include "declined_members.hpp"

// See the Lua sibling.
MIRROR_BRIDGE_JS_MODULE(declined_members_js,
    mirror_bridge::javascript::bind_class_when_bindable<dm::Engine>(env, exports, "Engine");
    mirror_bridge::javascript::bind_class_when_bindable<dm::FixtureDef>(env, exports, "FixtureDef");
    mirror_bridge::javascript::bind_class_when_bindable<dm::IO>(env, exports, "IO");
    mirror_bridge::javascript::bind_class_when_bindable<dm::Base>(env, exports, "Base");
    mirror_bridge::javascript::bind_class_when_bindable<dm::Derived>(env, exports, "Derived");
    mirror_bridge::javascript::bind_class_when_bindable<dm::Handles>(env, exports, "Handles");
    mirror_bridge::javascript::bind_class_when_bindable<dm::World>(env, exports, "World");
)
