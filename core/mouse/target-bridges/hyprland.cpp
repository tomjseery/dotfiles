// SPDX-License-Identifier: GPL-2.0-or-later
#include <hyprland/src/plugins/PluginAPI.hpp>

#include <hyprland/src/desktop/view/View.hpp>
#include <hyprland/src/desktop/view/WLSurface.hpp>
#include <hyprland/src/desktop/view/window/Window.hpp>
#include <hyprland/src/desktop/view/window/WindowMetadata.hpp>
#include <hyprland/src/layout/LayoutManager.hpp>
#include <hyprland/src/managers/SeatManager.hpp>
#include <hyprland/src/managers/SessionLockManager.hpp>
#include <hyprland/src/managers/input/InputManager.hpp>
#include <hyprland/src/pointer/PointerManager.hpp>
#include <hyprland/src/protocols/core/Compositor.hpp>
#include <hyprland/src/protocols/core/DataDevice.hpp>

#include <nlohmann/json.hpp>

#include <cstdint>
#include <cstdio>
#include <format>
#include <limits>
#include <memory>
#include <random>
#include <stdexcept>
#include <string>

namespace dotfiles::mouse {
namespace {

std::string unique_token() {
    std::random_device random{};
    return std::format("{:x}-{:x}-{:x}-{:x}", random(), random(), random(), random());
}

class TargetBridge final {
public:
    explicit TargetBridge(HANDLE handle) : handle_{handle}, session_{unique_token()} {
        command_ = HyprlandAPI::registerHyprCtlCommand(handle_, {
            .name = "mouse-target",
            .match = IPC::Socket1::COMMAND_MATCH_EXACT,
            .handler = [this](const IPC::Socket1::SRequest&) -> IPC::Socket1::SResponse {
                try {
                    return snapshot();
                } catch (const nlohmann::json::type_error& error) {
                    // Client metadata must not let invalid UTF-8 escape through
                    // the compositor's IPC callback as a C++ exception.
                    std::fprintf(stderr, "Mouse Target: invalid target metadata: %s\n", error.what());
                    last_surface_.reset();
                    surface_token_.clear();
                    return "null";
                }
            },
        });
        if (!command_)
            throw std::runtime_error{"Could not register mouse-target query"};
    }

    ~TargetBridge() {
        if (command_)
            HyprlandAPI::unregisterHyprCtlCommand(handle_, command_);
    }

private:
    std::string snapshot() {
        const auto unknown{[this] {
            last_surface_.reset();
            surface_token_.clear();
            return std::string{"null"};
        }};
        if (!g_pSeatManager || !g_pInputManager || !g_pSessionLockManager
            || g_pSessionLockManager->isSessionLocked() || g_pSeatManager->m_seatGrab
            || g_pInputManager->isConstrained() || g_pInputManager->hasHeldButtons()
            || g_pInputManager->getClickMode() != CLICKMODE_DEFAULT
            || (PROTO::data && PROTO::data->dndActive())
            || !g_layoutManager || g_layoutManager->dragController()->mode() != MBIND_INVALID)
            return unknown();

        const auto surface{g_pSeatManager->m_state.pointerFocus.lock()};
        if (!surface || !surface->m_mapped || !g_pSeatManager->m_state.pointerFocusResource.lock())
            return unknown();
        const auto wrapper{Desktop::View::CWLSurface::fromResource(surface)};
        const auto view{wrapper ? wrapper->view() : nullptr};
        // Only a root window surface may grant fallback. A popup/subsurface or
        // layer is not silently mapped to the application behind it.
        if (!view || view->type() != Desktop::View::VIEW_TYPE_WINDOW
            || !view->mapped() || !view->acceptsInput())
            return unknown();
        const auto window{dynamicPointerCast<Desktop::View::CWindow>(view)};
        if (!window || window->resource() != surface || window->metadata().appID().empty())
            return unknown();
        const auto content_box{window->surfaceLogicalBox()};
        // This only rejects non-content areas of the already-focused surface;
        // it never selects a window or grants fallback from a rectangle.
        if (!content_box || !content_box->containsPoint(Pointer::mgr()->untransformedPosition()))
            return unknown();

        if (last_surface_.lock() != surface) {
            if (surface_sequence_ == std::numeric_limits<std::uint64_t>::max())
                return unknown();
            last_surface_ = surface;
            surface_token_ = std::format("{}/{}", window->metadata().stableID(), ++surface_sequence_);
        }
        return nlohmann::json{{"session", session_}, {"surface", surface_token_},
                              {"app", window->metadata().appID()}}.dump();
    }

    HANDLE handle_;
    std::string session_;
    WP<CWLSurfaceResource> last_surface_;
    std::string surface_token_;
    std::uint64_t surface_sequence_{0};
    SP<IPC::Socket1::SCommand> command_;
};

std::unique_ptr<TargetBridge> bridge;

} // namespace
} // namespace dotfiles::mouse

APICALL EXPORT std::string PLUGIN_API_VERSION() { return HYPRLAND_API_VERSION; }

APICALL EXPORT PLUGIN_DESCRIPTION_INFO PLUGIN_INIT(HANDLE handle) {
    // The compositor passes C++ objects across this boundary. Never load a
    // plugin compiled against another compositor/dependency ABI fingerprint.
    if (std::string{__hyprland_api_get_hash()} != __hyprland_api_get_client_hash())
        throw std::runtime_error{"Mouse Target: Hyprland ABI fingerprint mismatch"};
    dotfiles::mouse::bridge = std::make_unique<dotfiles::mouse::TargetBridge>(handle);
    return {"mouse-target", "Read-only pointer-focus snapshot", "dotfiles", "0.1.0"};
}

APICALL EXPORT void PLUGIN_EXIT() { dotfiles::mouse::bridge.reset(); }
