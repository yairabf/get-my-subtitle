# CI/CD Scripts

This directory contains scripts for continuous integration and deployment.

## Available Scripts

### `ci_code_quality.sh` - Code Quality Checks Only

Runs code quality checks without executing any tests. Perfect for fast feedback on code style and linting.

**What it does:**
1. ✅ **Code Formatting** (Black) - Ensures consistent code style
2. ✅ **Import Sorting** (isort) - Checks import organization
3. ✅ **Linting** (Flake8) - Detects code quality issues
4. ⚠️  **Type Checking** (MyPy) - Optional static type analysis
5. ⚠️  **Security Scanning** (Bandit) - Optional security vulnerability detection

### `ci_run_tests.sh` - Test Execution

Runs all tests (unit and integration) with optional coverage reporting.

**What it does:**
1. ✅ **Unit Tests** (pytest) - Runs all unit tests
2. ✅ **Integration Tests** (pytest + Docker) - End-to-end testing
3. ✅ **Code Coverage** (pytest-cov) - Optional coverage reporting

**Usage:**

#### Code Quality Script

```bash
# Run code quality checks
./scripts/ci_code_quality.sh

# Verbose output
./scripts/ci_code_quality.sh --verbose

# Stop on first failure
./scripts/ci_code_quality.sh --fail-fast
```

#### Test Runner Script

```bash
# Run all tests (unit + integration)
./scripts/ci_run_tests.sh

# Skip integration tests
./scripts/ci_run_tests.sh --skip-integration

# With coverage report
./scripts/ci_run_tests.sh --with-coverage

# Verbose output
./scripts/ci_run_tests.sh --verbose

# Combine flags
./scripts/ci_run_tests.sh --skip-integration --with-coverage --verbose
```

**Via Makefile:**

```bash
# Code quality checks only
make ci-quality

# Run all tests (unit + integration) with coverage
make ci-tests

# Run unit tests only with coverage
make ci-tests-unit
```

**Exit Codes:**

`ci_code_quality.sh`:
- `0` - All checks passed
- `1` - Linting/formatting errors
- `2` - Type checking errors (non-blocking)

`ci_run_tests.sh`:
- `0` - All tests passed
- `3` - Unit tests failed
- `4` - Integration tests failed
- `5` - Coverage below threshold

**Environment Variables:**

The script respects these environment variables:

```bash
# Set coverage threshold (default: 80%)
export COVERAGE_THRESHOLD=85

# Skip specific checks
export SKIP_FORMATTING=true
export SKIP_LINTING=true
export SKIP_TYPE_CHECK=true
```

**Requirements:**

The script will auto-install missing tools, but you can pre-install them:

```bash
pip install black isort flake8 pytest pytest-cov pytest-asyncio
pip install mypy bandit  # Optional
```

**Integration with CI Systems:**

#### GitHub Actions

```yaml
name: CI Pipeline

on: [push, pull_request]

jobs:
  code-quality:
    name: Code Quality Checks
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      
      - name: Run code quality checks
        run: |
          chmod +x scripts/ci_code_quality.sh
          ./scripts/ci_code_quality.sh --verbose
  
  unit-tests:
    name: Unit Tests
    runs-on: ubuntu-latest
    needs: code-quality
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      
      - name: Run unit tests with coverage
        run: |
          chmod +x scripts/ci_run_tests.sh
          ./scripts/ci_run_tests.sh --skip-integration --with-coverage --verbose
      
      - name: Upload coverage reports
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
  
  integration-tests:
    name: Integration Tests
    runs-on: ubuntu-latest
    needs: unit-tests
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      
      - name: Run integration tests
        run: |
          chmod +x scripts/ci_run_tests.sh
          ./scripts/ci_run_tests.sh --verbose
```

#### GitLab CI

```yaml
code_quality:
  stage: test
  image: python:3.11
  services:
    - docker:dind
  script:
    - pip install -r requirements.txt
    - chmod +x scripts/ci_code_quality.sh
    - ./scripts/ci_code_quality.sh --verbose
  artifacts:
    reports:
      coverage_report:
        coverage_format: cobertura
        path: coverage.xml
```

#### CircleCI

```yaml
version: 2.1

jobs:
  code-quality:
    docker:
      - image: cimg/python:3.11
    steps:
      - checkout
      - run:
          name: Install dependencies
          command: pip install -r requirements.txt
      - run:
          name: Run code quality checks
          command: |
            chmod +x scripts/ci_code_quality.sh
            ./scripts/ci_code_quality.sh --verbose
      - store_artifacts:
          path: htmlcov
      - store_test_results:
          path: coverage.xml
```

#### Jenkins

```groovy
pipeline {
    agent any
    
    stages {
        stage('Setup') {
            steps {
                sh 'python -m venv venv'
                sh '. venv/bin/activate && pip install -r requirements.txt'
            }
        }
        
        stage('Code Quality') {
            steps {
                sh '''
                    . venv/bin/activate
                    chmod +x scripts/ci_code_quality.sh
                    ./scripts/ci_code_quality.sh --verbose
                '''
            }
        }
    }
    
    post {
        always {
            publishHTML([
                reportDir: 'htmlcov',
                reportFiles: 'index.html',
                reportName: 'Coverage Report'
            ])
            junit 'coverage.xml'
        }
    }
}
```

## Script Customization

### Adding Custom Checks

You can extend the `ci_code_quality.sh` script with custom checks:

```bash
# Add to the script after the existing checks:

############################################################################
# 10. Custom Security Check
############################################################################

print_header "10. Running Custom Security Scan"

if python scripts/custom_security_check.py; then
    print_success "Custom security check passed"
else
    print_error "Custom security check failed"
    EXIT_CODE=6
fi
```

### Configuring Code Quality Tools

#### Black (`.black`)
No configuration needed - uses sensible defaults.

#### isort (`.isort.cfg` or `pyproject.toml`)
```toml
[tool.isort]
profile = "black"
line_length = 88
```

#### Flake8 (`.flake8` or `setup.cfg`)
```ini
[flake8]
max-line-length = 120
extend-ignore = E203, W503
exclude = 
    .git,
    __pycache__,
    venv,
    .venv
```

#### MyPy (`mypy.ini` or `pyproject.toml`)
```ini
[mypy]
python_version = 3.11
ignore_missing_imports = True
strict_optional = False
```

## Troubleshooting

### Script Fails with "Permission Denied"

```bash
chmod +x scripts/ci_code_quality.sh
```

### Integration Tests Timeout

Increase the wait time in the script:
```bash
# Change from:
sleep 15

# To:
sleep 30
```

### Docker Not Found in CI

Ensure Docker is installed and the Docker daemon is running. For CI systems, you may need to use Docker-in-Docker or enable Docker in the executor.

### Coverage Calculation Fails

Ensure `coverage.xml` is generated:
```bash
pytest --cov=. --cov-report=xml
```

## Best Practices

1. **Run locally before pushing**: Use `make ci-fast` to catch issues early
2. **Fix formatting automatically**: Use `make format` to auto-fix Black and isort issues
3. **Review coverage reports**: Check `htmlcov/index.html` for detailed coverage analysis
4. **Keep tests fast**: Unit tests should complete in < 30 seconds
5. **Use Docker for integration tests**: Ensures consistent environment
6. **Monitor CI execution time**: Optimize slow tests or split into parallel jobs

## Performance Optimization

### Parallel Test Execution

Install `pytest-xdist`:
```bash
pip install pytest-xdist
```

Modify the script to use parallel execution:
```bash
pytest -n auto tests/
```

### Caching Dependencies

In GitHub Actions:
```yaml
- name: Cache pip packages
  uses: actions/cache@v3
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('requirements.txt') }}
```

### Docker Layer Caching

In GitLab CI:
```yaml
variables:
  DOCKER_DRIVER: overlay2
  DOCKER_TLS_CERTDIR: ""
  
cache:
  paths:
    - .docker
```

## Contributing

When adding new checks to the CI script:

1. Add a new section with clear header
2. Check if tool is installed, install if missing
3. Use `run_cmd` function for consistent error handling
4. Update the summary section
5. Document the new check in this README
6. Test locally with all flags (`--verbose`, `--fail-fast`, `--skip-integration`)

## Support

For issues or questions:
- Check the script output for detailed error messages
- Review the generated reports (coverage.xml, htmlcov/, bandit-report.json)
- See logs from integration tests: `make test-integration-logs`

