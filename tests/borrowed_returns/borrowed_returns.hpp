#pragma once

#include <array>
#include <functional>
#include <map>
#include <memory>
#include <optional>
#include <string>
#include <system_error>
#include <tuple>
#include <utility>
#include <vector>

// The shape of a factory-style C++ API: one object owns the others, hands
// them out as raw pointers, and frees them itself. tinyxml2's XMLDocument and
// box2d's b2World are both this, and in both the handed-out class is the
// central one.
namespace borrowed {

// How many Nodes and Items exist, counted by their constructors and
// destructors. A borrow must never move `destroyed`.
struct Tally {
    static inline int live = 0;
    static inline int destroyed = 0;
    static int alive() { return live; }
    static int freed() { return destroyed; }
    static void reset() { live = 0; destroyed = 0; }
};

class Tree;

// tinyxml2::XMLElement: constructor and destructor are the owner's alone, so
// the only way to hold one is to be handed a pointer to it.
class Node {
public:
    int value() const { return value_; }
    void set_value(int v) { value_ = v; }

    Node* next() { return next_; }
    // Declared, as tinyxml2 does, beside its non-const twin. A Node cannot be
    // copied, so this one has no way to cross.
    const Node* next() const { return next_; }

    Node* first_child() { return child_; }
    Node* add_child(int v);

    Tree* tree() { return tree_; }

    // Written to be chained: node.bump()->bump().
    Node* bump() { ++value_; return this; }

    // A raw pointer nested inside something that otherwise converts. None of
    // these has a conversion, and each used to fail the module to compile as
    // soon as a class like this one stopped being skipped.
    void visit(const std::function<void(Node*)>& f) { f(this); }
    std::pair<Node*, bool> insert(int) { return {this, true}; }
    std::optional<Node*> maybe() { return this; }
    std::tuple<Node*, int> tagged() { return {this, 1}; }
    std::map<std::string, Node*> by_name() { return {{"self", this}}; }
    std::array<Node*, 2> both() { return {this, this}; }

private:
    friend class Tree;
    Node(Tree* tree, int v) : tree_(tree), value_(v) { ++Tally::live; }
    ~Node() { --Tally::live; ++Tally::destroyed; }
    Node(const Node&) = delete;
    Node& operator=(const Node&) = delete;

    Tree* tree_;
    int value_;
    Node* next_ = nullptr;
    Node* child_ = nullptr;
};

class Tree {
public:
    Tree() = default;
    ~Tree() { clear(); }
    Tree(const Tree&) = delete;
    Tree& operator=(const Tree&) = delete;

    Node* create(int v) {
        Node* n = new Node(this, v);
        if (!nodes_.empty()) nodes_.back()->next_ = n;
        nodes_.push_back(n);
        owned_.push_back(n);
        return n;
    }
    Node* root() { return nodes_.empty() ? nullptr : nodes_.front(); }
    Node* find(int v) {
        for (Node* n : nodes_) if (n->value_ == v) return n;
        return nullptr;
    }
    int size() const { return static_cast<int>(nodes_.size()); }

    // XMLDocument::Clear(), b2World::DestroyBody(): the owner stays alive and
    // frees what it handed out. A borrow taken earlier dangles after this.
    void clear() {
        for (Node* n : owned_) delete n;
        owned_.clear();
        nodes_.clear();
    }

private:
    friend class Node;
    std::vector<Node*> nodes_;   // top-level, in creation order
    std::vector<Node*> owned_;   // everything this tree frees
};

inline Node* Node::add_child(int v) {
    Node* n = new Node(tree_, v);
    n->next_ = child_;
    child_ = n;
    tree_->owned_.push_back(n);
    return n;
}

// An ordinary value class that a registry happens to hand out by pointer.
// Destructible and copyable, so both halves of the policy are visible on it.
struct Item {
    int id = 0;
    double weight = 0.0;

    Item() { ++Tally::live; }
    Item(int i, double w) : id(i), weight(w) { ++Tally::live; }
    Item(const Item& o) : id(o.id), weight(o.weight) { ++Tally::live; }
    Item& operator=(const Item&) = default;
    ~Item() { --Tally::live; ++Tally::destroyed; }

    void scale(double f) { weight *= f; }
    Item* self() { return this; }
};

struct Crate {
    Item first;
    Item second;
};

// A struct with a member that has no conversion. It used to be unbindable
// for that; now the member is what is left out. Nothing here binds it.
struct RawNode {
    int depth = 0;
    RawNode* children[8] = {};
};

struct Opaque;   // only ever forward declared

// A class template that cannot be instantiated over a forward-declared type.
// A pointer to such a specialization is a legal name, and asking how big it
// is fails the build instead of answering.
template<typename T>
struct Holder {
    T held;
};

// A base class with a protected destructor, which names itself by value in
// its own interface. A member may do that; code outside the class may not,
// and a binding is code outside the class.
class Sealed {
public:
    explicit Sealed(int v) : value_(v) {}
    int value() const { return value_; }
    const Sealed& self() const { return *this; }

    Sealed scaled(int f) const { return Sealed(value_ * f); }
    Sealed operator+(const Sealed& o) const { return Sealed(value_ + o.value_); }
    Sealed operator-() const { return Sealed(-value_); }
    static Sealed make() { return Sealed(0); }
    void absorb(Sealed other) { value_ += other.value_; }
    void sink(Sealed&& other) { value_ += other.value_; }
    // Declared only: even inside the class these cannot be defined, because
    // the standard library would have to destroy a Sealed.
    std::optional<Sealed> maybe() const;
    std::vector<Sealed> all() const;
    std::unique_ptr<Sealed> owned() const;
    std::vector<Sealed*> kids() const { return {}; }

protected:
    ~Sealed() = default;

private:
    int value_;
};

// What a Sealed is for: something concrete derives from it.
class Concrete : public Sealed {
public:
    Concrete() : Sealed(4) {}
};

// A class this module never binds.
struct Unbound {
    int x = 0;
};

// The ref-counted shape: anyone may make one, and only release() may free it.
class Counted {
public:
    explicit Counted(int v) : value_(v) { ++Tally::live; }
    int value() const { return value_; }
    void release() { delete this; }

private:
    ~Counted() { --Tally::live; ++Tally::destroyed; }
    int value_;
};

class Registry {
public:
    Registry() = default;
    Registry(const Registry&) = delete;
    Registry& operator=(const Registry&) = delete;

    void add(int id, double weight) { items_.push_back(std::make_unique<Item>(id, weight)); }

    // Each pointer overload is declared FIRST and would accept the argument
    // its sibling was always called with: an int converts to double and to
    // long, a str to const char*.
    Item* pick(double key) { return get(static_cast<int>(key)); }
    int pick(int key) { return key * 10; }
    Item* flag(long id) { return get(static_cast<int>(id)); }
    bool flag(bool on) { return !on; }
    Item* named(const char*) { return nullptr; }
    std::string named(const std::string& s) { return "str:" + s; }

    // Callable on an rvalue only, which a wrapper's object never is.
    Item* take() && { return nullptr; }
    int drain() && { return 0; }

    // Neither of these returns anything the registry owns: the result is the
    // caller's argument, or a part of it.
    Item* same(Item& item) { return &item; }
    Item* second_of(Crate& crate) { return &crate.second; }

    // Mutable pointer: the caller is looking at the registry's own Item.
    Item* get(int id) {
        for (auto& it : items_) if (it->id == id) return it.get();
        return nullptr;
    }
    // Const pointer, and no non-const twin: not bound. A wrapper is a
    // mutable handle, so borrowing here would let Python write through a
    // pointer C++ declared read-only.
    const Item* peek(int id) const {
        for (auto& it : items_) if (it->id == id) return it.get();
        return nullptr;
    }

    // The pair every container-like class declares. C++ picks the non-const
    // one for a non-const object, whichever is written first.
    const Item* at(int index) const { return items_.at(index).get(); }
    Item* at(int index) { return items_.at(index).get(); }

    // The same pair the other way round, so neither order is the one that
    // happens to work.
    Item* front() { return items_.front().get(); }
    const Item* front() const { return items_.front().get(); }

    Unbound* unbound() { return &unbound_; }
    Counted* counted() { return counted_; }
    Sealed* sealed() { return &sealed_; }

    // The iterator protocol. end() is one past the last Item, and data() is
    // not an Item at all when the registry is empty.
    Item* begin() { return slab_; }
    Item* end() { return slab_ + 2; }
    Item* data() { return slab_; }
    int canary() const { return canary_; }

    // A pointer to a specialization that cannot be completed.
    Holder<Opaque>* holder() { return nullptr; }

    // Pointers to classes that could never be bound, so there is no wrapper
    // type a borrow of them could ever have.
    std::error_code* last_error() { return &error_; }
    RawNode* raw_root() { return &raw_; }

    // A container of pointers. Never convertible, and until now a compile
    // error for the module rather than a declined method.
    std::vector<Item*> all_items() {
        std::vector<Item*> out;
        for (auto& it : items_) out.push_back(it.get());
        return out;
    }

    double total() const {
        double t = 0.0;
        for (auto& it : items_) t += it->weight;
        return t;
    }

    // None of these has a receiver that owns what comes back, or names a
    // class that can be wrapped, so each stays unbound.
    static Item* shared_default() { static Item item(-1, 0.0); return &item; }
    Opaque* handle() { return nullptr; }
    Item** slots() { return nullptr; }
    int* raw_counter() { return &counter_; }

    static const Item* default_item() { static Item item(-2, 1.5); return &item; }

private:
    std::vector<std::unique_ptr<Item>> items_;
    int counter_ = 0;
    Unbound unbound_;
    Counted* counted_ = new Counted(9);
    Concrete sealed_;
    std::error_code error_;
    RawNode raw_;
    Item slab_[2];
    int canary_ = 0x5afe;   // sits right where end() points

public:
    ~Registry() { counted_->release(); }
};

// An intrusive handle. It names Pinned, which nobody outside may destroy,
// and holds only a pointer to one, so it is an ordinary destructible value.
class Pinned {
public:
    Pinned() = default;
    int get() const { return 11; }
    void retain() { ++refs_; }
    void release() { if (--refs_ == 0) delete this; }

protected:
    ~Pinned() = default;
    int refs_ = 0;
};

template<typename T>
class Ref {
public:
    Ref() = default;
    explicit Ref(T* p) : p_(p) { if (p_) p_->retain(); }
    Ref(const Ref& o) : p_(o.p_) { if (p_) p_->retain(); }
    Ref& operator=(const Ref& o) {
        if (o.p_) o.p_->retain();
        if (p_) p_->release();
        p_ = o.p_;
        return *this;
    }
    ~Ref() { if (p_) p_->release(); }
    bool valid() const { return p_ != nullptr; }
    int value() const { return p_->get(); }

private:
    T* p_ = nullptr;
};

class Vault {
public:
    Ref<Pinned> root() { return root_; }
    int use(Ref<Pinned> r) { return r.value() + 1; }
    std::shared_ptr<Pinned> shared() { return nullptr; }
    int size() const { return 1; }

private:
    Ref<Pinned> root_{new Pinned};
};

inline Ref<Pinned> make_pinned() { return Ref<Pinned>(new Pinned); }
inline int use_pinned(Ref<Pinned> r) { return r.value() + 2; }

// The opaque-handle idiom with a type parameter: declared, never defined.
template<typename T> struct Opaque2;

struct Opener {
    Opaque2<int>* open() { return nullptr; }
    void close(Opaque2<int>*) {}
    void finish(Opaque2<int> handle);
    int n() const { return 1; }
};

// Data members that carry raw pointers have no conversion. They are left out
// and the class binds with what remains; before, the class was skipped with
// a message, and before that it was a compile error.
struct PointerBag {
    int n = 0;
    std::vector<Item*> items;
    std::map<std::string, Item*> by_name;
};

// No receiver, so nothing to keep alive: both stay unbound.
inline Item* global_item() { static Item item(-3, 0.0); return &item; }
inline const Item* global_default() { static Item item(-4, 2.5); return &item; }

// A Python subclass of a class with a protected destructor. The trampoline
// is an ordinary destructible class, so `new Trampoline_Listener()` compiles;
// what cannot happen is the wrapper, which only knows it as a Listener,
// ever freeing it.
class Listener {
public:
    Listener() { ++Tally::live; }
    virtual int on_event(int x) { return x; }
    int fire(int x) { return on_event(x); }

protected:
    ~Listener() { --Tally::live; ++Tally::destroyed; }
};

}  // namespace borrowed
