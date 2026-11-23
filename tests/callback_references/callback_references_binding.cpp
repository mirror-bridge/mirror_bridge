#include "python/mirror_bridge_python.hpp"
#include "callback_references.hpp"

MIRROR_BRIDGE_MODULE(callback_references,
    mirror_bridge::bind_class<cbref::Request>(m, "Request");
    mirror_bridge::bind_class<cbref::Response>(m, "Response");
    mirror_bridge::bind_class<cbref::Counter>(m, "Counter");
    mirror_bridge::bind_class<cbref::Server>(m, "Server");
)
