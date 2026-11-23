// Resolution order: NODE_PATH (set by ctest to the CMake build tree), then
// the bash harness output
let m;
try {
    m = require('multimap_js');
} catch (e) {
    m = require('../../../build/multimap_js.node');
}

console.log("=== multimap members, JavaScript ===");
const assert = require('assert');

const r = new m.Request();
assert.deepStrictEqual(r.params, [["a", "1"], ["a", "2"], ["b", "3"]],
                       "a multimap reads as an Array of [key, value] pairs with repeats kept");
console.log("  ok  reads as an Array of pairs");

r.params = [["x", "1"], ["x", "2"]];
assert.deepStrictEqual(r.params, [["x", "1"], ["x", "2"]]);
assert.strictEqual(r.param_count(), 2);
r.counts = [["hit", 1], ["hit", 2], ["miss", 0]];
assert.strictEqual(r.count_of("hit"), 2);
assert.strictEqual(r.count_of("miss"), 1);
r.params = [];
assert.strictEqual(r.param_count(), 0);
console.log("  ok  written from an Array of pairs, both kinds, with a repeated key");

r.params = [["keep", "me"]];
for (const bad of [[["x"]], [["x", 1]], [["a", "b"], ["c"]], "text", 5, {k: "v"}]) {
    assert.throws(() => { r.params = bad; }, TypeError, "accepted " + JSON.stringify(bad));
}
assert.deepStrictEqual(r.params, [["keep", "me"]], "a refused assignment changed the member");
console.log("  ok  a malformed value is refused whole");

r.replace([["p", "q"], ["p", "r"]]);
assert.deepStrictEqual(r.all(), [["p", "q"], ["p", "r"]]);
console.log("  ok  as a parameter and as a return");

console.log("PASS: multimap members (JavaScript)");
