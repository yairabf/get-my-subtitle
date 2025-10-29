# CI/CD Quick Reference Card

## 🚀 Before You Commit

```bash
make check          # Run all checks (recommended!)
```

Or run individually:

```bash
make format         # Auto-fix code style issues
make lint           # Check code style (no changes)
make test-unit      # Run unit tests only
make test-cov       # Run tests + coverage report
```

## 📊 CI/CD Status Checks

When you create a PR, these checks will run:

| Check | What it does | Time |
|-------|-------------|------|
| ✅ Black | Code formatting | ~15s |
| ✅ isort | Import sorting | ~15s |
| ✅ Unit Tests | Tests (3.11, 3.12) | ~2-3m |
| ✅ Coverage | Coverage ≥ 70% | ~2-3m |
| ✅ Integration | Real services test | ~4-5m |
| ✅ Build | Docker builds | ~3-4m |

## 🔧 Fixing Common Issues

### Black formatting failed
```bash
black .
git add .
git commit -m "style: apply black formatting"
```

### isort failed
```bash
isort .
git add .
git commit -m "style: sort imports"
```

### Coverage too low
```bash
# See what's missing
pytest --cov=common --cov=manager --cov-report=html
open htmlcov/index.html
# Add tests for uncovered code
```

### Tests failing
```bash
# Run tests locally
pytest tests/ -v
# Run specific test
pytest tests/path/to/test_file.py::test_name -v
```

## 🎯 Git Workflow

```bash
# 1. Create feature branch
git checkout -b feat/my-feature

# 2. Make changes
# ... edit files ...

# 3. Check locally
make check

# 4. Commit
git add .
git commit -m "feat: add new feature"

# 5. Push
git push origin feat/my-feature

# 6. Create PR on GitHub
# Wait for CI to pass ✅
# Get review approval ✅
# Merge! 🎉
```

## 📝 Commit Message Format

Use conventional commits:

```
type(scope): description

feat: new feature
fix: bug fix
docs: documentation
style: formatting
refactor: code restructure
test: add tests
chore: maintenance
```

Examples:
```bash
git commit -m "feat(manager): add subtitle caching"
git commit -m "fix(downloader): handle network errors"
git commit -m "test(common): add parser edge cases"
```

## 🆘 Emergency: CI is Broken

### Option 1: Fix Forward (Preferred)
```bash
# Create hotfix branch
git checkout -b hotfix/ci-fix

# Make fix
# ... fix the issue ...

# Test locally
make check

# Push and create PR
git push origin hotfix/ci-fix
```

### Option 2: Revert (If needed)
```bash
git revert <commit-hash>
git push
```

## 🔍 Checking CI Status

**In GitHub:**
- Go to **Actions** tab
- Click on workflow run
- Check individual job logs

**In PR:**
- Scroll to bottom of PR
- See all required checks
- Click "Details" for logs

**Via Badge:**
- Check README badges for overall status

## 💡 Pro Tips

1. **Run `make check` before pushing** - catches issues early
2. **Use `pytest -k "test_name"` ** - run specific tests
3. **Check coverage locally** - don't wait for CI
4. **Read failure logs** - they usually tell you exactly what's wrong
5. **Keep PRs small** - faster reviews, faster CI

## 🎓 Learning Resources

- [GitHub Actions Docs](https://docs.github.com/en/actions)
- [pytest Docs](https://docs.pytest.org/)
- [Black Docs](https://black.readthedocs.io/)
- [Conventional Commits](https://www.conventionalcommits.org/)

## 📞 Need Help?

1. Check [SETUP_CI.md](.github/SETUP_CI.md)
2. Check [CI_CD_SUMMARY.md](.github/CI_CD_SUMMARY.md)
3. Check workflow logs in Actions tab
4. Ask in team chat
5. Open an issue with `ci/cd` label

---

**Remember:** CI is here to help, not hinder. It catches bugs before they reach production! 🛡️

