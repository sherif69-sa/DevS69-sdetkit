# Repository Structure Guide

This document explains the organization of the DevS69-sdetkit repository.

## Root Level

```
DevS69-sdetkit/
├── .docs/                    # Documentation (guides, architecture, policies)
├── .config/                  # Configuration files
├── .github/                  # GitHub-specific files (Actions, templates)
├── .sdetkit/                 # Local sdetkit runtime state
├── docs/                     # MkDocs documentation (published)
├── src/
│   └── sdetkit/              # Main package
├── tests/                    # Test suite
├── scripts/                  # Utility scripts
├── templates/                # Document templates
├── tools/                    # Development tools
├── build/                    # Build artifacts
└── [config files]            # pyproject.toml, Makefile, etc.
```

## Documentation Structure (.docs/)

- **ARCHITECTURE.md** - System architecture and design
- **CONTRIBUTING.md** - Contribution guidelines
- **CODE_OF_CONDUCT.md** - Community code of conduct
- **SECURITY.md** - Security policies and procedures
- **ENTERPRISE_OFFERINGS.md** - Enterprise-specific features
- **QUALITY_PLAYBOOK.md** - Quality guidelines
- **guides/** - How-to guides and tutorials
- **api/** - API documentation
- **enterprise/** - Enterprise-specific documentation

## Package Structure (src/sdetkit/)

```
src/sdetkit/
├── __init__.py                # Package initialization
├── __main__.py                # CLI entry point
├── cli/                       # Command-line interface modules
│   ├── cli.py
│   ├── cli_shortcuts.py
│   ├── playbook*.py
│   └── serve*.py
├── core/                      # Core infrastructure
│   ├── _toml.py
│   ├── _legacy_lane.py
│   ├── *dispatch*.py
│   └── parser*.py
├── gates/                     # Quality gates & checks
│   ├── gate.py
│   ├── security_gate.py
│   └── premium_gate_engine.py
├── phases/                    # Phase orchestration
│   ├── phase*.py              # Phase 1-6 modules
│   └── phase_boost.py
├── readiness/                 # Readiness assessments
│   ├── *readiness.py
│   ├── startup_readiness.py
│   └── launch_readiness*.py
├── evidence/                  # Evidence collection & assessment
│   ├── evidence.py
│   ├── trust*.py
│   └── reliability*.py
├── intelligence/              # Analysis & intelligence
│   ├── review*.py
│   ├── judgment.py
│   └── forensics.py
├── ops/                       # Operations & control
│   ├── ops.py
│   ├── ops_control.py
│   └── operator*.py
├── legacy/                    # Legacy support modules
│   └── legacy*.py
├── checks/                    # Check implementations (existing)
│   └── [check modules]
├── agent/                     # Agent orchestration (existing)
│   └── [agent modules]
├── data/                      # Data structures (existing)
│   └── [data modules]
├── maintenance/               # Maintenance utilities (existing)
│   └── [maintenance modules]
├── utils/                     # Utilities and helpers
│   ├── *util*.py
│   ├── textutil.py
│   ├── atomicio.py
│   └── bools.py
└── templates/                 # Template management (existing)
    └── [template modules]
```

## Key Modules by Category

### CLI & Interface
- `cli.py` - Main CLI interface
- `cli_shortcuts.py` - CLI shortcut definitions
- `playbook_aliases.py` - Playbook command aliases
- `playbooks_cli.py` - Playbook CLI operations
- `serve.py` - Server operations

### Quality Gates
- `gate.py` - Main gate implementation
- `security_gate.py` - Security-specific gates
- `premium_gate_engine.py` - Premium gate features
- `release_readiness.py` - Release readiness assessment

### Phase Management
- `phase1_*.py` - Phase 1 operations
- `phase2_*.py` - Phase 2 operations
- `phase3_*.py` - Phase 3 operations
- `phase4_*.py` - Phase 4 governance
- `phase5_*.py` - Phase 5 ecosystem
- `phase6_*.py` - Phase 6 metrics

### Assessment & Evidence
- `evidence.py` - Evidence collection
- `trust_*.py` - Trust asset management
- `reliability_*.py` - Reliability assessment
- `performance_readiness.py` - Performance assessment

### Operations
- `ops.py` - Core operations
- `ops_control.py` - Control flow
- `maintenance/` - Maintenance procedures

### Utilities
- `textutil.py` - Text manipulation
- `atomicio.py` - Atomic I/O operations
- `netclient.py` - Network operations
- `plugin_system.py` - Plugin infrastructure

## Configuration Files

Key configuration files at repository root:
- `pyproject.toml` - Python project configuration
- `Makefile` - Build and development tasks
- `mkdocs.yml` - Documentation site configuration
- `constraints-ci.txt` - CI dependency constraints
- `requirements.txt` - Production dependencies
- `requirements-test.txt` - Test dependencies
- `requirements-docs.txt` - Documentation dependencies

## Best Practices

1. **Keep root clean** - Only core configuration files at repository root
2. **Organize by feature** - Group related modules together
3. **Use __init__.py** - Every package directory needs one
4. **Document dependencies** - Keep import relationships clear
5. **Update imports** - When moving files, update all imports

## Future Improvements

- [ ] Group contract/check modules in `checks/` subdirectories
- [ ] Consolidate upgrade-related modules
- [ ] Organize closeout contract modules
- [ ] Create `integrations/` for external service modules
- [ ] Consolidate obsolete/legacy numbered versions
