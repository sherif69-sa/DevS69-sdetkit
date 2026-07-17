# C++ quality and security evidence

SDETKit reports C++ quality and security tools only when a repository owns explicit configuration, workflow, command, or artifact evidence. A generic C++ source tree does not imply that a tool is installed, configured, or used.

This adapter is read-only. It does not install or run CMake, compilers, analyzers, formatters, sanitizers, CodeQL, or target tests. Every discovered command remains advisory and manual.

## Supported evidence

| Surface | Evidence required | Reported result |
| --- | --- | --- |
| `clang-tidy` | Owned `.clang-tidy`, active CMake configuration, a literal CMake preset value, or an exact non-mutating repository command | `clang_tidy` security/quality evidence and an advisory command only when the command itself is literal |
| `cppcheck` | Exact active configuration text or an exact repository command | `cppcheck` evidence and an advisory command when literal |
| Clang/GCC sanitizers | Explicit active `-fsanitize=` or `/fsanitize=` flags in owned CMake, preset, script, or workflow evidence | Named sanitizer evidence such as address, undefined-behavior, thread, memory, or leak sanitizer |
| CodeQL C/C++ | A repository-owned GitHub Actions workflow using `github/codeql-action/init` with literal `languages: c-cpp` | `codeql_cpp` evidence |
| `clang-format` | Owned `.clang-format` or an exact non-mutating `clang-format` command | `clang_format_evidence` artifact surface and an advisory quality command when literal |
| Compile database | Owned `compile_commands.json`, explicit `CMAKE_EXPORT_COMPILE_COMMANDS` enablement, or a literal analyzer command that references the database | `cpp_compile_database_contract` artifact surface |

## Commands remain manual

Exact repository commands retain their source file and working-directory context. They are emitted with:

```text
executes_untrusted_code=true
auto_run_allowed=false
automation_allowed=false
patch_application_allowed=false
merge_authorized=false
semantic_equivalence_proven=false
```

Commands that request source mutation are not recommended. This includes `clang-tidy` fix modes and in-place `clang-format` modes.

## Fail-closed behavior

SDETKit does not create a high-confidence claim from:

- C++ source or header files alone;
- comments or descriptive workflow text;
- dynamic variables, templates, shell interpolation, pipelines, or compound commands;
- generated build directories;
- vendored, external, dependency, or third-party trees;
- a CodeQL workflow whose language is dynamic or does not explicitly include `c-cpp`;
- disabled compile-database configuration;
- an analyzer name without executable repository context.

Ambiguous supported-tool evidence is recorded in `review_first_unknowns` rather than converted into a command or authority-bearing decision.

## Example artifact fragment

```json
{
  "security_tools": [
    {
      "name": "clang_tidy",
      "confidence": "detected",
      "evidence": ["CMakePresets.json"]
    }
  ],
  "artifact_surfaces": [
    {
      "name": "cpp_compile_database_contract",
      "confidence": "detected",
      "paths": ["CMakePresets.json"]
    }
  ],
  "automation_allowed": false,
  "patch_application_allowed": false,
  "merge_authorized": false,
  "semantic_equivalence_proven": false
}
```

The next C++ roadmap slice is the complete fixture-backed operator proof that composes discovery, advisory commands, saved failure normalization, FailureVector, SafetyGate, ProtectedVerifier, operator reporting, and reviewed learning evidence.
