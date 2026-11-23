#include "javascript/mirror_bridge_javascript.hpp"
#include "multimap.hpp"

MIRROR_BRIDGE_JS_MODULE(multimap_js,
    mirror_bridge::javascript::bind_class<mm::Request>(env, exports, "Request");
)
