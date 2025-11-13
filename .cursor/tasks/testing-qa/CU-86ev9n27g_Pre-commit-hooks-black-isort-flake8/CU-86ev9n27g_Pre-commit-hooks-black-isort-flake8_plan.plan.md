---
epic: testing-qa
task: CU-86ev9n27g_Pre-commit-hooks-black-isort-flake8
created: 2025-01-13
---

# Pre-commit Hooks (black, isort, flake8) - Implementation Plan

## Overview

This plan implements automated code formatting and linting checks via pre-commit hooks to maintain consistent code style and quality. The hooks will run automatically before each commit, ensuring all code follows project standards.

## Current State Analysis

### Existing Tools
- **Black** (24.10.0) - Already in `requirements.txt`
- **isort** (5.13.2) - Already in `requirements.txt`
- **Flake8** - Used in CI scripts but NOT in `requirements.txt`
- **isort config** - `.isort.cfg` exists with `profile = black`
- **Makefile** - Has `lint` and `format` targets for manual checks

### Missing Components
- Pre-commit framework not installed
- No `.pre-commit-config.yaml` file
- Flake8 not in `requirements.txt`
- No flake8 configuration file (using CLI args in CI scripts)

## Implementation Steps

### 1. Add Dependencies to requirements.txt

**File**: `requirements.txt`

Add:
- `pre-commit>=3.0.0` - Pre-commit framework
- `flake8>=7.0.0` - Linting tool (currently missing from requirements)

**Location**: Add after existing formatting tools (after isort line)

### 2. Create .pre-commit-config.yaml

**File**: `.pre-commit-config.yaml` (new file)

Configure hooks for:
- **black** - Code formatting (using version 24.10.0 to match requirements.txt)
- **isort** - Import sorting (using version 5.13.2 to match requirements.txt)
- **flake8** - Linting (using latest stable version)

**Configuration details**:
- Use `default_language_version: python: python3.11` to match project Python version
- Configure flake8 with same settings as CI: `--max-line-length=120 --extend-ignore=E203,W503`
- Set appropriate file patterns (Python files only)
- Use official pre-commit hooks for all tools

### 3. Create Flake8 Configuration File

**File**: `.flake8` (new file)

Create configuration file to match CI script settings:
```ini
[flake8]
max-line-length = 120
extend-ignore = E203, W503
exclude = 
    .git,
    __pycache__,
    venv,
    .venv,
    build,
    dist,
    *.egg-info
```

This ensures consistency between pre-commit hooks and CI/CD pipeline.

### 4. Update Documentation

**Files to update**:
- `README.md` - Add pre-commit installation and usage instructions

**Documentation should include**:
- Installation steps: `pre-commit install`
- Manual run: `pre-commit run --all-files`
- Bypass instructions (if needed): `git commit --no-verify`
- Integration with existing Makefile targets

## Configuration Details

### Pre-commit Hook Configuration

Based on Context7 best practices and project requirements:

1. **Black Hook**:
   - Use official pre-commit hook
   - Match version: 24.10.0
   - Run on all Python files

2. **isort Hook**:
   - Use official pre-commit hook
   - Match version: 5.13.2
   - Respect existing `.isort.cfg` configuration (profile = black)
   - Run on all Python files

3. **Flake8 Hook**:
   - Use official flake8 pre-commit hook
   - Configure with max-line-length=120 and extend-ignore=E203,W503
   - Use `.flake8` config file for consistency
   - Run on all Python files

### Hook Execution Order

1. isort (fixes import order)
2. black (formats code)
3. flake8 (lints code - should pass after formatting)

## Files to Create/Modify

### New Files
1. `.pre-commit-config.yaml` - Pre-commit configuration
2. `.flake8` - Flake8 configuration file

### Modified Files
1. `requirements.txt` - Add pre-commit and flake8
2. `README.md` - Add pre-commit documentation section

## Testing Strategy

### Manual Testing Steps

1. **Install pre-commit**:
   ```bash
   pip install -r requirements.txt
   pre-commit install
   ```

2. **Test hooks manually**:
   ```bash
   pre-commit run --all-files
   ```

3. **Test commit hook**:
   - Make a small code change
   - Attempt to commit
   - Verify hooks run automatically
   - Verify hooks can fix issues automatically (black, isort)
   - Verify hooks fail on unfixable issues (flake8)

4. **Test with existing codebase**:
   - Run `pre-commit run --all-files` on current codebase
   - Fix any issues found
   - Verify all hooks pass

### Integration Testing

- Verify hooks work with existing Makefile targets (`make lint`, `make format`)
- Ensure CI/CD pipeline still works (hooks should not interfere)
- Test on clean repository clone

## Success Criteria

1. ✅ Pre-commit framework installed and configured
2. ✅ All three hooks (black, isort, flake8) configured and working
3. ✅ Hooks run automatically on `git commit`
4. ✅ Manual execution works: `pre-commit run --all-files`
5. ✅ Configuration matches existing CI/CD settings
6. ✅ Documentation updated with installation and usage instructions
7. ✅ All hooks pass on current codebase (or issues are documented)
8. ✅ Flake8 configuration file created and matches CI settings

## Dependencies

- Python 3.11 (already in use)
- Existing black and isort installations (already in requirements.txt)
- Git repository (already initialized)

## Notes

- Pre-commit hooks will use local Python environment (venv if available)
- Hooks respect existing configuration files (`.isort.cfg`, `.flake8`)
- Can be bypassed with `--no-verify` flag if needed (documented)
- Hooks run only on staged files by default (faster)
- Use `--all-files` flag to check entire codebase

## Potential Issues and Solutions

1. **Issue**: Hooks fail on existing codebase
   - **Solution**: Run `pre-commit run --all-files` and fix issues, or configure hooks to only check changed files initially

2. **Issue**: Slow hook execution
   - **Solution**: Hooks only run on staged files by default, which is fast. For full codebase checks, use Makefile targets.

3. **Issue**: Conflicts with existing CI/CD
   - **Solution**: Ensure hook configurations match CI settings exactly (same versions, same arguments)

