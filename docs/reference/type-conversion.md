# Type Conversion Reference

Mirror Bridge automatically converts types between C++ and target languages. This document details all supported conversions.

## Primitive Types

### Numeric Types

| C++ Type | Python | Lua | JavaScript |
|----------|--------|-----|------------|
| `bool` | `bool` | `boolean` | `boolean` |
| `char` | `int` | `number` | `number` |
| `short` | `int` | `number` | `number` |
| `int` | `int` | `number` | `number` |
| `long` | `int` | `number` | `number` |
| `long long` | `int` | `number` | `number` |
| `unsigned int` | `int` | `number` | `number` |
| `float` | `float` | `number` | `number` |
| `double` | `float` | `number` | `number` |

### String Types

| C++ Type | Python | Lua | JavaScript |
|----------|--------|-----|------------|
| `std::string` | `str` | `string` | `string` |
| `std::string_view` | `str` | `string` | `string` |
| `const char*` | `str` | `string` | `string` |
| `char[N]` data member | `str` | `string` | `string` |

## Container Types

### Sequential Containers

| C++ Type | Python | Lua | JavaScript |
|----------|--------|-----|------------|
| `std::vector<T>` returned from a method (numeric T) | `array.array` (bulk memcpy) | `table` (array) | `Array` |
| `std::vector<T>` returned from a method (other T) | `list` | `table` (array) | `Array` |
| `std::vector<T>` read as a **data member** | live view (see below) | `table` (array) | `Array` |
| `std::array<T, N>` | `list` | `table` (array) | `Array` |
| `T[N]` data member (not `char`) | `list` | `table` (array) | `Array` |
| `std::deque<T>` | `list` | `table` (array) | `Array` |
| `std::list<T>` | `list` | `table` (array) | `Array` |

**A vector data member is a live view, not a copy.** Reading one gives an
object that holds a pointer to the C++ vector itself and a reference to its
owner, so `obj.points.append(p)` and `obj.points[0] = p` reach the C++ object
instead of mutating a temporary that is then discarded. It registers as a
`collections.abc.MutableSequence`, which is what the `.pyi` says it is, and
supports `len`, indexing, negative indices, iteration, `in`, `==` against any
sequence, `append`, `extend`, `insert`, `pop`, `clear`, `del` and `tolist()`.
A numeric one also exports the buffer protocol, so `numpy.asarray(obj.xs)`
shares the vector's own storage rather than copying it.

Because the view does not copy, reading a member is O(1) instead of O(n):
measured on a `vector<double>` member, 122 ns to 44 ns at ten elements and
54.0 us to 44 ns at a hundred thousand.

Three cases deliberately keep the copy they always had:

- **A method return.** A reference out of a method cannot be shown to point
  inside the receiver, so there is nothing to keep alive and nothing to view.
- **A `const` member.** A writable view of one would get around what C++ said.
- **`std::vector<bool>`.** It packs its elements and yields a proxy, so there
  is no element to take a reference to.

A slice (`v[:]`), `list(v)` and `v.tolist()` each give a real copy, which is
how you take a snapshot. Resizing is refused with `BufferError` while a
`memoryview` or numpy array is outstanding, because it would reallocate the
storage they point at. Holding an element of a vector of classes across an
`append` has the same hazard the underlying C++ reference would.
**Vectors of plain structs**: `std::vector<Point3>` returns a list of `Point3` objects by default. With `--columnar` it returns a sequence that also describes its own memory, so `np.asarray` reads it without copying and the dtype is built from the struct's reflected layout. Measured 21x at ten elements rising to about 200x from a thousand up. Off by default because it changes the return type; see [columnar-returns.md](../guides/columnar-returns.md).

**Bulk transfer optimization**: For `vector<float>`, `vector<double>`, `vector<int>`, and other numeric types, Python bindings copy the buffer in bulk into an `array.array` object instead of converting element by element. This is ~10-50x faster for large arrays. At or above 1 KB the buffer is copied once, out of the C++ container through a borrowed `memoryview`; below that it goes through an intermediate `bytes` object, which is two copies but one fewer call into the interpreter and measurably cheaper at that size. The crossover is a measured one and can be moved with `-DMIRROR_BRIDGE_ARRAY_BORROW_BYTES=<n>`. The `from_python` direction accepts both `list` and `array.array` inputs.

**Example:**

```cpp
struct Container {
    std::vector<int> numbers;
    std::vector<std::string> names;
};
```

**Python:**
```python
c = Container()
c.numbers = [1, 2, 3, 4, 5]
c.names = ["Alice", "Bob"]
print(c.numbers)  # array('i', [1, 2, 3, 4, 5])  -- see the note above
```

**Lua:**
```lua
c = Container()
c.numbers = {1, 2, 3, 4, 5}
c.names = {"Alice", "Bob"}
```

**JavaScript:**
```javascript
const c = new Container();
c.numbers = [1, 2, 3, 4, 5];
c.names = ["Alice", "Bob"];
```

**A `std::array<T, N>` takes exactly `N` elements**, in every backend. A list,
table or `Array` of any other length is refused, and so is one holding an
element that does not convert; a refused assignment leaves the member as it
was. Lua and JavaScript used to accept any length and keep none of it, so a
member read back as uninitialised memory and a parameter arrived as zeros.

**A C array member is the same thing spelled the old way.** `float rgba[4]`
reads as a list, table or `Array` of four and takes exactly four; `int
cells[3][3]` nests one level per extent. As with `std::array`, a refused
assignment leaves the member as it was. A static array member is a class
attribute in Python.

**A fixed `char` buffer is the string it holds.** `char name[64]` reads up to
its first NUL, or to the end of the array if there is none, and never past
it. Writing takes a string whose UTF-8 form fits with its terminator and
zeroes the rest of the buffer. A string that does not fit, or that has a NUL
inside it (which would be stored whole and read back cut short), is refused
with the reason in the message (`ValueError` in Python, `RangeError` in
JavaScript, an error in Lua) and is never truncated. A number is not coerced.
`signed char[N]` and `unsigned char[N]` are arrays of numbers, not strings. C#
does not carry C arrays yet and says so per member.

In Python, `bytes` are stored as they are: up to all `N` of them, with no
terminator required. That is the exact form, and it is what pickling and
`copy.copy` use, so a buffer that was full to the brim or held bytes that are
not UTF-8 comes back byte for byte. Read as a `str`, such bytes show as
U+FFFD, because the read also happens inside `repr()`. One consequence in
every backend: a buffer with no terminator reads as `N` characters, and that
string cannot be written back as text, since there is no room for the
terminator.

**An array of `const char*` or `std::string_view` is readable and not
assignable.** Assigning it would store pointers into strings the host
language owns and may free as soon as the assignment returns.

**A large array member is fine.** `double samples[2000000]` is converted on
the heap before it is stored, not on the stack.

**An element can be anything a single value can be.** A `std::vector` of a
bound class, of `std::optional`, `std::pair` or `std::shared_ptr`, a
`std::array` of a bound class, and `std::vector<bool>` all cross in Lua and
JavaScript, where each used to fail the whole module to compile. A vector of a
class with no default constructor reads but refuses assignment, because each
element is converted into a local first. A `std::span` parameter is refused at
the call in Lua and JavaScript: a table or `Array` has no storage for it to
view, and it used to arrive empty.

### Associative Containers

| C++ Type | Python | Lua | JavaScript |
|----------|--------|-----|------------|
| `std::map<K, V>` | `dict` | `table` | `Object` |
| `std::unordered_map<K, V>` | `dict` | `table` | `Object` |
| `std::multimap<K, V>`, `std::unordered_multimap<K, V>` | `list` of `(key, value)` | array of `{key, value}` | `Array` of `[key, value]` |

A key may repeat in a multimap, so it is not a dict: it reads as its pairs,
in the container's own order, and is written from the same shape. Python also
takes a `dict` and Lua a `key = value` table, for the common case of one value
per key. A value that is not pairs of the right types is refused whole and
leaves the target as it was.

## Nested Objects

Nested structs/classes are converted to native dictionary/object/table types:

**C++:**
```cpp
struct Address {
    std::string street;
    std::string city;
    int zip;
};

struct Person {
    std::string name;
    Address address;
};
```

**Python:**
```python
p = Person()
p.name = "Alice"
p.address = {"street": "123 Main St", "city": "Boston", "zip": 12345}

# Reading nested objects
addr = p.address  # Returns a dict
print(addr["city"])  # "Boston"
```

**Lua:**
```lua
p = Person()
p.name = "Alice"
p.address = {street = "123 Main St", city = "Boston", zip = 12345}
```

**JavaScript:**
```javascript
const p = new Person();
p.name = "Alice";
p.address = {street: "123 Main St", city: "Boston", zip: 12345};
```

## Smart Pointers

| C++ Type | Conversion |
|----------|------------|
| `std::unique_ptr<T>` | Converted to/from value |
| `std::shared_ptr<T>` | Converted to/from value |

**C++:**
```cpp
struct Resource {
    std::string name;
    int value;
};

struct Manager {
    std::unique_ptr<Resource> resource;
    std::unique_ptr<Resource> create_resource(std::string n, int v);
};
```

**Python:**
```python
m = Manager()

# Smart pointers convert to/from dicts
result = m.create_resource("test", 42)
print(result)  # {"name": "test", "value": 42}

# Assign dict to smart pointer property
m.resource = {"name": "data", "value": 123}

# None handling for null pointers
m.resource = None  # Sets to nullptr
```

A pointee that cannot be built from a host value — an abstract class, one with
no default constructor, or one that is not copy-assignable — converts only from
`None`/`nil`/`null`, which resets the pointer. Anything else is refused. In Lua
and JavaScript it used to "convert" to a null pointer, so an assignment
silently cleared the member and a parameter handed C++ `nullptr` to
dereference. Sharing ownership with a host object — passing a bound `Circle`
where a `std::shared_ptr<Shape>` is expected — is
[#54](https://github.com/FranciscoThiesen/mirror_bridge/issues/54).

## Enum Types

| C++ Type | Python | Lua | JavaScript |
|----------|--------|-----|------------|
| `enum` | `enum.IntEnum` | `number` | `number` |
| `enum class` | `enum.IntEnum` | `number` | `number` |

The Python backend exports the enum *type* as an `enum.IntEnum` whose members
carry the C++ enumerator names and values. Nothing about the *value*
conversion changed, because an `IntEnum` member is an `int`: a function that
took a bare `int` still takes one, and one that returns an enum still returns
a plain `int`, which compares equal to the member. An enumerator whose name is
a Python keyword gets a trailing underscore, since `Permission.None` is a
syntax error rather than an attribute lookup. Lua and JavaScript have no enum
object to map onto and their values keep crossing as numbers.

**C++:**
```cpp
enum class Color { Red = 0, Green = 1, Blue = 2 };

struct ColoredShape {
    Color color;
    int get_color_value() const { return static_cast<int>(color); }
};
```

**Python:**
```python
s = ColoredShape()
s.color = 1  # Green
print(s.get_color_value())  # 1
```

## Method Parameters

All supported types can be used as method parameters:

**C++:**
```cpp
struct Processor {
    // Primitive parameters
    int add(int a, int b);

    // String parameters
    void set_name(std::string name);

    // Container parameters
    double sum(std::vector<double> values);

    // Multiple parameters
    std::string format(std::string prefix, int value, std::string suffix);
};
```

**Python:**
```python
p = Processor()
result = p.add(10, 20)  # 30
p.set_name("MyProcessor")
total = p.sum([1.0, 2.0, 3.0])  # 6.0
text = p.format("Value: ", 42, "!")  # "Value: 42!"
```

## Return Values

All supported types can be returned from methods:

| Return Type | Conversion |
|-------------|------------|
| `void` | `None` / `nil` / `undefined` |
| Primitive types | Direct conversion |
| `std::string` | String type |
| Containers | List/Array/Table |
| Nested objects | Dict/Object/Table |
| Smart pointers | Converted value or null |

### A method that cannot be called is left out (Lua, JavaScript)

Lua and JavaScript call a method by converting each argument into a local of
the parameter's type, moving those into the call, and converting what comes
back. A method is bound when all three steps are possible and left out when
one is not:

| Left out when | For example |
|---------------|-------------|
| a parameter has no conversion, or no local of its type can be built | `adopt(Item*)`, `release(void*)`, `each(void (*)(int))`, a class with no default constructor taken by value |
| a parameter is a non-`const` reference | `fill(Item& out)`: the write would land in the local and be lost |
| the return type has no conversion | `Item* find(int)`, `std::vector<Item*> all()` |

A pointer type is asked of the backend's own overloads, so `char*` is a string here (as it always was in these two backends) and a handle type with `to_lua`/`from_lua` or `to_javascript`/`from_javascript` overloads of your own keeps its methods.

The class binds with every other method, and so does the rest of the module.
Each of these was a compile error for the whole module before, so one pointer
return anywhere meant no bindings at all. Where a name is overloaded, an
overload that cannot be called no longer stands in front of one that can.

Set `MIRROR_BRIDGE_REPORT_DECLINED=1` when the module loads to have each
method that was left out named on stderr with the step it failed at, in the
same line shape the Python backend uses:

```
mirror_bridge: skipped method 'Shelf::find' (the return type has no conversion to Lua)
mirror_bridge: skipped method 'Shelf::fill' (a parameter has no conversion from Lua)
```

### Pointer returns (Python)

A factory-style C++ API hands out the objects it owns as raw pointers:
`XMLDocument::RootElement()`, `b2World::GetBodyList()`. A `T*` does not say
who owns the `T`, so mirror_bridge answers the one case the signature settles
and refuses the rest, almost all of it by name at build time.

| Return | From | Crosses as |
|--------|------|------------|
| `T*`, `T` a bound class | an instance method | A **borrow**: a wrapper over the library's own object. It frees nothing, a write through it reaches the object, and it keeps the owner alive. `None` when null |
| `T*`, `T` a class that could be bound and that no loaded module binds | an instance method | Bound, and raises `TypeError` naming the class when called. Whether a class is bound is not known until the modules are loaded |
| `T*`, `T` a class that could never be bound: a standard-library class, `FILE`, a struct of raw pointers, a class that converts as a container | anywhere | Not bound |
| `T*` | a static method, a free function or an operator | Not bound. There is no receiver whose lifetime could stand in for the object's |
| `T*` | a method named `begin`, `end`, `data` or one of their `c`/`r` forms | Not bound. That is a position, not an object: `end()` is one past the last element |
| `const T*` | anywhere | Not bound. A wrapper is a mutable handle, so a borrow would let Python write through a pointer C++ declared read-only |
| `T**`, `int*`, a pointer to a forward-declared class or to a class template that is declared and never defined | anywhere | Not bound |
| a raw pointer inside a standard template: `std::vector<T*>`, `std::pair<T*, bool>`, `std::optional<T*>`, `std::map<K, T*>`, `std::function<void(T*)>` | a return, a parameter or a data member | Not bound. Such a data member is left out and its class binds without it |
| `T*` | a method that is `&&`-qualified | Not bound, like any `&&`-qualified method: a wrapper's object is never an rvalue |

```cpp
class Tree {
public:
    Node* create(int value);   // borrow
    Node* find(int value);     // borrow, or None
};
```

```python
tree = Tree()
node = tree.create(5)
node.set_value(6)             # changes the Tree's own Node
assert tree.find(6) is not None
assert tree.find(99) is None

node = Tree().create(5)       # the Tree has no other reference...
node.value()                  # ...and is still alive: the borrow holds it
```

**What keeps what alive.** A borrow holds a reference to the object the method
was called on, or, when that object is itself a borrow, to *its* owner. Walking
`doc.RootElement().FirstChildElement().FirstChildElement()` therefore pins the
document once per wrapper you keep, and no intermediate node. A method that
returns the receiver or its owner (`node.GetDocument()`, a setter that returns
`this`) returns the Python object that already exists, so
`node.GetDocument() is doc` and a Python subclass stays one through a chain of
calls. Any other object gets a new wrapper each time, so compare borrows by
what they hold and not with `is`.

A method that returns a pointer to one of its own *arguments*, or to a part
of one (`Node* attach(Node& child)` returning `&child`), is not returning
anything the receiver owns. The borrow then holds the argument, and when the
pointer is to the whole argument you get that same Python object back.

**A class nobody outside may destroy** — a private, protected or deleted
destructor, which is how tinyxml2 and box2d say "the library frees these" —
binds as a class that is only ever borrowed. Its methods work. Constructing
one from Python raises `TypeError`, including when it has a public constructor
or a trampoline, because nothing could free the result. A method of such a
class that returns or takes the class *by value* is not bound: receiving the
value would mean destroying it. The same goes for a standard wrapper that
holds one by value (`std::optional<V>`, `std::vector<V>`,
`std::unique_ptr<V>`). A template of your own that only points at one, such as
an intrusive `Ref<V>`, is an ordinary value and is unaffected, as are
`std::shared_ptr<V>` and `std::weak_ptr<V>`.

**Overloads.** Where a name is overloaded and only some overloads return a
pointer, the ones that do not are tried first, in declaration order, and the
pointer-returning ones after them. Those are the overloads that were bound
before pointer returns were, so no existing call changes its target: with
`Node* find(double)` declared ahead of `int find(int)`, `tree.find(3)` still
returns an `int` and `tree.find(3.0)` returns the `Node`.

**`const`/non-`const` pairs.** A class that declares both
`const Item* at(int) const` and `Item* at(int)` has one Python method `at`,
the non-`const` one, since that is the half that can cross. `generate` does not
list the `const` half as declined.

**What a borrow assumes, and no signature can tell it:**

- *The object belongs to the receiver, or is an argument.*
  `Node* Node::clone_into(Doc& target)` returns a new object that `target`
  owns and that lives outside it. The borrow keeps the receiver's owner
  alive, which is the wrong one, and dangles when `target` goes.
- *The pointer is to one object.* A method returning a pointer to the first
  element of an array gives you that element only.
- *The owner does not free the object while it is itself alive* —
  `XMLDocument::Clear()`, `b2World::DestroyBody()`. A wrapper taken earlier
  then points at freed memory, exactly as the `T*` would in C++.
- *The caller is not meant to free it.* A method whose returned pointer the
  caller should `delete` is bound as a borrow, and the object leaks. Return a
  `std::unique_ptr` instead.

Not covered yet: any `const T*` return, and returning the most-derived type
for a pointer to a polymorphic base (an `XMLNode*` that is really an
`XMLElement` arrives as an `XMLNode`; the library's own `ToElement()` narrows
it). Lua and JavaScript still refuse pointer returns; C# borrows them under
its own rules, described in
[the C# design notes](../internals/csharp-design.md#a-class-c-cannot-own-binds-borrow-only).

### Pointer parameters (Python)

`world.DestroyBody(body)`, `node.InsertEndChild(child)`,
`world.CreateBody(definition)`: a method that takes a pointer to a class takes
the object a wrapper already holds. It is passed by address, exactly as a
`T&` parameter is, so nothing is copied, a write through a `T*` reaches the
Python object, and a derived object is adjusted to the base the callee asked
for.

| Parameter | Of | Takes |
|-----------|----|-------|
| `T*` or `const T*`, `T` a class that can be bound | an instance or static method | An object of `T` or of a class derived from it. `None` only if the parameter has a default argument |
| the same, declared beside an integer named like a count (`points, count`; `numVertices, vertices`) or beside an unnamed integer | an instance or static method | Not bound. That is an array, and a wrapper holds one object |
| `T*` or `const T*` | a constructor, a free function or an operator | Not bound |
| `T*&`, `T**`, `int*`, a pointer to a standard-library class or to a forward-declared class | anywhere | Not bound |

```cpp
class World {
public:
    Body* CreateBody(const BodyDef* def);
    void DestroyBody(Body* body);
    int kind_or(const Body* body = nullptr, int fallback = -1) const;
    void Set(const Vec2* points, int count);   // not bound: an array
};
```

```python
world = World()
body = world.CreateBody(BodyDef())
world.kind_or(body)
world.kind_or(None)          # the header defaults it, so None is nullptr
world.kind_or()              # the same call
world.CreateBody(None)       # TypeError: no default, so no None
world.DestroyBody(body)      # `body` now dangles, as it would in C++
```

**`None`.** A null pointer is passed only where the header says one is
expected, and the one place a signature says that is a default argument. Every
other pointer parameter refuses `None` with a `TypeError`. Libraries routinely
dereference a pointer parameter without checking it, and an exception is a
better answer than a crash inside the library. The stub agrees:
`body: Body | None = ...` for the defaulted parameter and `def_: BodyDef` for
the other.

**Arrays.** `Set(const Vec2* points, int count)` reads `count` objects, and
binding it would let `shape.Set(vec, 8)` read seven objects past one. The
types do not tell that apart from `addWidget(Widget* w, int stretch)`, which
takes one object; the parameter names do. A pointer is taken to be an array
when the parameter before or after it is an integer whose name contains
`count`, `size`, `len`, `num` or `capacity`, or is `n`, `nb`, `cnt` or `sz`,
or is an integer with no name at all. `generate` lists such a method as
declined and says why.

**Overloads.** Where a class declares both `f(const T&)` and `f(T*)`, a call
with an object goes to the reference overload, whichever is declared first.
That is the overload such a call reached before pointer parameters were
bound, so no existing call changes its target.

**What a pointer parameter assumes, and no signature can tell it**, the same
as for a `T&` parameter:

- *The callee does not keep the pointer.* `world.SetContactListener(listener)`
  stores it. Keep the Python object alive yourself for as long as the world
  uses it, as you would in C++; nothing does that for you yet.
- *The callee does not free it, unless the library owns it already.*
  `world.DestroyBody(body)` is fine, since `body` is a borrow the world owns.
  Passing an object Python constructed to a method that deletes its argument
  frees it twice.
- *The pointer is to one object.* An array passed with no count in the
  signature cannot be told from a single object.

Constructors are left out because a constructor that takes a pointer nearly
always keeps it, and the new object cannot yet hold its argument alive. A
class whose only useful constructor takes a pointer still binds, with that
constructor missing.

## Const Correctness

Const methods are supported and bound correctly:

```cpp
struct Data {
    int value;

    int get_value() const { return value; }  // Bound
    void set_value(int v) { value = v; }      // Bound
};
```

## std::optional

| C++ Type | Python | Lua | JavaScript |
|----------|--------|-----|------------|
| `std::optional<T>` (with value) | Converted `T` | Converted `T` | Converted `T` |
| `std::optional<T>` (empty) | `None` | `nil` | `null` |

## std::expected

C++23's `std::expected<T, E>` maps naturally to each language's error handling idiom:

| C++ State | Python | Lua | JavaScript |
|-----------|--------|-----|------------|
| Success (has value) | Returns `T` | Returns `value, nil` | Returns `T` |
| Error (!has_value) | Raises `ValueError` | Returns `nil, error_string` | Throws `Error` |

**C++:**
```cpp
struct Service {
    std::expected<double, std::string> safe_divide(double a, double b) {
        if (b == 0.0) return std::unexpected("division by zero");
        return a / b;
    }
};
```

**Python:**
```python
svc = Service()
result = svc.safe_divide(10.0, 2.0)  # Returns 5.0
try:
    svc.safe_divide(10.0, 0.0)       # Raises ValueError("division by zero")
except ValueError as e:
    print(e)
```

**Lua:**
```lua
local svc = Service()
local result, err = svc:safe_divide(10.0, 2.0)  -- result=5.0, err=nil
local result, err = svc:safe_divide(10.0, 0.0)  -- result=nil, err="division by zero"
```

**JavaScript:**
```javascript
const svc = new Service();
const result = svc.safe_divide(10.0, 2.0);  // 5.0
try {
    svc.safe_divide(10.0, 0.0);  // throws Error("division by zero")
} catch (e) { console.error(e.message); }
```

## Constructor Calls

In Lua and JavaScript, a call with arguments goes to a constructor taking that
many, trying the constructors of that arity in declaration order; the first
whose arguments all convert is called. With no arguments, a
default-constructible class is default-constructed.

Arguments that no constructor accepts are refused. They used to be dropped in
favour of a default-constructed object: `Rect(2)` built a 0 x 0 rectangle and
an aggregate's `Point2(3, 4)` built (0, 0), with no error. The error names the
class and what would have worked:

```lua
Rect(2)          -- Rect: no constructor takes 1 argument (constructors take 0 or 2)
Rect(2, "tall")  -- Rect: argument 2 could not be converted from string
Point2(3, 4)     -- Point2 takes no constructor arguments (...); construct it with none and assign its members
Shape()          -- Shape is abstract in C++ and cannot be constructed; construct a concrete derived class
```

JavaScript raises the same messages as a `TypeError`. In Lua, `Rect(2, 3)`,
`Rect:new(2, 3)` and `Rect.new(2, 3)` are the same call; the dot form used to
skip its first argument.

A constructor is offered only if its arguments can be converted and passed the
way a call converts them. Left out are a deleted one, one an abstract class
declares, one taking a non-const reference (a converted argument is a
temporary, which a non-const reference cannot bind), one taking a class with no
default constructor, and one taking a raw pointer or a smart pointer to an
incomplete type. The class binds through its other constructors; each of these
used to fail the whole module to compile. A constructor inherited with
`using Base::Base;` is not offered either, because reflection does not list it
as a member of the derived class. The Python backend also honours default
arguments and keywords in a constructor call; Lua and JavaScript need the exact
count.

## Argument Type Checking

A parameter, data member, or container element whose type is a bound C++
class accepts only an object of that class, an object of a class derived
from it, or a host-language subclass of either. Anything else is refused:
`TypeError` in Python and JavaScript, a Lua error in Lua.

```python
curve = pricing.Curve()
pricing.discount(curve, 2.0)   # fine
pricing.discount(42, 2.0)      # TypeError: Argument 1: type conversion failed
pricing.discount(label, 2.0)   # TypeError, even though Label is also bound
```

```lua
local curve = pricing.Curve.new()
curve:at(2.0)        -- fine
curve.at(label, 2.0) -- error: at: expected Curve, got Label
```

```javascript
const curve = new pricing.Curve();
curve.at(2.0);                                  // fine
pricing.Curve.prototype.at.call(label, 2.0);    // TypeError: at: expected Curve, got Label
```

A plain value written in place of an object is a separate question, and the
backends answer it differently. Lua accepts a table with the class's fields
wherever a bound class is expected: as a top-level argument or member a missing
field keeps its default, but inside a composite — a vector, array, optional,
variant, map or smart pointer — the table must have every field, because a
variant or an optional is asking whether the table *is* that class. JavaScript
accepts a plain object with every field inside a composite, and only a wrapper
at top level. A wrapper of an unrelated class is refused everywhere, even one
whose members happen to have the same names.

The receiver is checked as well as the arguments. `obj.method(x, ...)` in Lua
and `Class.prototype.method.call(x, ...)` in JavaScript reach the same code as
`obj:method(...)` and `obj.method(...)`, with whatever the caller put first as
`self`, so an object of the wrong class there is refused too.

Conversion to a base class is offset-adjusted, so it is correct for a base
that is not the first one:

```cpp
struct Swap : Observable, Priceable { ... };   // Priceable is not at offset 0
double value(const Priceable&);
```

```python
value(swap)   # reaches the Priceable subobject, not the start of the Swap
```

Virtual bases work too in Python: the offset is resolved at call time rather
than assumed.

The conversion is recorded by the derived class when it is bound, so the
base and the derived class may live in different modules and be loaded in
either order. Two cases are deliberately not convertible:

- A derived class whose module has never been loaded, because nothing has
  registered it yet.
- A base that C++ itself would not let you reach from that call site: one
  that is inaccessible (`private`/`protected`) or ambiguous because it is
  inherited twice non-virtually.

Inside an overload set a rejected argument simply moves to the next
candidate, so the error is raised only when no overload matches.

### What differs between the backends

| | Python | Lua | JS (N-API) | V8 (direct) |
|---|---|---|---|---|
| Wrong class refused | yes | yes | yes | untested |
| Derived-to-base, offset-adjusted | yes | yes | yes | untested |
| Same class bound by two modules | yes | yes | yes | untested |
| Derived class bound by *another* module | yes | yes | no | no |

The first three are what the identity check has to preserve. The fourth is
where the backends differ in how far their cross-module state reaches: Python
keeps it in `sys.modules` and Lua in the Lua registry, both shared by every
module in the process, while the N-API backend keeps its upcast table per
`.node` file — which matches the rest of that backend, where `to_javascript`
already falls back to a plain-object snapshot for a class the module did not
bind.

The V8 column is marked untested because it is. `javascript/mirror_bridge_v8.hpp`
does not compile against the V8 in the dev image (7.8, from `libnode-dev`): it
calls `String::NewFromUtf8Literal` and the one-argument
`String::NewFromUtf8`, both V8 8.x, and a bound-class parameter or data member
hits a declaration-order defect in `from_v8` besides. The gate it carries was
exercised by hand against a locally patched copy and behaved, but nothing in
CI covers it. Use the N-API backend.

Two modules recognise each other's objects by the class's reflected C++
spelling, so they have to spell it the same way. For every shape a discovered
class actually has — plain, nested, namespaced, inherited — clang-p2996 and
GCC 16 agree byte for byte, and `std::string` and `std::string_view` are
special-cased so they agree too. They do not agree on a key that names any
other standard-library template, because clang is only usable with libc++ and
that puts its ABI inline namespace in the name: `std::__1::vector<int, ...>`
against `std::vector<int, ...>`. Those keys reach error messages, not
identity, since a container can never be the expected class. The exception is
a class that *is* a template specialisation mentioning one — a hand-written
`bind_class<MyVec<int>>`, where `MyVec`'s defaulted allocator is spelled out,
or a discovered class deriving from one. Two such modules built by different
compilers would stop recognising each other, in a process where they are
already ABI-incompatible for other reasons.

### Forged identity

The check asks what a value *is*, so it is worth being precise about what it
trusts. Both backends read the answer out of memory the backend itself wrote
into the wrapper, after establishing that the memory is theirs:

- **Lua** reads the class's metatable address from the wrapper's payload,
  having first confirmed with `lua_touserdata` and `lua_rawlen` that the value
  is a full userdata long enough to hold one. It deliberately does *not* trust
  the metatable attached to the value, because Lua lets a script attach any
  metatable to any value — `setmetatable({}, getmetatable(curve))` needs no
  privileged library, and `debug.setmetatable` reaches userdata that belongs to
  other C libraries entirely. Nothing in Lua writes a full userdata's payload,
  so the payload cannot be forged the same way.
- **N-API** reads a magic word and then the class tag, because `napi_unwrap`
  establishes that an object was wrapped and not by whom: another addon's
  wrapped objects come back through it with that addon's payload layout.

Neither is a proof. A full userdata or a foreign payload whose first word
happened to match would be accepted, which is a coincidence a script cannot
aim for — it never learns the address and cannot write those bytes. N-API 8
(Node 14.17+) offers `napi_type_tag_object`, which would be a proof, at the
cost of a property lookup on every boundary crossing.

In Lua a plain table is still accepted where a bound class is expected: that
is how nested structs are written from Lua, and it reads the fields rather
than the object's bytes, so the check does not close it.

## Python Data Model

This section describes the Python backend. Lua and JavaScript bind neither
iteration nor serialization yet.

Four protocol slots are filled from the shape of the C++ class, with nothing
to declare per class.

| You write in C++ | Python gains |
|------------------|--------------|
| `begin()` / `end()` over convertible elements | `for x in obj`, `list(obj)`, `x in obj` |
| the above plus `size()` | `len(obj)`, and `bool(obj)` is `len(obj) != 0` |
| default-constructible, every member assignable | `pickle`, `copy.copy`, `copy.deepcopy` |

### Iteration

`tp_iter`/`tp_iternext` are generated from `begin()`/`end()`: `++it`, `*it`
and the sentinel comparison are splices, and the element goes through the
same conversion gate a method return value does. A range whose element has no
Python representation — a range of raw pointers, say — declines the slot
rather than failing the build. Membership needs nothing extra: with no
`sq_contains`, CPython answers `in` by iterating.

`end()` does not have to return the same type as `begin()`. A C++20 range
that ends at a sentinel iterates normally, and the element is taken from
`std::iterator_traits<It>::value_type` where the iterator has traits, so
`std::vector<bool>` yields `True`/`False` rather than the layout of the proxy
reference `*it` actually returns.

Iterating a `std::map`-shaped class yields `(key, value)` pairs, because that
is what the C++ range yields. `in` therefore tests pairs, not keys:
`("a", 1) in lookup` is `True` where `"a" in lookup` is `False`. This is the
one place where following the C++ range disagrees with the Python convention
that a mapping iterates its keys.

The iterator holds a reference to the object the range belongs to, so
`for x in make_bag()` is safe even though nothing else refers to the
container while the loop runs. This is the equivalent of pybind11's
`py::keep_alive<0, 1>()`, except that it is not something you can forget.

What ownership cannot fix is mutation: a `push_back` that reallocates
invalidates C++ iterators whoever holds the memory. The generated iterator
checks the two things it can check cheaply, and it is worth being precise
about what that does and does not cover.

| mutation during iteration | detected? |
|---|---|
| `push_back`, `insert`, `erase`, `clear` — the count moves | yes, `RuntimeError: Bag changed size during iteration` |
| `reserve`, `shrink_to_fit`, assigning a fresh container — the buffer moves, the count does not | yes, `RuntimeError: Bag reallocated its storage during iteration` |
| an `erase` paired with a `push_back` — same count, same buffer, elements shifted | **no** |
| anything at all, on a range whose iterator cannot be compared to another iterator | **no** |

The first check is the element count, the one CPython's own `dict` and `set`
iterators use; it needs `size()`, so a range without one does not get it. The
second re-reads `begin()` and compares, which is what catches the
reallocation that would otherwise read freed memory.

Neither check sees a mutation that preserves both the count and the buffer.
Such a range keeps iterating and yields shifted elements — wrong values read
from live memory, not a crash. **Mutating a container while iterating it is
undefined, exactly as it is in C++.** The guards turn the most common ways to
do it by accident into an exception; they are not a licence to do it.

### len() and truthiness

`len()` is offered only to a class that is both iterable and sized, never to
one that merely has a method spelled `size()`. The reason is truthiness: a
length slot is where CPython gets `bool(obj)` from, so gating on `size()`
alone would quietly turn `if obj:` into "it has elements" for a gauge whose
`size()` is a physical dimension. A class with `size()` and no range keeps
both its truthiness and its absence of `len()`.

A `size()` whose value will not fit a `Py_ssize_t` raises
`OverflowError: Bag.size() is 18446744073709551615, which cannot be a Python
length`. The realistic way to get there is an unsigned count that underflowed,
`items.size() - 1` on an empty container; reaching CPython as a negative
length instead produces only `SystemError: returned NULL without setting an
exception`.

### bool() is a behavior change

A class that is iterable and sized used to be truthy always, because nothing
in the type defined otherwise. It is now falsy when empty. This changes more
than `if obj:`:

```python
if bag: ...                  # now skipped when bag is empty
assert bag                   # now raises on an empty bag
bag or fallback              # now evaluates to fallback when bag is empty
[b for b in bags if b]       # now drops the empty ones
filter(None, bags)           # same
any(bags) / all(bags)        # now answer about emptiness
```

For a class that is really a container this is the Python semantics you want.
The case to look for is a container-shaped class used as a handle or a flag —
a `Connection` that happens to expose a queue through `begin()`/`end()` and
`size()`, where `if conn: conn.send(...)` used to mean "I have a connection"
and now means "my queue is non-empty". That reads the same and silently stops
sending.

The migration is to say what was meant: `if conn is not None:` for an
existence check, `if len(conn):` for a count. There is no per-class opt-out;
truthiness follows from the length slot, and a class gets the length slot only
by having both `begin()`/`end()` and `size()`. Removing `size()` from the
binding surface with `[[=exclude{}]]` is not an option either, since that
annotation applies to data members rather than methods.

One asymmetry is worth knowing: a range *without* `size()` has no length slot,
so it stays truthy even when empty. `bool()` therefore depends on whether the
class offers `size()`, not on whether it is a range.

A class with `operator[]` and `size()` but no `begin()`/`end()` is also not
covered. `mp_subscript` accepts whatever key `operator[]` takes, so reading a
`0..n-1` sequence out of it would be a guess; give the class `begin()` and
`end()` and it iterates.

### Pickling

`__reduce__` serializes the reflected non-static data member list — the same
walk `__repr__` uses, so a member added in C++ joins the pickle without
anyone editing a list. Reconstruction is `cls()` followed by `__setstate__`,
which is why a class qualifies only when Python can default-construct it and
assign every member back. Anything the state would not carry, or would not be
able to put back, disqualifies the class, and `pickle.dumps` raises
`TypeError: cannot pickle 'mod.Frozen' object` rather than handing back an
object that quietly lost a field:

| the class has | why it cannot round-trip |
|---|---|
| no default constructor | reconstruction is `cls()` |
| a `const` or `[[=readonly{}]]` member | read into the state, not assignable back out |
| a `private` member | not in the reflected visible member list, so the state never sees it |
| a `[[=exclude{}]]` member | same |
| a member declared by a base class | `nonstatic_data_members_of` reports direct members only |

The last three are the ones worth naming explicitly, because the member is
invisible from Python and an unpickled object would look right in `repr()`
while holding a default-constructed value for it.

A Python subclass pickles as itself, and its instance `__dict__` travels with
the C++ members.

For pickle to find the class again, a bound type's `tp_name` is
`<module>.<Class>`; CPython reads a static type's `__module__` from the text
before the last dot, and without it every bound class claimed to live in
`builtins`. `__name__`, `__qualname__` and `repr()` are unaffected.

### Hashing

No `tp_hash` is generated, which leaves two different behaviors depending on
whether the class defines `operator==`.

| the class | `hash()` | in a `set` or as a `dict` key |
|---|---|---|
| no `operator==` | identity hash | works; two equal-looking objects are two keys |
| has `operator==` | **unhashable** | `TypeError: unhashable type: 'mod.Point'` |

The second row is CPython's own rule, not a mirror_bridge decision:
`inherit_slots` copies `tp_hash` from the base only when `tp_richcompare` is
also being inherited, so a type that sets comparison and leaves hashing null
ends up with `__hash__` of `None` — the same state Python puts a class in when
it defines `__eq__` and no `__hash__`. It is self-consistent: you never get
`a == b` while `hash(a) != hash(b)`. It is also easy to trip over, because
`operator==` is the thing that takes the class out of a `set`:

```python
a == b          # True
{a, b}          # TypeError: unhashable type: 'mod.Point'
[x for x in xs if x == a]   # the workaround: a list and ==
```

Hashing the member values instead would be worse: every non-`const` member is
assignable from Python, and a hash that changes when the object is mutated
corrupts any `set` or `dict` already holding it. The safe opt-in — every
member `const` or `[[=readonly{}]]` — describes almost no real class.

## Limitations

### Shapes at the edge

Every row below was measured against a built module, not reasoned about. The
ones that are refused are refused by name at build time, so a signature that
cannot cross is something you hear about from `generate` rather than from an
`AttributeError` later.

| Shape | Status | What to write instead |
|-------|--------|-----------------------|
| A data member whose type has no conversion: a raw pointer, `void*`, a function pointer, a container of raw pointers | Left out, in every backend. The class binds with its other members and all its methods, and `generate` names the member | Nothing. A hand-written `bind_class<T>` refuses such a class unless the member is marked `[[=exclude{}]]`; `bind_class_when_bindable<T>` is what `generate` emits and leaves it out. See [errors](errors.md#unconvertible-member-type-bind_class--mirror_bridge_validate) |
| `T*` as a parameter of a method, `T` a bound class | Python: bound, takes the wrapper's own object. Lua, JavaScript: not bound | Nothing. See [Pointer parameters](#pointer-parameters-python) for `None`, arrays and what it assumes |
| `T*` as a parameter of a constructor or a free function | Not bound | Take `T&`, which aliases the Python object |
| `T*` returned by an instance method, `T` a bound class | Python: bound, a borrow that keeps the owner alive. Lua, JavaScript: not bound | Nothing. See [Pointer returns](#pointer-returns-python) for what it assumes about lifetime |
| `const T*` as a return | Not bound | Return `const T&`, which crosses as a copy, or add a non-`const` overload |
| `T*` returned by a static method or free function | Not bound | There is no owner to keep alive. Return by value or by `unique_ptr`, or make it a method of the owner |
| `const char*` as a parameter or return | Bound, crosses as `str` | Nothing. The caller borrows it and the value is copied into a Python `str` before the call returns. A null crosses as `None`, which is how a C API says "absent" |
| `char*` as a return | Not bound | By convention that one is the caller's to free, so copying it would leak. Return `std::string` |
| `const T&` as a parameter | Bound, no copy | Nothing |
| `T&` as a parameter, `T` a bound class | Bound, aliases the Python object, writes are visible | Nothing |
| `T&` as a parameter, `T` anything else | Not bound | The argument would be a copy and the write would be lost, so this is refused rather than silently doing nothing. Return the value: `double sum(const std::vector<double>&)`, not `void sum(const std::vector<double>&, double&)` |
| `std::span<T>` as a parameter | Not bound | A span does not own its storage. Take `const std::vector<T>&` |
| Overloaded free functions | Not bound | Give one overload a distinct name, or bind a single non-overloaded wrapper |
| Function pointers | Not bound | Take `std::function<R(Args...)>`, which does cross and can be called with any Python callable |
| `weak_ptr` | Not bound | Pass `shared_ptr` |

Every one of these is reported by `mirror_bridge generate`, by name and with
the reason, and carried in `--json` under `declined`. Nothing is dropped in
silence.

### Template Classes

`mirror_bridge generate` plans template instantiations itself: it reads the
parameter list from the headers, tries combinations against the compiler, and
binds the ones that compile. `--instantiate "geom::Vector3<short>"` names one
explicitly and `--no-templates` turns the pass off.

Writing a binding by hand, there is no planner, so the specialization has to
exist before it can be bound:

```cpp
template<typename T>
struct Container {
    T value;
};

// Explicit instantiation
using IntContainer = Container<int>;
using StringContainer = Container<std::string>;

// Now can be bound
MIRROR_BRIDGE_MODULE(my_module,
    mirror_bridge::bind_class<IntContainer>(m, "IntContainer");
    mirror_bridge::bind_class<StringContainer>(m, "StringContainer");
)
```
