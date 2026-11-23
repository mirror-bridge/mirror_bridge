#include "javascript/mirror_bridge_javascript.hpp"
#include "array_members.hpp"

// See the Lua sibling: any C array member made the whole module uncompilable.
MIRROR_BRIDGE_JS_MODULE(array_members_js,
    mirror_bridge::javascript::bind_class<arr::Label>(env, exports, "Label");
    mirror_bridge::javascript::bind_class<arr::Brimful>(env, exports, "Brimful");
    mirror_bridge::javascript::bind_class<arr::Tint>(env, exports, "Tint");
    mirror_bridge::javascript::bind_class<arr::Grid>(env, exports, "Grid");
    mirror_bridge::javascript::bind_class<arr::Huge>(env, exports, "Huge");
    mirror_bridge::javascript::bind_class<arr::Names>(env, exports, "Names");
)
