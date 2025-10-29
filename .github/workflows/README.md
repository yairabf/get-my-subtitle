# GitHub Actions CI/CD Workflows

This directory contains GitHub Actions workflows for automated testing, code quality checks, and continuous integration.

## Workflows

### 1. CI Workflow (`ci.yml`)

**Triggers:**
- Push to `main`, `develop`, or any `feat/*` branches
- Pull requests to `main` or `develop`

**Jobs:**

#### Lint
- Checks code formatting with **Black**
- Checks import sorting with **isort**
- Fast feedback on code style issues

#### Unit Tests
- Runs unit tests on Python 3.11 and 3.12
- Tests marked with `@pytest.mark.unit`
- Uses mocked dependencies (no external services required)
- Uploads test results as artifacts

#### Coverage
- Runs tests with coverage reporting
- Generates coverage reports (XML, HTML, term)
- Uploads to Codecov (requires `CODECOV_TOKEN` secret)
- Fails if coverage drops below 70%
- Comments coverage summary on pull requests

#### Integration Tests
- Runs integration tests against real services
- Uses GitHub Actions services for Redis and RabbitMQ
- Tests marked with `@pytest.mark.integration`
- Validates end-to-end workflows

#### Build Check
- Builds all Docker images to ensure they compile
- Uses Docker layer caching for speed
- Validates Dockerfiles for all services

#### Status Check
- Final job that checks if all previous jobs passed
- Provides single status check for branch protection rules

### 2. Lint Workflow (`lint.yml`)

**Triggers:**
- Push to `main`, `develop`, or any `feat/*` branches
- Pull requests to `main` or `develop`

**Jobs:**

#### Black
- Checks Python code formatting
- Auto-comments on PRs with formatting issues
- Run locally: `black .` or `make format`

#### isort
- Checks import statement sorting
- Auto-comments on PRs with import issues
- Run locally: `isort .` or `make format`

#### Pylint (Optional)
- Runs static code analysis
- Continues on error (doesn't fail CI)
- Provides additional code quality insights
- Uploads report as artifact

## Required Secrets

### Codecov (Optional but Recommended)
1. Sign up at [codecov.io](https://codecov.io)
2. Add your repository
3. Get the upload token
4. Add `CODECOV_TOKEN` to repository secrets

**How to add:**
```
Repository Settings → Secrets and variables → Actions → New repository secret
Name: CODECOV_TOKEN
Value: <your-token>
```

## Status Badges

Add these badges to your README.md:

```markdown
[![CI](https://github.com/YOUR_USERNAME/get-my-subtitle/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/get-my-subtitle/actions/workflows/ci.yml)
[![Lint](https://github.com/YOUR_USERNAME/get-my-subtitle/actions/workflows/lint.yml/badge.svg)](https://github.com/YOUR_USERNAME/get-my-subtitle/actions/workflows/lint.yml)
[![codecov](https://codecov.io/gh/YOUR_USERNAME/get-my-subtitle/branch/main/graph/badge.svg)](https://codecov.io/gh/YOUR_USERNAME/get-my-subtitle)
```

## Local Testing

Before pushing, run these commands to ensure CI will pass:

```bash
# Format code
make format

# Check formatting
make lint

# Run unit tests
make test-unit

# Run tests with coverage
make test-cov

# Run all checks (recommended before committing)
make check
```

## Branch Protection Rules

Recommended branch protection settings for `main` and `develop`:

1. **Require status checks to pass before merging**
   - CI Status Check
   - Check Black Formatting
   - Check Import Sorting

2. **Require branches to be up to date before merging**
   - ✅ Enabled

3. **Require linear history**
   - ✅ Enabled (optional)

4. **Require conversation resolution before merging**
   - ✅ Enabled

## Workflow Performance

### Typical Run Times

| Job | Duration | Notes |
|-----|----------|-------|
| Lint | ~30s | Very fast, runs first |
| Unit Tests | ~2-3 min | Parallel on multiple Python versions |
| Coverage | ~2-3 min | Includes coverage calculation |
| Integration Tests | ~4-5 min | Slower due to service startup |
| Build Check | ~3-4 min | Uses layer caching |
| **Total** | ~6-8 min | Jobs run in parallel |

### Optimization Tips

1. **Use caching**: Both workflows use pip caching and Docker layer caching
2. **Parallel jobs**: Jobs run concurrently when possible
3. **Fast failures**: Lint runs first and fails fast
4. **Minimal dependencies**: Lint jobs only install required packages

## Troubleshooting

### Build Failures

**Black formatting issues:**
```bash
# Fix locally
black .
git add .
git commit -m "fix: apply black formatting"
```

**isort import sorting issues:**
```bash
# Fix locally
isort .
git add .
git commit -m "fix: sort imports with isort"
```

**Coverage below threshold:**
```bash
# Check coverage locally
pytest --cov=common --cov=manager --cov-report=html
# Open htmlcov/index.html to see what's missing
# Add tests to increase coverage
```

**Integration tests failing:**
```bash
# Run integration tests locally with Docker
make up-infra  # Start Redis and RabbitMQ
pytest tests/integration/ -v
make down      # Clean up
```

### GitHub Actions Issues

**Services not starting:**
- Check service health checks in `ci.yml`
- Ensure ports are correctly mapped
- Verify environment variables are set

**Artifacts not uploading:**
- Check artifact paths exist after test runs
- Verify retention-days is appropriate
- Check artifact size limits (500MB default)

**Codecov upload failing:**
- Verify `CODECOV_TOKEN` secret is set correctly
- Check network connectivity in workflow logs
- Ensure coverage.xml is generated

## Extending Workflows

### Adding New Tests

1. Add tests in `tests/` directory
2. Mark appropriately:
   - `@pytest.mark.unit` for unit tests
   - `@pytest.mark.integration` for integration tests
3. Tests will automatically run in CI

### Adding New Services

To add a new service to integration tests:

```yaml
services:
  your-service:
    image: your-service:latest
    ports:
      - 8080:8080
    env:
      YOUR_ENV: value
    options: >-
      --health-cmd "your-health-check"
      --health-interval 10s
      --health-timeout 5s
      --health-retries 5
```

### Adding New Linters

To add a new linter (e.g., flake8):

```yaml
flake8:
  name: Check Flake8
  runs-on: ubuntu-latest
  steps:
  - uses: actions/checkout@v4
  - uses: actions/setup-python@v5
    with:
      python-version: '3.11'
  - run: pip install flake8
  - run: flake8 .
```

## Best Practices

1. **Keep workflows fast**: Use caching, parallel jobs, and fast failures
2. **Test locally first**: Use `make check` before pushing
3. **Monitor workflow runs**: Check Actions tab regularly
4. **Update dependencies**: Keep action versions up to date
5. **Use secrets properly**: Never commit tokens or credentials
6. **Document changes**: Update this README when modifying workflows

## Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [pytest Documentation](https://docs.pytest.org/)
- [Black Documentation](https://black.readthedocs.io/)
- [isort Documentation](https://pycqa.github.io/isort/)
- [Codecov Documentation](https://docs.codecov.com/)

