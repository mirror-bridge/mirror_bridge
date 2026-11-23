#pragma once
#include "python/mirror_bridge_annotations.hpp"

// A data member with no conversion must cost itself and not its class.
//
// It used to cost the class: under auto discovery one raw pointer field got
// the whole class skipped, methods and all. Dear ImGui lost ImGuiIO,
// ImDrawList and seventeen others that way, and box2d its b2FixtureDef and
// b2JointDef, which is every way of putting a shape or a joint in a world.
namespace dm {

struct Engine {
    int rpm = 900;
};

// b2FixtureDef: plain settings beside a pointer the library reads and an
// opaque slot for the caller.
struct FixtureDef {
    float friction = 0.25f;
    float density = 1.0f;
    const Engine* shape = nullptr;
    void* user_data = nullptr;
    bool is_sensor = false;

    float mass() const { return density * 2.0f; }
    bool has_shape() const { return shape != nullptr; }
};

// ImGuiIO: callbacks among the settings.
struct IO {
    float delta_time = 0.5f;
    void (*set_clipboard)(const char*) = nullptr;
    int (IO::*handler)(int) = nullptr;
    int frame = 0;

    int next_frame() { return ++frame; }
};

// The member with no conversion is inherited.
struct Base {
    int* raw = nullptr;
    int kept = 5;
};

struct Derived : Base {
    int own = 6;
    int total() const { return kept + own; }
};

// Nothing left once the members are gone, and still worth binding for what
// it does.
struct Handles {
    void* first = nullptr;
    void* second = nullptr;
    int count() const { return 2; }
};

// The remedy the static_assert always recommended, on a type that needs it.
// The assertion never read the annotation, so this did not compile.
struct Marked {
    [[=mirror_bridge::exclude{}]] int* secret = nullptr;
    int shown = 1;
};

// A class with a declined member used every way a class is used: held as a
// member, returned by pointer, returned by value, taken by reference.
struct World {
    FixtureDef def;
    Engine engine;

    FixtureDef* fixture() { return &def; }
    FixtureDef copy() const { return def; }
    void apply(const FixtureDef& other) { def = other; }
    void attach() { def.shape = &engine; }
};

}  // namespace dm
