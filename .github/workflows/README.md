# GitHub Actions Workflows

This directory contains the CI/CD pipeline for the Get My Subtitle project.

## CI Pipeline (`ci.yml`)

A streamlined, single-file CI pipeline that runs on every push and pull request.

### Pipeline Stages

#### 1. **Code Quality (Linting)**
- **Black**: Checks code formatting
- **isort**: Validates import sorting
- Runs on: Python 3.11
- Fast execution: ~15-20 seconds

#### 2. **Unit Tests**
- Runs all unit tests with coverage
- Tests: `common/`, `manager/`, `downloader/`, `translator/`
- Coverage requirement: 60% minimum
- Generates coverage report artifact
- Runs on: Python 3.11
- Execution time: ~30-60 seconds

#### 3. **Integration Tests**
- Tests with real Redis and RabbitMQ services
- Validates end-to-end message queue flows
- Services: Redis 7, RabbitMQ 3
- Runs on: Python 3.11
- Execution time: ~45-90 seconds

#### 4. **Security Checks**
- **Safety**: Scans dependencies for known vulnerabilities
- **Bandit**: Static analysis for security issues in code
- Both checks are informational (won't fail CI)
- Generates security report artifacts
- Execution time: ~20-30 seconds

### Total Pipeline Time
Expected duration: **2-3 minutes** for all checks to complete.

### Workflow Triggers

```yaml
on:
  push:
    branches: [ main, develop, feat/* ]
  pull_request:
    branches: [ main, develop ]
```

### Artifacts

The pipeline generates and uploads the following artifacts:

1. **coverage-report** (7 days retention)
   - Coverage XML report for analysis

2. **security-reports** (14 days retention)
   - Bandit JSON security scan results

### Running Checks Locally

Before pushing, run these commands locally to catch issues early:

```bash
# Linting
black .
isort .

# Unit tests with coverage
pytest tests/common tests/downloader tests/manager tests/translator \
  --cov=common --cov=manager --cov=downloader --cov=translator \
  --cov-report=term-missing

# Integration tests (requires Docker)
docker-compose up -d redis rabbitmq
pytest tests/integration/

# Security checks
pip install safety bandit
safety check
bandit -r common/ manager/ downloader/ translator/
```

## Design Philosophy

The CI pipeline follows these principles:

1. **Simplicity**: Single workflow file, easy to understand and maintain
2. **Speed**: Runs only essential checks, ~2-3 minutes total
3. **Focus**: Tests on single Python version (3.11) - the production version
4. **Clarity**: Four clear stages with specific purposes
5. **Actionable**: Security checks are informational, don't block merges

## Troubleshooting

### Linting Failures
```bash
# Fix formatting issues
black .
isort .
git add -A
git commit -m "Fix formatting"
```

### Test Failures
```bash
# Run tests locally
pytest tests/ -v

# Run with more detail
pytest tests/ -vv --tb=long
```

### Integration Test Failures
```bash
# Ensure services are running
docker-compose up -d redis rabbitmq

# Check service health
docker-compose ps

# Run integration tests
pytest tests/integration/ -v
```

## Pipeline Status Badge

Add this to your README.md:

```markdown
[![CI Pipeline](https://github.com/yairabf/get-my-subtitle/actions/workflows/ci.yml/badge.svg)](https://github.com/yairabf/get-my-subtitle/actions/workflows/ci.yml)
```
