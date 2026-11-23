#include "python/mirror_bridge_python.hpp"
#include "borrowed_returns.hpp"

class Trampoline_Listener : public borrowed::Listener,
                            public mirror_bridge::TrampolineBase<borrowed::Listener> {
public:
    int on_event(int x) override {
        if (mirror_bridge::has_python_override(this->py_self_, "on_event")) {
            return this->dispatch_python<int>("on_event", x);
        }
        return borrowed::Listener::on_event(x);
    }
};

MIRROR_BRIDGE_MODULE(borrowed_returns,
    mirror_bridge::bind_class<borrowed::Tally>(m, "Tally");
    mirror_bridge::bind_class<borrowed::Node>(m, "Node");
    mirror_bridge::bind_class<borrowed::Tree>(m, "Tree");
    mirror_bridge::bind_class<borrowed::Item>(m, "Item");
    mirror_bridge::bind_class<borrowed::Crate>(m, "Crate");
    mirror_bridge::bind_class<borrowed::Counted>(m, "Counted");
    mirror_bridge::bind_class<borrowed::Sealed>(m, "Sealed");
    mirror_bridge::bind_class<borrowed::Registry>(m, "Registry");
    mirror_bridge::bind_class<borrowed::Listener, Trampoline_Listener>(m, "Listener");
    mirror_bridge::bind_class<borrowed::Ref<borrowed::Pinned>>(m, "PinnedRef");
    mirror_bridge::bind_class<borrowed::Vault>(m, "Vault");
    mirror_bridge::bind_class<borrowed::Opener>(m, "Opener");
    mirror_bridge::bind_class_when_bindable<borrowed::PointerBag>(m, "PointerBag");
    mirror_bridge::bind_function_when_bindable<&borrowed::make_pinned>(m, "make_pinned");
    mirror_bridge::bind_function_when_bindable<&borrowed::use_pinned>(m, "use_pinned");
    mirror_bridge::bind_function_when_bindable<&borrowed::global_item>(m, "global_item");
    mirror_bridge::bind_function_when_bindable<&borrowed::global_default>(m, "global_default");
)
