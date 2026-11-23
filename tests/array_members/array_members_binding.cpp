#include "python/mirror_bridge_python.hpp"
#include "array_members.hpp"

MIRROR_BRIDGE_MODULE(array_members,
    mirror_bridge::bind_class<arr::Label>(m, "Label");
    mirror_bridge::bind_class<arr::Brimful>(m, "Brimful");
    mirror_bridge::bind_class<arr::Tint>(m, "Tint");
    mirror_bridge::bind_class<arr::Grid>(m, "Grid");
    mirror_bridge::bind_class<arr::Huge>(m, "Huge");
    mirror_bridge::bind_class<arr::Names>(m, "Names");
    mirror_bridge::bind_class<arr::Constants>(m, "Constants");
)
