# Repository Reorganization Summary

## Changes Made

### 1. Documentation Organization (.docs/)
✓ Created `.docs/` directory for centralized documentation
✓ Moved policy and guide files:
  - ARCHITECTURE.md
  - CONTRIBUTING.md
  - CODE_OF_CONDUCT.md
  - SECURITY.md
  - ENTERPRISE_OFFERINGS.md
  - QUALITY_PLAYBOOK.md
  - SUPPORT.md

✓ Created subdirectories:
  - `guides/` - Development and usage guides
  - `api/` - API documentation
  - `enterprise/` - Enterprise-specific documentation

**Note**: Original files remain at root for backward compatibility during transition.

### 2. Dependency Cleanup
✓ Removed duplicate lock files:
  - ✗ requirements.lock
  - ✗ requirements.txt.lock
✓ Kept single source of truth: `poetry.lock`

Remaining dependency files:
  - requirements.txt (production)
  - requirements-test.txt (testing)
  - requirements-docs.txt (documentation)
  - constraints-ci.txt (CI constraints)

### 3. Source Code Organization (src/sdetkit/)
Created logical package subdirectories for better code organization:

#### Created Directories:

| Directory | Purpose | Module Types |
|-----------|---------|-------------|
| `cli/` | Command-line interface | CLI, playbooks, serve operations |
| `core/` | Core infrastructure | Parsers, dispatchers, TOML handling |
| `gates/` | Quality gates & checks | Gate implementations, security gates |
| `phases/` | Phase orchestration | Phase 1-6 operations, control flow |
| `readiness/` | Readiness assessments | Readiness checks, startup, launch |
| `evidence/` | Evidence & assessment | Evidence collection, trust, reliability |
| `intelligence/` | Analysis & intelligence | Review, judgment, forensics |
| `ops/` | Operations & control | Operations, control loops, operators |
| `legacy/` | Legacy code support | Backward compatibility modules |
| `utils/` | Utilities & helpers | Text, I/O, common utilities |

**Existing Directories** (not modified):
- `checks/` - Quality check implementations
- `agent/` - Agent orchestration
- `data/` - Data structures
- `maintenance/` - Maintenance utilities
- `templates/` - Template management

### 4. Configuration Organization (.config/)
Created `.config/` directory structure (ready for expansion):
```
.config/
├── ci/             (CI configuration)
└── quality/        (Quality configuration)
```

**Future candidates for .config/**:
- constraints-ci.txt → .config/ci/constraints.txt
- mkdocs.yml → .config/docs/mkdocs.yml

## Benefits

✅ **Improved Navigation** - Easier to find related modules
✅ **Better Scalability** - Clear structure for growth
✅ **Reduced Root Clutter** - Core config at root, policies organized
✅ **Cleaner Dependencies** - No duplicate lock files
✅ **Documentation Accessibility** - Centralized policy/guide documentation

## Migration Path

### Immediate (Phase 1 - Complete)
- [x] Create .docs/ structure
- [x] Move documentation files
- [x] Remove duplicate lock files
- [x] Create src/sdetkit/ subdirectories

### Next Steps (Phase 2 - Pending Module Migration)
- [ ] Move CLI modules to cli/
- [ ] Move core infrastructure to core/
- [ ] Move gate modules to gates/
- [ ] Move phase operations to phases/
- [ ] Move readiness assessment modules to readiness/
- [ ] Move evidence/intelligence modules to evidence/ and intelligence/
- [ ] Update all internal imports
- [ ] Update CI/CD configurations

### Future (Phase 3 - Advanced Organization)
- [ ] Contract modules → checks/contracts/
- [ ] Integration modules → integrations/
- [ ] Consolidate vertically-numbered modules (cleanup/v1, /v2, etc.)
- [ ] Create examples/ subdirectory structure

## Testing & Validation

Before proceeding with Phase 2 module migration:
1. Run full test suite: `make test`
2. Check imports: `python -c "import sdetkit; print('OK')"`
3. Verify CLI: `sdetkit --help`
4. Run linters: `make lint`

## References

- See [REPOSITORY_STRUCTURE.md](.docs/REPOSITORY_STRUCTURE.md) for detailed organization guide
- Original documentation remains accessible at root
- .docs/ becomes the single source of truth for policies

## Questions & Revisions

This reorganization is designed to be:
- **Non-breaking** - Original files remain during transition
- **Incremental** - Changes can be staged across releases
- **Reversible** - No permanent changes to functionality

For questions or suggestions, refer to CONTRIBUTING.md
