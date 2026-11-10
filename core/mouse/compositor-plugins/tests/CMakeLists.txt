cmake_minimum_required(VERSION 3.26)
project(mouse_target_probe LANGUAGES C CXX)

find_package(PkgConfig REQUIRED)
pkg_check_modules(WAYLAND REQUIRED IMPORTED_TARGET wayland-client>=1.26)
find_program(WAYLAND_SCANNER wayland-scanner REQUIRED)
if(NOT IS_DIRECTORY "${PROTOCOL_DIR}")
    message(FATAL_ERROR "PROTOCOL_DIR must contain the harness-verified XML inputs")
endif()

set(protocol_sources)
foreach(protocol IN ITEMS fake-input virtual-pointer xdg-shell)
    set(header "${CMAKE_CURRENT_BINARY_DIR}/${protocol}-client.h")
    set(source "${CMAKE_CURRENT_BINARY_DIR}/${protocol}-protocol.c")
    add_custom_command(OUTPUT "${header}" "${source}"
        COMMAND "${WAYLAND_SCANNER}" client-header "${PROTOCOL_DIR}/${protocol}.xml" "${header}"
        COMMAND "${WAYLAND_SCANNER}" private-code "${PROTOCOL_DIR}/${protocol}.xml" "${source}"
        DEPENDS "${PROTOCOL_DIR}/${protocol}.xml"
        VERBATIM
    )
    list(APPEND protocol_sources "${header}" "${source}")
endforeach()
add_library(mouse_probe_protocols STATIC ${protocol_sources})
target_link_libraries(mouse_probe_protocols PUBLIC PkgConfig::WAYLAND)
target_include_directories(mouse_probe_protocols PUBLIC "${CMAKE_CURRENT_BINARY_DIR}")

add_executable(mouse-target-client client.cpp)
target_compile_features(mouse-target-client PRIVATE cxx_std_23)
set_target_properties(mouse-target-client PROPERTIES CXX_EXTENSIONS OFF)
target_compile_options(mouse-target-client PRIVATE -Wall -Wextra -Wpedantic)
target_link_libraries(mouse-target-client PRIVATE mouse_probe_protocols)
