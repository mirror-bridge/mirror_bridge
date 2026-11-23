#pragma once
#include <vector>

// A method this backend cannot call must cost itself and not the module.
//
// Lua and JavaScript convert each argument into a local, move the locals
// into the call and convert the result, and nothing asked first whether a
// given method allowed that. One pointer return in one class was a compile
// error for every class beside it, which is every factory-style library:
// tinyxml2, box2d, Dear ImGui. tests/js/declined_methods holds a copy of
// this header.
namespace dmeth {

struct Item {
    int value = 1;
};

struct NoDefault {
    explicit NoDefault(int v) : v(v) {}
    int v;
};

struct Shelf {
    Item item;
    int count = 0;

    // Bound: every step of the call is possible.
    int size() const { return count; }
    Item first() const { return item; }
    void put(const Item& i) { item = i; ++count; }
    const char* label() const { return "shelf"; }
    static int capacity() { return 8; }

    // Bound, and worth saying so: these two backends have always carried a
    // mutable `char*` as a string, and a gate whose job is to turn a compile
    // error into a missing method has no business taking away one that
    // compiled. (Python refuses `char*`; that is Python's rule.)
    char* scratch() { static char text[] = "mut"; return text; }
    std::vector<char*> words() { static char a[] = "one"; static char b[] = "two"; return {a, b}; }
    char* dual() { static char text[] = "nc"; return text; }
    const char* dual() const { return "c"; }

    // Not bound, each for its own reason.
    Item* find(int) { return &item; }                       // pointer return
    const Item* peek() const { return &item; }
    void adopt(Item* i) { if (i) item = *i; }               // pointer parameter
    void release(void* block) { (void)block; }
    void fill(Item& out) const { out = item; }              // the write would be lost
    void each(void (*visit)(int)) { if (visit) visit(count); }
    std::vector<Item*> all() { return {&item}; }            // pointer inside a container
    int weigh(NoDefault n) const { return n.v; }            // no local can be built
    static Item* shared() { static Item i; return &i; }

    // Two overload sets with one member that cannot be called, declared
    // first in one and last in the other. Lua reaches the first overload
    // that is offered and JavaScript the last, so each backend has one set
    // where the uncallable overload used to stand in the way.
    int pick(Item* i) { return i ? -1 : -2; }
    int pick(int i) { return i; }
    int take(int i) { return i + 1; }
    int take(Item* i) { return i ? -1 : -2; }
};

}  // namespace dmeth
