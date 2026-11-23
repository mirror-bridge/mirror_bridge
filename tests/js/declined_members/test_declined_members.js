// Resolution order: NODE_PATH (set by ctest to the CMake build tree), then
// the bash harness output
let m;
try {
    m = require('declined_members_js');
} catch (e) {
    m = require('../../../build/declined_members_js.node');
}

console.log("=== a member with no conversion costs itself, JavaScript ===");
const assert = require('assert');

const f = new m.FixtureDef();
assert.strictEqual(f.friction, 0.25);
assert.strictEqual(f.density, 1);
assert.strictEqual(f.is_sensor, false);
f.density = 3.0;
assert.strictEqual(f.mass(), 6.0, "a written field is seen by a method");
assert.ok(!("shape" in f) && !("user_data" in f), "the pointer members are not properties");
console.log("  ok  a class with a pointer member binds without that member");

const io = new m.IO();
assert.strictEqual(io.delta_time, 0.5);
assert.strictEqual(io.next_frame(), 1);
assert.strictEqual(io.frame, 1);
assert.ok(!("set_clipboard" in io) && !("handler" in io));
console.log("  ok  a function pointer and a pointer to member are left out the same way");

const d = new m.Derived();
assert.strictEqual(d.own, 6);
assert.strictEqual(d.total(), 11);
assert.ok(!("raw" in d));
assert.strictEqual(new m.Base().kept, 5);
assert.ok(!("raw" in new m.Base()));
console.log("  ok  an inherited member with no conversion costs neither class");

assert.strictEqual(new m.Handles().count(), 2);
console.log("  ok  a class left with no properties still binds for what it does");

const w = new m.World();
w.attach();
const c = w.copy();
assert.ok(c.has_shape(), "a copy must keep the member JavaScript does not carry");
c.density = 4.0;
w.apply(c);
assert.strictEqual(w.copy().density, 4.0);
assert.ok(w.copy().has_shape());
assert.strictEqual(w.def.density, 4.0, "and the class still reads as a member");
console.log("  ok  such a class works as a member, a value and an argument");

console.log("PASS: declined members (JavaScript)");
