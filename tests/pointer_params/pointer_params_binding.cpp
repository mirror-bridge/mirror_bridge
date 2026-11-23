#include "python/mirror_bridge_python.hpp"
#include "pointer_params.hpp"

MIRROR_BRIDGE_MODULE(pointer_params,
    mirror_bridge::bind_class<ptrparams::Vec2>(m, "Vec2");
    mirror_bridge::bind_class<ptrparams::BodyDef>(m, "BodyDef");
    mirror_bridge::bind_class<ptrparams::Body>(m, "Body");
    mirror_bridge::bind_class<ptrparams::Shape>(m, "Shape");
    mirror_bridge::bind_class<ptrparams::Circle>(m, "Circle");
    mirror_bridge::bind_class<ptrparams::Square>(m, "Square");
    mirror_bridge::bind_class<ptrparams::World>(m, "World");
    mirror_bridge::bind_class<ptrparams::Joint>(m, "Joint");
    mirror_bridge::bind_function_when_bindable<&ptrparams::free_x>(m, "free_x");
)
