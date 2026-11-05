// Compile check: the platform must build C++14 (library aliases, variable
// templates, relaxed constexpr) and link a class with a virtual destructor.
#include <type_traits>

template <typename T>
constexpr bool is_small_v = sizeof(T) <= 4;

template <typename T, std::enable_if_t<is_small_v<T>, int> = 0>
constexpr int widen(T v)
{
    int r = 0;
    for (int i = 0; i < 2; i++)
        r += static_cast<int>(v);
    return r;
}

struct Base {
    virtual ~Base() {}
    virtual int value() const { return widen<short>(21); }
};

static_assert(widen<char>(1) == 2, "relaxed constexpr");

Base *probe = nullptr;

void setup()
{
    Serial.begin(115200);
    probe = new Base();
    Serial.println(probe->value());
    delete probe;
}

void loop() {}
