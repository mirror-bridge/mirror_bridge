#pragma once
#include <cstddef>
#include <map>
#include <string>
#include <unordered_map>

// std::multimap and std::unordered_multimap, as a member, a return and a
// parameter. A class with either as a member failed its whole module to
// compile in every backend: the generic container conversion builds each
// element as the container's value_type, which for these is pair<const K, V>,
// and nothing can be converted into a const key. cpp-httplib's Headers is an
// unordered_multimap, held by both Request and Response.
// tests/lua/multimap and tests/js/multimap hold copies of this header.
namespace mm {

struct Request {
    std::multimap<std::string, std::string> params = {{"a", "1"}, {"a", "2"}, {"b", "3"}};
    std::unordered_multimap<std::string, int> counts;
    int id = 1;

    std::size_t param_count() const { return params.size(); }
    std::size_t count_of(const std::string& key) const { return counts.count(key); }
    std::multimap<std::string, std::string> all() const { return params; }
    void replace(const std::multimap<std::string, std::string>& p) { params = p; }
};

}  // namespace mm
