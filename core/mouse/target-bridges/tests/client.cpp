// SPDX-License-Identifier: MIT
// A disposable protocol client. It refuses host input and inherited display selection.
#include "fake-input-client.h"
#include "virtual-pointer-client.h"
#include "xdg-shell-client.h"

#include <wayland-client.h>

#include <sys/mman.h>
#include <unistd.h>

#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

namespace mouse_probe {
namespace {

constexpr int output_width{800};
constexpr int output_height{600};
constexpr auto app_id{"mmb-native-probe"};

enum class Backend { kwin, hyprland };

struct Window {
    wl_surface* surface{};
    xdg_surface* shell{};
    xdg_toplevel* top{};
    wl_buffer* buffer{};
    std::string title;
    int width{300};
    int height{200};
};

struct Client {
    Backend backend;
    wl_display* display{};
    wl_compositor* compositor{};
    wl_shm* shm{};
    xdg_wm_base* shell{};
    org_kde_kwin_fake_input* fake{};
    zwlr_virtual_pointer_manager_v1* manager{};
    zwlr_virtual_pointer_v1* virtual_pointer{};
    wl_seat* seat{};
    wl_pointer* pointer{};
    std::vector<Window> windows{};
};

void pointer_enter(void*, wl_pointer*, std::uint32_t, wl_surface*, wl_fixed_t, wl_fixed_t) {}
void pointer_leave(void*, wl_pointer*, std::uint32_t, wl_surface*) {}
void pointer_motion(void*, wl_pointer*, std::uint32_t, wl_fixed_t, wl_fixed_t) {}
void pointer_button(void*, wl_pointer*, std::uint32_t, std::uint32_t, std::uint32_t, std::uint32_t) {}
void pointer_axis(void*, wl_pointer*, std::uint32_t, std::uint32_t, wl_fixed_t) {}
const wl_pointer_listener pointer_listener{
    pointer_enter, pointer_leave, pointer_motion, pointer_button, pointer_axis,
    nullptr, nullptr, nullptr, nullptr, nullptr, nullptr, nullptr};

void capabilities(void* data, wl_seat* seat, std::uint32_t caps) {
    auto& client{*static_cast<Client*>(data)};
    if ((caps & WL_SEAT_CAPABILITY_POINTER) && !client.pointer) {
        client.pointer = wl_seat_get_pointer(seat);
        wl_pointer_add_listener(client.pointer, &pointer_listener, nullptr);
    }
}

void seat_name(void*, wl_seat*, const char*) {}
const wl_seat_listener seat_listener{capabilities, seat_name};
void ping(void*, xdg_wm_base* shell, std::uint32_t serial) { xdg_wm_base_pong(shell, serial); }
const xdg_wm_base_listener shell_listener{ping};

void global(void* data, wl_registry* registry, std::uint32_t name, const char* interface,
            std::uint32_t version) {
    auto& client{*static_cast<Client*>(data)};
    if (!std::strcmp(interface, "wl_compositor"))
        client.compositor = static_cast<wl_compositor*>(wl_registry_bind(registry, name, &wl_compositor_interface, 1));
    else if (!std::strcmp(interface, "wl_shm"))
        client.shm = static_cast<wl_shm*>(wl_registry_bind(registry, name, &wl_shm_interface, 1));
    else if (!std::strcmp(interface, "xdg_wm_base")) {
        client.shell = static_cast<xdg_wm_base*>(wl_registry_bind(registry, name, &xdg_wm_base_interface, 1));
        xdg_wm_base_add_listener(client.shell, &shell_listener, nullptr);
    } else if (client.backend == Backend::kwin && !std::strcmp(interface, "org_kde_kwin_fake_input"))
        client.fake = static_cast<org_kde_kwin_fake_input*>(wl_registry_bind(registry, name, &org_kde_kwin_fake_input_interface, std::min(version, 6u)));
    else if (client.backend == Backend::hyprland && !std::strcmp(interface, "zwlr_virtual_pointer_manager_v1")) {
        client.manager = static_cast<zwlr_virtual_pointer_manager_v1*>(wl_registry_bind(registry, name, &zwlr_virtual_pointer_manager_v1_interface, std::min(version, 2u)));
        client.virtual_pointer = zwlr_virtual_pointer_manager_v1_create_virtual_pointer(client.manager, nullptr);
    } else if (!std::strcmp(interface, "wl_seat")) {
        client.seat = static_cast<wl_seat*>(wl_registry_bind(registry, name, &wl_seat_interface, 1));
        wl_seat_add_listener(client.seat, &seat_listener, &client);
    }
}

void removed(void*, wl_registry*, std::uint32_t) {}
const wl_registry_listener registry_listener{global, removed};

void configured(void* data, xdg_surface* shell, std::uint32_t serial) {
    auto& window{*static_cast<Window*>(data)};
    xdg_surface_ack_configure(shell, serial);
    const int bytes{window.width * window.height * 4};
    const int fd{memfd_create("mouse-probe-buffer", MFD_CLOEXEC)};
    if (fd < 0 || ftruncate(fd, bytes))
        std::abort();
    auto* pixels{static_cast<std::uint32_t*>(mmap(nullptr, bytes, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0))};
    if (pixels == MAP_FAILED)
        std::abort();
    std::fill_n(pixels, window.width * window.height, 0xff224466U);
    auto* owner{static_cast<Client*>(wl_proxy_get_user_data(reinterpret_cast<wl_proxy*>(window.surface)))};
    auto* pool{wl_shm_create_pool(owner->shm, fd, bytes)};
    auto* previous{window.buffer};
    window.buffer = wl_shm_pool_create_buffer(pool, 0, window.width, window.height, window.width * 4, WL_SHM_FORMAT_XRGB8888);
    wl_shm_pool_destroy(pool);
    munmap(pixels, bytes);
    close(fd);
    if (previous)
        wl_buffer_destroy(previous);
    wl_surface_attach(window.surface, window.buffer, 0, 0);
    wl_surface_damage(window.surface, 0, 0, window.width, window.height);
    wl_surface_commit(window.surface);
}

const xdg_surface_listener surface_listener{configured};
void top_configure(void* data, xdg_toplevel*, std::int32_t width, std::int32_t height, wl_array*) {
    auto& window{*static_cast<Window*>(data)};
    if (width > 0)
        window.width = width;
    if (height > 0)
        window.height = height;
    std::cerr << "configure " << window.title << ' ' << window.width << 'x' << window.height << '\n';
}
void top_close(void*, xdg_toplevel*) {}
const xdg_toplevel_listener top_listener{top_configure, top_close, nullptr, nullptr};

bool roundtrip(Client& client) {
    return wl_display_roundtrip(client.display) >= 0 && wl_display_roundtrip(client.display) >= 0;
}

int run(const std::filesystem::path& socket, Backend backend) {
    Client client{.backend = backend};
    client.display = wl_display_connect(socket.c_str());
    if (!client.display)
        return 2;
    auto* registry{wl_display_get_registry(client.display)};
    wl_registry_add_listener(registry, &registry_listener, &client);
    if (!roundtrip(client) || !client.compositor || !client.shm || !client.shell || !client.seat
        || (backend == Backend::kwin && !client.fake)
        || (backend == Backend::hyprland && !client.virtual_pointer))
        return 3;
    if (client.fake)
        org_kde_kwin_fake_input_authenticate(client.fake, "mouse-native-probe", "contained acceptance");
    client.windows.resize(2);
    for (std::size_t index{0}; index < client.windows.size(); ++index) {
        auto& window{client.windows[index]};
        window.title = index == 0 ? "MMB Lab A" : "MMB Lab B";
        window.surface = wl_compositor_create_surface(client.compositor);
        wl_proxy_set_user_data(reinterpret_cast<wl_proxy*>(window.surface), &client);
        window.shell = xdg_wm_base_get_xdg_surface(client.shell, window.surface);
        xdg_surface_add_listener(window.shell, &surface_listener, &window);
        window.top = xdg_surface_get_toplevel(window.shell);
        xdg_toplevel_add_listener(window.top, &top_listener, &window);
        xdg_toplevel_set_title(window.top, window.title.c_str());
        xdg_toplevel_set_app_id(window.top, app_id);
        wl_surface_commit(window.surface);
    }
    if (!roundtrip(client))
        return 4;
    std::cout << "ready" << std::endl;
    for (std::string command; std::getline(std::cin, command);) {
        if (command == "quit")
            break;
        if (command != "sync") {
            std::istringstream input{command};
            std::string action;
            int x{}, y{};
            if (!(input >> action >> x >> y) || action != "move"
                || x < 0 || y < 0 || x >= output_width || y >= output_height)
                return 5;
            if (backend == Backend::kwin)
                org_kde_kwin_fake_input_pointer_motion_absolute(client.fake, wl_fixed_from_int(x), wl_fixed_from_int(y));
            else {
                zwlr_virtual_pointer_v1_motion_absolute(client.virtual_pointer, 1, x, y, output_width, output_height);
                zwlr_virtual_pointer_v1_frame(client.virtual_pointer);
            }
        }
        if (!roundtrip(client))
            return 6;
        std::cout << "done" << std::endl;
    }
    for (auto& window : client.windows) {
        xdg_toplevel_destroy(window.top);
        xdg_surface_destroy(window.shell);
        wl_surface_destroy(window.surface);
        wl_buffer_destroy(window.buffer);
    }
    roundtrip(client);
    wl_registry_destroy(registry);
    wl_display_disconnect(client.display);
    return 0;
}

} // namespace
} // namespace mouse_probe

int main(int argc, char** argv) {
    if (argc != 3 || std::filesystem::exists("/dev/input") || std::filesystem::exists("/dev/uinput"))
        return 1;
    const auto socket{std::filesystem::canonical(argv[1])};
    if (!socket.string().starts_with("/lab/runtime/") || socket.parent_path() != "/lab/runtime")
        return 1;
    const std::string backend{argv[2]};
    if (backend != "kwin" && backend != "hyprland")
        return 1;
    return mouse_probe::run(socket, backend == "kwin" ? mouse_probe::Backend::kwin : mouse_probe::Backend::hyprland);
}
