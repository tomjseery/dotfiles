// SPDX-License-Identifier: GPL-2.0-or-later
#include <hyprland/src/plugins/PluginAPI.hpp>

#include <hyprland/src/desktop/view/View.hpp>
#include <hyprland/src/desktop/view/WLSurface.hpp>
#include <hyprland/src/desktop/view/window/Window.hpp>
#include <hyprland/src/desktop/view/window/WindowMetadata.hpp>
#include <hyprland/src/layout/LayoutManager.hpp>
#include <hyprland/src/ipc/s2/S2.hpp>
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
#include <string_view>
#include <vector>

namespace dotfiles::mouse {
namespace {

std::string unique_token() {
    std::random_device random{};
    return std::format("{:x}-{:x}-{:x}-{:x}", random(), random(), random(), random());
}

class TargetBridge final {
public:
    explicit TargetBridge(HANDLE handle) : handle_{handle}, session_{unique_token()} {
        // Own the observation subscriptions before exposing the query. Missing
        // subscriptions must never permit a snapshot-based permission lease.
        if (g_pSeatManager && g_pSessionLockManager) {
            listeners_.push_back(g_pSeatManager->m_events.pointerFocusChange.listen(
                [this] { invalidate(); }));
            listeners_.push_back(g_pSeatManager->m_events.dndPointerFocusChange.listen(
                [this] { invalidate(); }));
            listeners_.push_back(g_pSessionLockManager->m_events.lock.listen(
                [this] { invalidate(); }));
            listeners_.push_back(g_pSessionLockManager->m_events.unlock.listen(
                [this] { invalidate(); }));
            listeners_.push_back(Event::bus()->m_events.window.class_.listen(
                [this] { invalidate(); }));
        }
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
        try {
            observe_command_ = HyprlandAPI::registerHyprCtlCommand(handle_, {
                .name = "mouse-target-observe ",
                .match = IPC::Socket1::COMMAND_MATCH_PREFIX,
                .handler = [](const IPC::Socket1::SRequest& request) -> IPC::Socket1::SResponse {
                    constexpr std::string_view prefix{"mouse-target-observe "};
                    constexpr std::size_t token_length{32};
                    std::string_view token{request.command};
                    if (!token.starts_with(prefix))
                        return "invalid observation token";
                    token.remove_prefix(prefix.size());
                    if (token.size() != token_length)
                        return "invalid observation token";
                    for (const char value : token) {
                        if (!((value >= '0' && value <= '9') || (value >= 'a' && value <= 'f')
                              || (value >= 'A' && value <= 'F')))
                            return "invalid observation token";
                    }
                    IPC::Socket2::sock()->postEvent(IPC::Socket2::SEvent{
                        .event = "mouse-target-ready", .data = std::string{token},
                    });
                    return "ok";
                },
            });
            if (!observe_command_)
                throw std::runtime_error{"Could not register mouse-target observation barrier"};
        } catch (...) {
            // A failed second registration must not leave a compositor callback
            // referring to an object whose constructor did not finish.
            HyprlandAPI::unregisterHyprCtlCommand(handle_, command_);
            command_.reset();
            throw;
        }
    }

    ~TargetBridge() {
        listeners_.clear();
        invalidate();
        if (observe_command_)
            HyprlandAPI::unregisterHyprCtlCommand(handle_, observe_command_);
        if (command_)
            HyprlandAPI::unregisterHyprCtlCommand(handle_, command_);
    }

private:
    void invalidate() {
        if (focus_generation_ == std::numeric_limits<std::uint64_t>::max())
            generation_exhausted_ = true;
        else
            ++focus_generation_;
        last_surface_.reset();
        surface_token_.clear();
        IPC::Socket2::sock()->postEvent(IPC::Socket2::SEvent{
            .event = "mouse-target-changed",
            .data = nlohmann::json{{"session", session_}, {"generation", focus_generation_}}.dump(),
        });
    }

    std::string snapshot() {
        const auto unknown{[this] {
            last_surface_.reset();
            surface_token_.clear();
            return std::string{"null"};
        }};
        if (generation_exhausted_ || listeners_.empty()
            || !g_pSeatManager || !g_pInputManager || !g_pSessionLockManager
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
            surface_token_ = std::format("{}/{}/{}", window->metadata().stableID(),
                                         focus_generation_, ++surface_sequence_);
        }
        return nlohmann::json{{"session", session_}, {"surface", surface_token_},
                              {"app", window->metadata().appID()}}.dump();
    }

    HANDLE handle_;
    std::string session_;
    WP<CWLSurfaceResource> last_surface_;
    std::string surface_token_;
    std::uint64_t surface_sequence_{0};
    std::uint64_t focus_generation_{0};
    bool generation_exhausted_{false};
    std::vector<CHyprSignalListener> listeners_;
    SP<IPC::Socket1::SCommand> command_;
    SP<IPC::Socket1::SCommand> observe_command_;
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
