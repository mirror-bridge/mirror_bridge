#include "javascript/mirror_bridge_javascript.hpp"
#include "declined_methods.hpp"

MIRROR_BRIDGE_JS_MODULE(declined_methods_js,
    mirror_bridge::javascript::bind_class<dmeth::Item>(env, exports, "Item");
    mirror_bridge::javascript::bind_class<dmeth::Shelf>(env, exports, "Shelf");
)
