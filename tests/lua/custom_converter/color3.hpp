// Custom type for testing type converter extension
// This type is NOT reflected - it will be converted via custom converters

#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

// A simple RGB color type that we'll convert to/from language-native types
// This simulates third-party types like Eigen::Vector3d
struct Color3 {
    uint8_t r = 0;
    uint8_t g = 0;
    uint8_t b = 0;

    Color3() = default;
    Color3(uint8_t r_, uint8_t g_, uint8_t b_) : r(r_), g(g_), b(b_) {}

    bool operator==(const Color3& other) const {
        return r == other.r && g == other.g && b == other.b;
    }
};

// A struct that USES Color3 - this gets reflected and bound normally
struct Pixel {
    int x = 0;
    int y = 0;
    Color3 color;

    Pixel() = default;
    Pixel(int x_, int y_, Color3 c) : x(x_), y(y_), color(c) {}

    // Method that returns a Color3
    Color3 get_color() const { return color; }

    // Method that takes a Color3 parameter
    void set_color(Color3 c) { color = c; }

    // Method that modifies and returns Color3
    Color3 inverted_color() const {
        return Color3(255 - color.r, 255 - color.g, 255 - color.b);
    }
};

// A container of the library's own that holds raw pointers, converted by
// plain overloads like Color3 above. Nothing in mirror_bridge can convert a
// Tag* element, so without a converter a member of this type is left out of
// its class. With one it crosses, and since a plain overload is not something
// the member gate can see, the binding says so in one line (see
// pixel_binding.cpp).
struct Tag {
    int id = 0;
};

template<typename T>
struct Bag {
    using value_type = T;
    std::vector<T> items;
    auto begin() const { return items.begin(); }
    auto end() const { return items.end(); }
    std::size_t size() const { return items.size(); }
};

struct Scene {
    Tag first{7};
    Tag second{9};
    Bag<Tag*> tags{{&first, &second}};
    int count = 2;
};

// An opaque handle, the shape every C API hands out. A raw pointer has no
// conversion, so open() and close() are left out of the class unless the
// binding supplies one, and then they must be bound.
struct Opaque;
typedef Opaque* Handle;

struct Pool {
    int opened = 0;
    Handle open() { ++opened; return reinterpret_cast<Handle>(this); }
    bool close(Handle handle) { return handle == reinterpret_cast<Handle>(this); }
};
