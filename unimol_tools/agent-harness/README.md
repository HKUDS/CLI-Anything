# Uni-Mol Tools - Agent Harness

CLI-Anything harness for Uni-Mol Tools - Interactive molecular property prediction.

## 🚀 Quick Start

### Running the Demo

The fastest way to see all features in action:

```bash
# Provide path to examples directory
bash demo_real_examples.sh /path/to/examples
```

**Test Data**: Example datasets can be obtained from [https://github.com/545487677/CLI-Anything-unimol-tools/tree/main/unimol_tools/examples](https://github.com/545487677/CLI-Anything-unimol-tools/tree/main/unimol_tools/examples)

See [README_DEMO.md](README_DEMO.md) for detailed demo documentation.

### Installation & Usage

For complete installation and usage instructions, see the [documentation](docs/README.md).

## 📚 Documentation

- **Demo Guide**: [README_DEMO.md](README_DEMO.md) - Run the complete demo
- **Full Docs**: [docs/README.md](docs/README.md) - Complete documentation index
- **Test Report**: [docs/test/TEST_REPORT.md](docs/test/TEST_REPORT.md) - Test suite status

## 🎯 Features

- **Project Management** - Organize your experiments
- **Interactive Model Management** - Storage analysis, ranking, cleanup
- **5 Task Types** - Classification, regression, multiclass, multilabel
- **Automatic Model Tracking** - Performance history and trends
- **Smart Cleanup** - Intelligent storage management
- **JSON API** - Automation-friendly

## 🧪 Testing

Run the test suite:

```bash
cd docs/test
bash run_tests.sh --unit -v
```

Test Status: ✅ **67/67 tests passing (100%)**

## 📁 Project Structure

```
agent-harness/
├── README.md                    # This file
├── README_DEMO.md              # Demo documentation
├── demo_real_examples.sh       # Demo script
├── cli_anything/               # Source code
│   └── unimol_tools/
│       ├── core/              # Core functionality
│       ├── tests/             # Test suite
│       └── utils/             # Utilities
└── docs/                       # Complete documentation
    ├── guides/                # User guides
    ├── tutorials/             # Step-by-step tutorials
    ├── architecture/          # Technical docs
    ├── workflows/             # SOPs and workflows
    └── test/                  # Test documentation
```

## 🔗 Links

- **Documentation**: [docs/README.md](docs/README.md)
- **Quick Start**: [docs/guides/02-QUICK-START.md](docs/guides/02-QUICK-START.md)
- **Installation**: [docs/guides/01-INSTALLATION.md](docs/guides/01-INSTALLATION.md)

---

**Version**: 1.0.0
**Status**: Production Ready ✓
