cmake_minimum_required(VERSION 3.24)
project(calculator LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_CLANG_TIDY clang-tidy)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

add_library(calculator src/calculator.cpp)
target_include_directories(calculator PUBLIC include)

add_executable(calculator_tests tests/calculator_test.cpp)
target_link_libraries(calculator_tests PRIVATE calculator)

enable_testing()
add_test(NAME calculator_tests COMMAND calculator_tests)
