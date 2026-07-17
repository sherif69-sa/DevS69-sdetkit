#!/usr/bin/env sh
set -eu

clang-tidy -p build/ci src/calculator.cpp
cppcheck --project=build/ci/compile_commands.json --enable=warning
clang-format --dry-run --Werror src/calculator.cpp tests/calculator_test.cpp
