cmake_minimum_required(VERSION 3.26)
project(midscrollcursor LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
set(BUILD_SHARED_LIBS ON)
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/lib")

find_package(Qt6 REQUIRED COMPONENTS Core Gui Network)
find_package(KF6CoreAddons REQUIRED)
find_package(KF6Config REQUIRED)
# KWin's exported CMake package requires Vulkan development headers even for
# an effect that never touches Vulkan. Link the installed KWin library directly
# so this small plugin does not force a system-wide graphics build dependency.
find_path(KWIN_INCLUDE_PARENT NAMES kwin/effect/effect.h REQUIRED)
find_library(KWIN_LIBRARY NAMES kwin REQUIRED)

kcoreaddons_add_plugin(midscrollcursor
    SOURCES midscrollcursor.cpp
    INSTALL_NAMESPACE "kwin/effects/plugins"
)
set_target_properties(midscrollcursor PROPERTIES PREFIX "")
target_include_directories(midscrollcursor PRIVATE "${KWIN_INCLUDE_PARENT}/kwin")
target_link_libraries(midscrollcursor PRIVATE
    "${KWIN_LIBRARY}"
    KF6::CoreAddons
    KF6::ConfigCore
    Qt6::Gui
    Qt6::Network
)
