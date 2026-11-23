#include "python/mirror_bridge_python.hpp"
#include "multimap.hpp"

MIRROR_BRIDGE_MODULE(multimap,
    mirror_bridge::bind_class<mm::Request>(m, "Request");
)
