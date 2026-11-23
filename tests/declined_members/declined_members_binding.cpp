#include "python/mirror_bridge_python.hpp"
#include "declined_members.hpp"

// bind_class_when_bindable is what `mirror_bridge generate` emits. Marked
// goes through the hand-written bind_class on purpose: its one unconvertible
// member is annotated, which is the only way that binder accepts one.
MIRROR_BRIDGE_MODULE(declined_members,
    mirror_bridge::bind_class_when_bindable<dm::Engine>(m, "Engine");
    mirror_bridge::bind_class_when_bindable<dm::FixtureDef>(m, "FixtureDef");
    mirror_bridge::bind_class_when_bindable<dm::IO>(m, "IO");
    mirror_bridge::bind_class_when_bindable<dm::Base>(m, "Base");
    mirror_bridge::bind_class_when_bindable<dm::Derived>(m, "Derived");
    mirror_bridge::bind_class_when_bindable<dm::Handles>(m, "Handles");
    mirror_bridge::bind_class<dm::Marked>(m, "Marked");
    mirror_bridge::bind_class_when_bindable<dm::World>(m, "World");
    mirror_bridge::bind_class_when_bindable<dm::Log>(m, "Log");
)
