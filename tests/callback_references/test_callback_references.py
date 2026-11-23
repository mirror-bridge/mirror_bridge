#!/usr/bin/env python3
"""A reference argument to a Python callback is the caller's object, lent for the call.

`std::function<void(const Request&, Response&)>` is how a C++ library asks to
be called back, and the Response& is where the answer goes. It used to reach
Python as a copy, so the handler's answer was thrown away.
"""

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'build'))

import callback_references as m

print("Test 1: a write through a T& argument reaches the C++ caller...")
server = m.Server()


def hello(request, response):
    response.status = 201
    response.set_content("hello " + request.path)


server.on(hello)
assert server.serve("/hi") == "201 hello /hi", server.serve("/hi")
assert server.serve("/again") == "201 hello /again"
print("  ✓ both an attribute write and a method call landed in the caller's Response")

print("Test 2: the argument is a real instance of the bound class...")
seen = []
server.on(lambda request, response: seen.append((type(request), type(response))))
server.serve("/")
assert seen == [(m.Request, m.Response)], seen
print("  ✓ Request and Response, not dicts")

print("Test 3: a kept T& argument is taken back when the callback returns...")
kept = []
server.on(lambda request, response: kept.append((request, response)))
server.serve("/kept")
request, response = kept[0]
for use in (lambda: response.status,
            lambda: setattr(response, "status", 500),
            lambda: response.set_content("late")):
    try:
        use()
    except RuntimeError as e:
        assert "callback" in str(e), str(e)
    else:
        raise AssertionError("a Response from a finished call was still usable")
print("  ✓ reading, writing and calling each raise RuntimeError naming the callback")

print("Test 4: a const T& argument is a copy, and may be kept...")
assert request.path == "/kept", request.path
request.path = "changed"
assert request.path == "changed"
print("  ✓ the kept Request is the handler's own")

print("Test 5: the same object lent twice in one call...")
assert server.tally(lambda counter: counter.bump()) == 2
print("  ✓ two bumps on one Counter")

print("Test 6: an exception in the handler still takes the argument back...")
held = []


def failing(request, response):
    held.append(response)
    raise ValueError("handler failed")


server.on(failing)
try:
    server.serve("/boom")
except Exception as e:
    assert "handler failed" in str(e), str(e)
else:
    raise AssertionError("the handler's exception was lost")
try:
    held[0].status
except RuntimeError as e:
    assert "callback" in str(e), str(e)
else:
    raise AssertionError("a Response from a failed call was still usable")
print("  ✓ the exception crossed, and the kept Response is revoked")

print("Test 7: an arithmetic reference stays a value...")
received = []
assert server.scaled(lambda value: received.append(value)) == 5
assert received == [5]
print("  ✓ int& arrives as 5 and the caller's int is untouched")

print("Test 8: a revoked wrapper is not confused with a failed constructor...")
try:
    held[0].body
except RuntimeError as e:
    assert "constructor" not in str(e), str(e)
print("  ✓ the message is about the callback")

print("Test 9: and cannot be handed back to C++ or copied...")
import copy
import pickle

stale = held[0]
for name, use in (("by reference", lambda: server.status_of(stale)),
                  ("by pointer", lambda: server.status_at(stale)),
                  ("copy", lambda: copy.copy(stale)),
                  ("pickle", lambda: pickle.dumps(stale))):
    try:
        use()
    except (TypeError, RuntimeError):
        pass
    else:
        raise AssertionError("a revoked Response was accepted: " + name)
assert "invalid" in repr(stale), repr(stale)
assert server.status_of(m.Response()) == 200
print("  ✓ refused as an argument, by copy and by pickle; repr says it is invalid")

print("\nAll callback-reference tests passed!")
