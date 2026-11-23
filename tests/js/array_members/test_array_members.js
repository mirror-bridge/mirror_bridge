// Resolution order: NODE_PATH (set by ctest to the CMake build tree), then
// the bash harness output
let m;
try {
    m = require('array_members_js');
} catch (e) {
    m = require('../../../build/array_members_js.node');
}

console.log("=== C array members, JavaScript ===");
const assert = require('assert');

const label = new m.Label();
assert.strictEqual(label.name, "abc", "a char buffer should read as its string");
label.name = "hello";
assert.strictEqual(label.name, "hello");
assert.strictEqual(label.length(), 5, "and C++ should see what was written");
console.log("  ok  a char buffer is a string in both directions");

label.name = "x".repeat(15);
assert.strictEqual(label.length(), 15, "fifteen bytes and a terminator fit char[16]");
assert.throws(() => { label.name = "y".repeat(16); }, /16 bytes.*char\[16\]/,
              "sixteen bytes and a terminator do not fit, and the error gives both sizes");
assert.strictEqual(label.name, "x".repeat(15), "a refused write must leave the buffer alone");
console.log("  ok  a string that does not fit is refused by size, not truncated");

// The limit is the UTF-8 length, which is what the buffer holds.
assert.throws(() => { label.name = "é".repeat(8); }, /16 bytes/);
label.name = "é".repeat(7);
assert.strictEqual(label.name, "é".repeat(7));
assert.strictEqual(label.length(), 14);
console.log("  ok  the limit is in bytes, not in characters");

label.name = "a-longer-value";
label.name = "z";
assert.strictEqual(label.name, "z");
assert.ok(label.tail_is_clear(), "a shorter value leaves no tail behind");
console.log("  ok  the tail is zeroed");

for (const bad of [5, true, null, ["a"]]) {
    assert.throws(() => { label.name = bad; }, TypeError, "char[16] accepted " + String(bad));
}
assert.strictEqual(label.name, "z");
console.log("  ok  only a string is accepted");

assert.strictEqual(new m.Brimful().tag, "abcd",
                   "a buffer with no terminator is read to its end and no further");
console.log("  ok  an unterminated buffer stops at its extent");

const tint = new m.Tint();
assert.deepStrictEqual(tint.rgba, [1, 0, 0, 1], "float[4] should read as an Array of four");
tint.rgba = [0.5, 0.5, 0.5, 0.5];
assert.strictEqual(tint.sum(), 2.0, "and C++ should see an Array written to it");
assert.deepStrictEqual(tint.channels, [255, 128, 0], "unsigned char[3] is three numbers, not text");
console.log("  ok  a numeric array is an Array in both directions");

assert.throws(() => { tint.rgba = [1, 2]; }, TypeError, "float[4] accepted two elements");
assert.throws(() => { tint.rgba = [9, 9, "x", 9]; }, TypeError, "float[4] accepted a string element");
assert.strictEqual(tint.sum(), 2.0, "an Array that fails half way must not be half written");
console.log("  ok  wrong length and wrong element are refused, with nothing written");

const grid = new m.Grid();
assert.deepStrictEqual(grid.cells, [[1, 2, 3], [4, 5, 6]], "int[2][3] is an Array of Arrays");
assert.deepStrictEqual(grid.rows, ["ab", "cd"], "char[2][8] is an Array of strings");
grid.rows = ["x", "seven77"];
assert.deepStrictEqual(grid.rows, ["x", "seven77"]);
assert.strictEqual(grid.second_row_length(), 7);
grid.cells = [[1, 1, 1], [1, 1, 1]];
assert.strictEqual(grid.total(), 6);
assert.throws(() => { grid.rows = ["q", "eight888"]; });
assert.deepStrictEqual(grid.rows, ["x", "seven77"],
                       "a row that does not fit refuses the whole assignment");
console.log("  ok  nested arrays, of numbers and of char buffers");

assert.throws(() => { label.name = "ab\u0000cd"; }, /NUL/,
              "a string with a NUL inside is refused by name");
console.log("  ok  an embedded NUL is refused, not stored and read back short");

const huge = new m.Huge();
huge.samples = new Array(1500000).fill(1.5);
assert.strictEqual(huge.last(), 1.5, "a member too large for the stack is assigned");
assert.throws(() => { huge.samples = [1, 2]; }, TypeError);
assert.strictEqual(huge.last(), 1.5);
console.log("  ok  twelve megabytes written without overflowing the stack");

const names = new m.Names();
assert.deepStrictEqual(names.names, ["first", "second"]);
assert.throws(() => { names.names = ["a", "b"]; },
              "an array of const char* must not keep pointers into JavaScript strings");
assert.deepStrictEqual(names.names, ["first", "second"]);
console.log("  ok  an array of const char* reads and refuses assignment");

console.log("PASS: C array members (JavaScript)");
