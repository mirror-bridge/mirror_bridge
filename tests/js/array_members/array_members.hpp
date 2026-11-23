#pragma once
#include <cstddef>
#include <cstring>

// C array data members. Every backend's member gate says yes to one whose
// element converts, so every backend has to carry it: a `float rgba[4]`
// failed the Lua and JavaScript modules to compile, and a `char name[16]`
// failed all three. tests/lua/array_members and tests/js/array_members hold
// copies of this header, as the other per-language fixtures do.
namespace arr {

// Dear ImGui's ImGuiTextFilter::InputBuf is the real case.
struct Label {
    char name[16] = "abc";
    int id = 7;

    std::size_t length() const { return std::strlen(name); }

    // Whether every byte after the terminator is zero, which is what makes a
    // shorter value overwrite a longer one cleanly.
    bool tail_is_clear() const {
        for (std::size_t i = std::strlen(name); i < sizeof name; ++i) {
            if (name[i] != '\0') return false;
        }
        return true;
    }

    void corrupt() { name[0] = static_cast<char>(0xff); name[1] = 'k'; name[2] = '\0'; }
};

// No terminator anywhere in `tag`: legal C, and a read must stop at the end
// of the array instead of running on into `after`.
struct Brimful {
    char tag[4] = {'a', 'b', 'c', 'd'};
    char after[4] = {'X', 'Y', 'Z', '\0'};
};

// `channels` is the other half of the char rule: only plain `char` is text.
struct Tint {
    float rgba[4] = {1.0f, 0.0f, 0.0f, 1.0f};
    unsigned char channels[3] = {255, 128, 0};
    float sum() const { return rgba[0] + rgba[1] + rgba[2] + rgba[3]; }
};

struct Grid {
    int cells[2][3] = {{1, 2, 3}, {4, 5, 6}};
    char rows[2][8] = {"ab", "cd"};

    int total() const {
        int t = 0;
        for (auto& row : cells) for (int c : row) t += c;
        return t;
    }
    std::size_t second_row_length() const { return std::strlen(rows[1]); }
};

// Static members: Dear ImGui's `static char EmptyString[1]` is the real case.
// `shared` has no conversion and must cost only itself.
struct Constants {
    static constexpr char kName[8] = "mirror";
    static constexpr float kIdentity[4] = {1.0f, 0.0f, 0.0f, 1.0f};
    static constexpr int kAnswer = 42;
    static inline int* shared = nullptr;
    int value = 1;
};

}  // namespace arr
