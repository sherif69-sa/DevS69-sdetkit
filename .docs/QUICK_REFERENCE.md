# Repository Organization Quick Reference

## 📂 Current Structure (After Reorganization)

```
DevS69-sdetkit/
│
├── 📄 Core Configuration
│   ├── README.md
│   ├── LICENSE
│   ├── Makefile
│   ├── pyproject.toml
│   ├── mkdocs.yml
│   └── .gitignore
│
├── 📚 Documentation (.docs/)
│   ├── ARCHITECTURE.md
│   ├── CONTRIBUTING.md
│   ├── CODE_OF_CONDUCT.md
│   ├── SECURITY.md
│   ├── SUPPORT.md
│   ├── ENTERPRISE_OFFERINGS.md
│   ├── QUALITY_PLAYBOOK.md
│   ├── REPOSITORY_STRUCTURE.md (NEW)
│   ├── REORGANIZATION_SUMMARY.md (NEW)
│   ├── REORGANIZATION_COMPLETE.md (NEW)
│   ├── guides/
│   ├── api/
│   └── enterprise/
│
├── ⚙️ Configuration (.config/)
│   ├── ci/
│   └── quality/
│
├── 🔧 Development
│   ├── .venv/ (virtual environment)
│   ├── .github/ (GitHub Actions)
│   ├── .sdetkit/ (runtime state)
│   └── .pre-commit-config.yaml
│
├── 📦 Dependencies
│   ├── requirements.txt
│   ├── requirements-test.txt
│   ├── requirements-docs.txt
│   ├── constraints-ci.txt
│   └── poetry.lock (single source)
│
├── 🛠️ Source Code (src/sdetkit/)
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli/              (CLI interface)
│   ├── core/             (Core infrastructure)
│   ├── gates/            (Quality gates)
│   ├── phases/           (Phase operations)
│   ├── readiness/        (Readiness checks)
│   ├── evidence/         (Evidence collection)
│   ├── intelligence/     (Analysis)
│   ├── ops/              (Operations)
│   ├── legacy/           (Legacy support)
│   ├── utils/            (Utilities)
│   ├── checks/           (Quality checks)
│   ├── agent/            (Agent orchestration)
│   ├── data/             (Data structures)
│   ├── templates/        (Templates)
│   ├── maintenance/      (Maintenance)
│   └── [loose modules]   (To be organized in Phase 2)
│
├── 📋 Documentation Site
│   └── docs/             (MkDocs output)
│
├── 🧪 Tests
│   └── tests/
│
├── 📜 Scripts
│   └── scripts/
│
├── 🎨 Templates
│   └── templates/
│
└── 🔨 Tools
    └── tools/
```

## 🚀 Quick Commands

### View Organization Guide
```bash
cat .docs/REPOSITORY_STRUCTURE.md
```

### View What Changed
```bash
cat .docs/REORGANIZATION_SUMMARY.md
```

### View Organization Status
```bash
cat .docs/REORGANIZATION_COMPLETE.md
```

### Install & Test Project
```bash
make bootstrap    # Set up environment
make test         # Run tests
make lint         # Check code style
```

## 📍 Where to Find Things

| What You Need | Location | File Type |
|---|---|---|
| Architecture info | `.docs/ARCHITECTURE.md` | 📄 |
| Contributing guide | `.docs/CONTRIBUTING.md` | 📄 |
| Security policy | `.docs/SECURITY.md` | 📄 |
| Code of conduct | `.docs/CODE_OF_CONDUCT.md` | 📄 |
| CLI code | `src/sdetkit/cli/` | 🐍 |
| Quality gates | `src/sdetkit/gates/` | 🐍 |
| Phase logic | `src/sdetkit/phases/` | 🐍 |
| Readiness checks | `src/sdetkit/readiness/` | 🐍 |
| Evidence collection | `src/sdetkit/evidence/` | 🐍 |
| Analysis logic | `src/sdetkit/intelligence/` | 🐍 |
| Operations | `src/sdetkit/ops/` | 🐍 |
| Utilities | `src/sdetkit/utils/` | 🐍 |
| Tests | `tests/` | 🧪 |
| Development scripts | `scripts/` | 📜 |

## ✅ Completed Tasks

- [x] Create `.docs/` directory structure
- [x] Move policy & documentation files to `.docs/`
- [x] Remove duplicate lock files
- [x] Create `.config/` directory structure
- [x] Create `src/sdetkit/` subdirectories
- [x] Create REPOSITORY_STRUCTURE.md guide
- [x] Create REORGANIZATION_SUMMARY.md documentation
- [x] Create this quick reference guide

## 📋 Optional Phase 2 Tasks (Not Required)

These tasks are optional and can be done later if desired:

- [ ] Move loose modules to appropriate subdirectories
- [ ] Update all internal imports
- [ ] Move CI templates to `.config/ci/`
- [ ] Move docs config to `.config/docs/`
- [ ] Consolidate numbered module versions
- [ ] Create integration modules directory
- [ ] Update CI/CD to reference new structure

## 💡 Tips for Maintaining Organization

1. **New documentation?** → Add to `.docs/`
2. **New CLI command?** → Add to `src/sdetkit/cli/`
3. **New quality check?** → Add to `src/sdetkit/checks/`
4. **New utility?** → Add to `src/sdetkit/utils/`
5. **New test?** → Add to `tests/`
6. **New script?** → Add to `scripts/`

## 🆘 Need Help?

- **Can't find something?** → Check REPOSITORY_STRUCTURE.md
- **Want to understand changes?** → Read REORGANIZATION_SUMMARY.md
- **Contributing guide?** → See CONTRIBUTING.md in .docs/
- **Architecture questions?** → See ARCHITECTURE.md in .docs/

---

**Last Updated**: 2026-04-21
**Reorganization Status**: Phase 1 Complete ✅
