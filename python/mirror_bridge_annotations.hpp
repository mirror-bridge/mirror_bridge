#pragma once

// ═══════════════════════════════════════════════════════════════════════════
// Mirror Bridge Annotations - P3394 Field Annotations for Binding Control
// ═══════════════════════════════════════════════════════════════════════════
//
// This header provides annotation types for controlling binding behavior using
// C++26 P3394 (Annotations for Reflection), accepted at the Sofia meeting.
//
// Usage (recommended - import annotation types for clean syntax):
//
//   using mirror_bridge::exclude;
//   using mirror_bridge::readonly;
//
//   struct UserProfile {
//       int user_id;                              // Bound normally
//       [[=exclude{}]] std::string password_hash; // Not bound to Python
//       [[=readonly{}]] std::string created_at;   // Read-only in Python
//   };
//
// Both supported toolchains implement P3394: Bloomberg's clang-p2996 with
// -freflection-latest, and stock GCC 16+ with -freflection.
//
// ═══════════════════════════════════════════════════════════════════════════

#include <meta>
#include <vector>
#include <type_traits>

#include "core/mirror_bridge_core.hpp"

namespace mirror_bridge {

// ============================================================================
// Annotation Types
// ============================================================================

// Exclude a field from the binding entirely
// The field will not appear in the Python/Lua/JavaScript binding
struct exclude {
    constexpr bool operator==(const exclude&) const = default;
};

// Make a field read-only in the binding
// The field will have a getter but no setter
struct readonly {
    constexpr bool operator==(const readonly&) const = default;
};

// ============================================================================
// Annotation Detection Helpers
// ============================================================================

namespace annotations {

// Is this member annotated with one of these?
//
// Written against std::meta::annotations_of, which is the only part of P3394
// that both standard libraries spell the same way. The convenience overloads
// are not portable: libc++ has annotation_of_type<T>(info) -> optional<T> and
// no annotations_of_with_type, libstdc++ has annotations_of_with_type(info,
// info) and no annotation_of_type. Neither name can be probed with a requires
// expression either, because std::meta:: is not a dependent scope, so a
// qualified name that does not exist is a parse error rather than a
// substitution failure. Going through annotations_of avoids the question.
//
// remove_const is load-bearing. type_of on an annotation is `const T` in
// libstdc++ and `T` in libc++, so without it the comparison silently answers
// false on GCC and this function would report no annotations at all.
//
// Comparing types also avoids a divergence in the convenience overloads worth
// not inheriting: given two annotations of the same type with different values
// on one member, libc++'s annotation_of_type extracts every match and throws
// "inconsistent annotations", which is a hard compile error, while libstdc++'s
// annotations_of_with_type returns both. This returns true on either, since it
// never extracts anything.
//
// The range annotations_of returns owns a heap allocation in libstdc++, so it
// is consumed inside this evaluation. Returning it, or binding it to a
// constexpr variable, makes the result "a result of operator new" and it stops
// being a constant expression.
template<typename Annotation>
consteval bool has_annotation(std::meta::info member) {
    for (std::meta::info a : std::meta::annotations_of(member)) {
        if (std::meta::remove_const(std::meta::type_of(a)) == ^^Annotation) {
            return true;
        }
    }
    return false;
}

// An anonymous union is a nonstatic data member with no name. identifier_of
// has a precondition rather than a fallback, so letting one through made
// get_visible_member_name ill-formed and the enclosing consteval call stopped
// being a constant expression -- the module failed to compile over
// ImGuiStoragePair's `union { int val_i; float val_f; void* val_p; }`.
// Everything below filters through here so the index space, the count and the
// names cannot disagree.
template<typename T>
consteval std::vector<std::meta::info> named_members_of() {
    std::vector<std::meta::info> out;
    for (auto m : std::meta::nonstatic_data_members_of(^^T, std::meta::access_context::current())) {
        if (std::meta::has_identifier(m)) out.push_back(m);
    }
    return out;
}

// Check if a member has the 'exclude' annotation
template<std::meta::info Member>
consteval bool is_excluded() {
    return has_annotation<exclude>(Member);
}

// Check if a member has the 'readonly' annotation
template<std::meta::info Member>
consteval bool is_readonly() {
    return has_annotation<readonly>(Member);
}

// The members Python sees: named, not marked [[=exclude{}]], and of a type
// with a conversion. The last is the same test core::CarriedDataMembers
// applies, so a member with no conversion is left out here exactly as if it
// had been annotated, which is what the annotation was always documented to
// be the remedy for.
//
// Built once per class. Every getter, setter, repr and pickle site asks for
// a member by index, and each of those used to walk the whole class again.
template<typename T>
struct VisibleMembers {
    static consteval std::vector<std::meta::info> collect() {
        std::vector<std::meta::info> out;
        for (auto member : named_members_of<T>()) {
            if (has_annotation<exclude>(member)) continue;
            if (!core::data_member_converts(member)) continue;
            out.push_back(member);
        }
        return out;
    }
    static constexpr auto members = std::define_static_array(collect());
};

template<typename T>
consteval std::size_t count_visible_members() {
    return VisibleMembers<T>::members.size();
}

template<typename T>
consteval std::meta::info get_visible_member(std::size_t visible_index) {
    return VisibleMembers<T>::members[visible_index];
}

// The members left out for want of a conversion that nobody asked to have
// left out. These are the ones worth telling the caller about, and the ones
// a hand-written bind_class refuses to drop in silence.
template<typename T>
struct UnexpectedlyDeclinedMembers {
    static consteval std::vector<std::meta::info> collect() {
        std::vector<std::meta::info> out;
        for (auto member : core::DeclinedDataMembers<T>::members) {
            if (!has_annotation<exclude>(member)) out.push_back(member);
        }
        return out;
    }
    static constexpr auto members = std::define_static_array(collect());
};

template<typename T>
consteval std::size_t count_declined_members() {
    return UnexpectedlyDeclinedMembers<T>::members.size();
}

template<typename T, std::size_t Index>
consteval const char* get_declined_member_name() {
    return std::meta::identifier_of(UnexpectedlyDeclinedMembers<T>::members[Index]).data();
}

// Check if the Nth visible member is readonly
template<typename T, std::size_t VisibleIndex>
consteval bool is_visible_member_readonly() {
    constexpr auto member = get_visible_member<T>(VisibleIndex);
    return has_annotation<readonly>(member);
}

// Get the name of the Nth visible member
template<typename T, std::size_t VisibleIndex>
consteval const char* get_visible_member_name() {
    constexpr auto member = get_visible_member<T>(VisibleIndex);
    return std::meta::identifier_of(member).data();
}

} // namespace annotations
} // namespace mirror_bridge
