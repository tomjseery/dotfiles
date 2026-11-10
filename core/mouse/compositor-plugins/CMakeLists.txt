cmake_minimum_required(VERSION 3.26)
project(mouse_target_bridges VERSION 0.1.0 LANGUAGES CXX)

option(BUILD_KWIN_BRIDGE "Build the KWin 6.8.2 pointer-focus bridge" ON)
option(BUILD_HYPRLAND_BRIDGE "Build the Hyprland 0.57.1 pointer-focus bridge" ON)

if(BUILD_KWIN_BRIDGE)
    find_package(Qt6 REQUIRED COMPONENTS Core DBus Gui Quick Widgets)
    find_package(KF6CoreAddons REQUIRED)
    find_package(KWin 6.8.2 EXACT REQUIRED)
    add_library(mousetarget MODULE kwin.cpp)
    target_compile_definitions(mousetarget PRIVATE KPLUGINFACTORY_PLUGIN_CLASS_INTERNAL_NAME=mousetarget_factory)
    set_target_properties(mousetarget PROPERTIES AUTOMOC ON PREFIX "")
    target_compile_features(mousetarget PRIVATE cxx_std_23)
    set_target_properties(mousetarget PROPERTIES CXX_EXTENSIONS OFF)
    target_compile_options(mousetarget PRIVATE -Wall -Wextra -Wpedantic)
    target_link_libraries(mousetarget PRIVATE KWin::kwin Qt6::DBus)
endif()

if(BUILD_HYPRLAND_BRIDGE)
    find_package(PkgConfig REQUIRED)
    pkg_check_modules(HYPRLAND REQUIRED IMPORTED_TARGET hyprland=0.57.1)
    find_package(nlohmann_json 3.12 REQUIRED)
    add_library(mouse_target_hyprland MODULE hyprland.cpp)
    target_compile_features(mouse_target_hyprland PRIVATE cxx_std_23)
    set_target_properties(mouse_target_hyprland PROPERTIES
        CXX_EXTENSIONS OFF PREFIX ""
    )
    target_compile_options(mouse_target_hyprland PRIVATE -Wall -Wextra -Wpedantic)
    target_link_libraries(mouse_target_hyprland PRIVATE
        PkgConfig::HYPRLAND nlohmann_json::nlohmann_json
    )
endif()
