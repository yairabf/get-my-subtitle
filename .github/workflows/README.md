# GitHub Actions Workflows

This directory contains the CI/CD pipeline for the Get My Subtitle project.

## CI Pipeline (`ci.yml`)

A comprehensive CI pipeline that runs on every push and pull request, ensuring code quality, test coverage, and build validation.

### Pipeline Stages

#### 1. **Code Quality (Linting)**
- **Black**: Checks code formatting
- **isort**: Validates import sorting
- **Flake8**: Linting validation
- Runs on: Python 3.11
- Fast execution: ~30-60 seconds
- Timeout: 5 minutes

#### 2. **Unit Tests** (Matrix Strategy)
- Runs all unit tests with coverage
- Tests: `common/`, `manager/`, `downloader/`, `translator/`, `scanner/`
- Coverage requirement: 60% minimum
- **Python Versions**: 3.11, 3.12 (matrix strategy)
- Generates:
  - JUnit XML test results
  - Coverage XML and HTML reports
- Execution time: ~2-3 minutes per Python version
- Timeout: 10 minutes per job

#### 3. **Integration Tests**
- Tests with real Redis and RabbitMQ services
- Validates end-to-end message queue flows
- Services: Redis 7 (Alpine), RabbitMQ 3 (Management Alpine)
- Health checks with automatic retries
- Generates JUnit XML test results
- Runs on: Python 3.11
- Execution time: ~2-5 minutes
- Timeout: 15 minutes

#### 4. **Docker Build Validation**
- Validates all service Dockerfiles build successfully
- Services: manager, downloader, translator, scanner, consumer
- Uses Docker Buildx with GitHub Actions cache
- Parallel builds for all services
- Execution time: ~3-5 minutes
- Timeout: 15 minutes

#### 5. **Security Checks**
- **Safety**: Scans dependencies for known vulnerabilities
- **Bandit**: Static analysis for security issues in code
- Scans: `common/`, `manager/`, `downloader/`, `translator/`, `scanner/`, `consumer/`
- Both checks are informational (won't fail CI)
- Generates security report artifacts
- Execution time: ~2-3 minutes
- Timeout: 10 minutes

#### 6. **CI Status Check**
- Aggregates results from all jobs
- Creates summary in GitHub Actions
- Fails if critical jobs fail (lint, unit tests, integration tests, docker build)
- Execution time: ~5 seconds
- Timeout: 2 minutes

### Total Pipeline Time
Expected duration: **6-10 minutes** for all checks to complete (with parallel execution).

### Workflow Triggers

```yaml
on:
  push:
    branches: [ main, develop, feat/* ]
  pull_request:
    branches: [ main, develop ]
  workflow_dispatch:  # Manual trigger
```

### Artifacts

The pipeline generates and uploads the following artifacts:

1. **test-results-py3.11** / **test-results-py3.12** (7 days retention)
   - JUnit XML test results for each Python version

2. **coverage-report-py3.11** / **coverage-report-py3.12** (7 days retention)
   - Coverage XML and HTML reports for each Python version

3. **integration-test-results** (7 days retention)
   - JUnit XML integration test results

4. **security-reports** (14 days retention)
   - Bandit JSON security scan results

### Running Checks Locally

Before pushing, run these commands locally to catch issues early:

```bash
# Linting
black .
isort .
flake8 --max-line-length=120 --extend-ignore=E203,W503 common/ manager/ downloader/ translator/ scanner/ consumer/

# Or use Makefile
make format  # Auto-fix formatting
make lint    # Check code style

# Unit tests with coverage
pytest tests/common tests/downloader tests/manager tests/translator tests/scanner \
  --ignore=tests/scanner/test_websocket_client.py \
  --ignore=tests/scanner/test_worker.py \
  -m "not integration" \
  --cov=common --cov=manager --cov=downloader --cov=translator --cov=scanner \
  --cov-report=term-missing --cov-report=html

# Integration tests (requires Docker)
docker-compose up -d redis rabbitmq
pytest tests/integration/ -v -m integration

# Docker build validation
docker build -f manager/Dockerfile -t test-manager .
docker build -f downloader/Dockerfile -t test-downloader .
docker build -f translator/Dockerfile -t test-translator .
docker build -f scanner/Dockerfile -t test-scanner .
docker build -f consumer/Dockerfile -t test-consumer .

# Security checks
pip install safety bandit
safety check
bandit -r common/ manager/ downloader/ translator/ scanner/ consumer/
```

## Lint Pipeline (`lint.yml`)

A fast, dedicated workflow for code quality checks that provides quick feedback on pull requests.

### Features

- **Fast Execution**: Completes in ~30-60 seconds
- **Auto-Comments**: Automatically comments on PRs with formatting issues
- **Fix Commands**: Provides specific commands to fix issues
- **Summary Reports**: Creates GitHub Actions summary with results

### Pipeline Stages

1. **Black Check**: Format validation
2. **isort Check**: Import sorting validation
3. **Flake8 Check**: Linting validation
4. **PR Comments**: Auto-comments on PRs with issues

### Workflow Triggers

```yaml
on:
  push:
    branches: [ main, develop, feat/* ]
  pull_request:
    branches: [ main, develop ]
```

### Running Locally

```bash
# Quick lint check
make lint

# Auto-fix issues
make format
```

## Design Philosophy

The CI/CD pipelines follow these principles:

1. **Comprehensive**: Tests on multiple Python versions, validates Docker builds
2. **Fast Feedback**: Separate lint workflow for quick code quality checks
3. **Parallel Execution**: Jobs run in parallel where possible
4. **Smart Caching**: Pip and Docker layer caching for faster builds
5. **Artifact Management**: Test results and coverage reports preserved
6. **Actionable**: Clear error messages and fix commands
7. **Reliable**: Health checks, timeouts, and proper error handling

## Troubleshooting

### Linting Failures

```bash
# Fix formatting issues
black .
isort .
git add -A
git commit -m "Fix formatting"

# Or use Makefile
make format
```

### Test Failures

```bash
# Run tests locally
pytest tests/ -v

# Run with more detail
pytest tests/ -vv --tb=long

# Run specific test file
pytest tests/common/test_utils.py -v
```

### Integration Test Failures

```bash
# Ensure services are running
docker-compose up -d redis rabbitmq

# Check service health
docker-compose ps

# Run integration tests
pytest tests/integration/ -v -m integration

# View service logs
docker-compose logs redis rabbitmq
```

### Docker Build Failures

```bash
# Test Docker build locally
docker build -f manager/Dockerfile -t test-manager .

# Check Dockerfile syntax
docker build --dry-run -f manager/Dockerfile .

# View build logs
docker build -f manager/Dockerfile -t test-manager . 2>&1 | tee build.log
```

### Coverage Below Threshold

```bash
# Check current coverage
pytest --cov=common --cov=manager --cov=downloader --cov=translator --cov=scanner \
  --cov-report=term-missing -m "not integration"

# Generate HTML report
pytest --cov=common --cov=manager --cov=downloader --cov=translator --cov=scanner \
  --cov-report=html -m "not integration"
open htmlcov/index.html
```

## Pipeline Status Badges

Add these to your README.md:

```markdown
[![CI](https://github.com/yairabramovitch/get-my-subtitle/actions/workflows/ci.yml/badge.svg)](https://github.com/yairabramovitch/get-my-subtitle/actions/workflows/ci.yml)
[![Lint](https://github.com/yairabramovitch/get-my-subtitle/actions/workflows/lint.yml/badge.svg)](https://github.com/yairabramovitch/get-my-subtitle/actions/workflows/lint.yml)
```

## Matrix Strategy

The CI pipeline uses a matrix strategy to test on multiple Python versions:

- **Python 3.11**: Primary version (production)
- **Python 3.12**: Latest stable version (compatibility testing)

This ensures the codebase works across different Python versions and catches version-specific issues early.

## Caching Strategy

The workflows implement smart caching:

1. **Pip Cache**: Automatically cached by `setup-python@v5` action
   - Keyed by `requirements.txt` hash
   - Significantly speeds up dependency installation

2. **Docker Layer Cache**: Uses GitHub Actions cache
   - Caches Docker layers between builds
   - Reduces build time for unchanged layers

## Best Practices

1. **Run checks locally** before pushing: `make check`
2. **Fix formatting** automatically: `make format`
3. **Review artifacts** if tests fail
4. **Check PR comments** from lint workflow for quick fixes
5. **Monitor coverage trends** to maintain quality
