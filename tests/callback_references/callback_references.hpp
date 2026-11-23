#pragma once
#include <functional>
#include <stdexcept>
#include <string>
#include <utility>

// A C++ library calling back into Python with a reference it expects to be
// written through. cpp-httplib's handler type is the real case:
//
//   std::function<void(const Request&, Response&)>
//
// The Response used to reach Python as a copy, so a handler written in
// Python answered into an object that was thrown away.
namespace cbref {

struct Request {
    std::string path;
};

struct Response {
    int status = 200;
    std::string body;

    void set_content(std::string content) { body = std::move(content); }
};

struct Counter {
    int n = 0;
    void bump() { ++n; }
};

struct Server {
    using Handler = std::function<void(const Request&, Response&)>;
    Handler handler;
    int served = 0;

    void on(Handler h) { handler = std::move(h); }

    // Request and Response live on this frame, as they do in a real server:
    // nothing of them exists once serve() returns.
    std::string serve(const std::string& path) {
        Request request{path};
        Response response;
        if (handler) handler(request, response);
        ++served;
        return std::to_string(response.status) + " " + response.body;
    }

    // The same object lent twice in one call.
    int tally(const std::function<void(Counter&)>& visit) {
        Counter counter;
        visit(counter);
        visit(counter);
        return counter.n;
    }

    int status_of(const Response& response) const { return response.status; }
    int status_at(const Response* response) const { return response ? response->status : -1; }

    // An arithmetic reference is not an object anyone holds a wrapper of,
    // and stays a value.
    int scaled(const std::function<void(int&)>& adjust) {
        int value = 5;
        adjust(value);
        return value;
    }
};

}  // namespace cbref
