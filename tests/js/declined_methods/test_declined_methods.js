// Resolution order: NODE_PATH (set by ctest to the CMake build tree), then
// the bash harness output
let m, modulePath;
try {
    modulePath = require.resolve('declined_methods_js');
} catch (e) {
    modulePath = require.resolve('../../../build/declined_methods_js.node');
}
m = require(modulePath);

console.log("=== a method that cannot be called costs itself, JavaScript ===");
const assert = require('assert');
const { spawnSync } = require('child_process');

// The module loading at all is the first assertion: any one of the methods
// below used to be a compile error for both classes.
const shelf = new m.Shelf();
const item = new m.Item();
item.value = 5;
shelf.put(item);
assert.strictEqual(shelf.size(), 1);
assert.strictEqual(shelf.first().value, 5);
assert.strictEqual(shelf.label(), "shelf");
assert.strictEqual(m.Shelf.capacity(), 8);
assert.strictEqual(shelf.scratch(), "mut", "a char* return is a string here, as it always was");
assert.deepStrictEqual(shelf.words(), ["one", "two"]);
console.log("  ok  the methods that can be called are bound");

for (const name of ["find", "peek", "adopt", "release", "fill", "each", "all", "weigh"]) {
    assert.strictEqual(shelf[name], undefined, name + " cannot be called from JavaScript and was offered");
}
assert.strictEqual(m.Shelf.shared, undefined, "a static method returning a pointer was offered");
console.log("  ok  eight methods and one static method are absent");

assert.strictEqual(shelf.take(3), 4,
                   "the callable overload should not be replaced by the one declared after it");
assert.strictEqual(shelf.pick(3), 3);
console.log("  ok  an overload that cannot be called does not hide one that can");

// Named when asked, in the line shape the Python backend prints.
const load = "require(" + JSON.stringify(modulePath) + ")";
const loud = spawnSync(process.execPath, ["-e", load],
                       { env: { ...process.env, MIRROR_BRIDGE_REPORT_DECLINED: "1" }, encoding: "utf8" });
for (const name of ["find", "peek", "adopt", "release", "fill", "each", "all", "weigh",
                    "shared"]) {
    assert.ok(loud.stderr.includes("skipped method 'Shelf::" + name + "'"),
              name + " was left out and not named:\n" + loud.stderr);
}
assert.ok(loud.stderr.includes("the return type has no conversion to JavaScript"));
assert.ok(loud.stderr.includes("a parameter has no conversion from JavaScript"));
assert.ok(!loud.stderr.includes("Shelf::size"), "a bound method was reported as left out");
// One overload of each is bound, so the name is in the class and works.
assert.ok(!loud.stderr.includes("Shelf::pick") && !loud.stderr.includes("Shelf::take"),
          "a name with a bound overload was reported as left out:\n" + loud.stderr);

const env = { ...process.env };
delete env.MIRROR_BRIDGE_REPORT_DECLINED;
const quiet = spawnSync(process.execPath, ["-e", load], { env, encoding: "utf8" });
assert.ok(!quiet.stderr.includes("skipped"), "a plain load printed the list:\n" + quiet.stderr);
console.log("  ok  quiet by default, and each one is named with its reason when asked");

console.log("PASS: declined methods (JavaScript)");
