#pragma once

#include <string>
#include <vector>

namespace ptrparams {

struct Vec2 {
    double x = 0;
    double y = 0;
};

struct BodyDef {
    double x = 0;
    double y = 0;
    int kind = 0;
};

// Owned by its World, like b2Body: nothing outside World may build or free one.
class Body {
public:
    double x() const { return x_; }
    int kind() const { return kind_; }
    void move(double dx) { x_ += dx; }

private:
    friend class World;
    explicit Body(const BodyDef& def) : x_(def.x), kind_(def.kind) {}
    ~Body() = default;
    double x_;
    int kind_;
};

struct Shape {
    virtual ~Shape() = default;
    virtual double area() const { return 0; }
};

struct Circle : Shape {
    double r = 1;
    double area() const override { return 3 * r * r; }
};

struct Tagged {
    int tag = 7;
};

// Shape is the SECOND base, so a Square's Shape subobject is not at the
// Square's own address. A pointer passed without the base adjustment makes
// area() read Tagged::tag as a vtable pointer.
struct Square : Tagged, Shape {
    double side = 2;
    double area() const override { return side * side; }
};

struct Opaque;

class World {
public:
    World() = default;
    World(const World&) = delete;
    World& operator=(const World&) = delete;
    ~World() {
        for (Body* body : bodies_) delete body;
    }

    // `def` is a Python keyword, as it is in box2d's own header.
    Body* CreateBody(const BodyDef* def) {
        bodies_.push_back(new Body(*def));
        return bodies_.back();
    }

    void DestroyBody(Body* body) {
        for (auto it = bodies_.begin(); it != bodies_.end(); ++it) {
            if (*it == body) {
                delete body;
                bodies_.erase(it);
                return;
            }
        }
    }

    int index_of(const Body* body) const {
        for (std::size_t i = 0; i < bodies_.size(); ++i) {
            if (bodies_[i] == body) return static_cast<int>(i);
        }
        return -1;
    }

    void nudge(Body* body, double dx) { body->move(dx); }
    void scale(Vec2* v, double by) { v->x *= by; v->y *= by; }
    double area_of(const Shape* shape) const { return shape->area(); }

    // Hands back its argument, which the world does not own.
    Vec2* same(Vec2* v) { return v; }

    // Defaulted: the header says null is an expected argument.
    int kind_or(const Body* body = nullptr, int fallback = -1) const {
        return body ? body->kind() : fallback;
    }
    // Not defaulted: dereferences without a check, as real libraries do.
    int kind_of(const Body* body) const { return body->kind(); }

    // One object beside an integer that is not a count.
    double x_times(const Vec2* point, int factor) const { return point->x * factor; }

    // Arrays. Each of these reads past a single object.
    double sum_x(const Vec2* points, int count) const {
        double total = 0;
        for (int i = 0; i < count; ++i) total += points[i].x;
        return total;
    }
    double sum_leading(int numPoints, const Vec2* points) const { return sum_x(points, numPoints); }
    double sum_unnamed(const Vec2*, int) const { return 0; }
    double sum_sized(const Vec2* points, std::size_t vertexCount) const {
        return sum_x(points, static_cast<int>(vertexCount));
    }

    // Declared pointer-first on purpose: the reference overload is the one
    // that was bound before pointers could be, and it has to keep its calls.
    int which(Body*) { return 2; }
    int which(const Body&) { return 1; }

    // Shapes that stay refused.
    bool find(int index, Body*& out) {
        out = bodies_.at(static_cast<std::size_t>(index));
        return true;
    }
    void take_opaque(Opaque*) {}
    void take_string(std::string*) {}
    void take_int(int*) {}
    void take_pointers(Body**) {}

    int name_length(const char* name) const { return static_cast<int>(std::string(name).size()); }

    static double double_x(const Vec2* v) { return 2 * v->x; }

    std::size_t body_count() const { return bodies_.size(); }

private:
    std::vector<Body*> bodies_;
};

// A constructor that takes a pointer keeps it far more often than not, so
// these stay unbound until the new object can keep its argument alive.
class Joint {
public:
    Joint() = default;
    Joint(Body* a, Body* b) : a_(a), b_(b) {}
    int ends() const { return (a_ ? 1 : 0) + (b_ ? 1 : 0); }

private:
    Body* a_ = nullptr;
    Body* b_ = nullptr;
};

inline double free_x(const Vec2* v) { return v->x; }

}  // namespace ptrparams
