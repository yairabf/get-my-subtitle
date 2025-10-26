# Getting Started with Development Automation

Welcome! This guide will help you get up and running with the new development automation tools.

## Quick Start

### 1. Install Dependencies

If you already have the venv set up:
```bash
make install
```

Or for a complete fresh setup:
```bash
make setup
```

This will:
- Create a virtual environment (if needed)
- Install all dependencies including new tools (pytest-cov, invoke)
- Create `.env` from template

### 2. Verify Installation

```bash
# Check Makefile commands
make help

# Check Invoke tasks
invoke --list
```

## Your First Commands

### Start Development Environment

**Option A: Hybrid Mode (Recommended for Development)**
```bash
# Terminal 1: Start infrastructure
make up-infra

# Terminal 2: Start manager with hot reload
make dev-manager

# Terminal 3: Start downloader worker
make dev-downloader

# Terminal 4: Start translator worker
make dev-translator
```

**Option B: Full Docker Mode**
```bash
make up
make logs
```

### Run Tests

```bash
# All tests
make test

# With coverage report
make test-cov

# Open coverage report in browser
invoke coverage-html
```

### Format Code

```bash
# Auto-fix formatting
make format

# Check formatting without changes
make lint

# Run complete check (lint + tests)
make check
```

## Common Tasks

### Building & Running

```bash
make build              # Build Docker images
make up                 # Start all services
make down               # Stop all services
make restart            # Restart services
make logs               # Follow logs
```

### Testing

```bash
make test               # All tests
make test-unit          # Unit tests only
make test-integration   # Integration tests
make test-cov           # With coverage
make test-watch         # Watch mode
```

### Code Quality

```bash
make lint               # Check formatting
make format             # Fix formatting
make check              # Lint + tests
```

### Cleanup

```bash
make clean              # Clean Python cache
make clean-docker       # Clean Docker resources
make clean-all          # Complete cleanup
```

## Advanced Operations (Invoke)

### Docker Management

```bash
invoke build-service manager      # Build specific service
invoke shell manager              # Open shell in container
invoke rebuild manager            # Force rebuild
```

### Development

```bash
invoke dev              # Start hybrid development
invoke dev-full         # Start full Docker environment
```

### Health & Monitoring

```bash
invoke health           # Check service status
invoke wait-for-services  # Wait for healthy state
invoke ps               # Show container status
invoke top              # Show container processes
```

### Database Operations

```bash
invoke redis-cli        # Interactive Redis CLI
invoke redis-flush      # Clear Redis (with confirmation)
invoke rabbitmq-ui      # Open management UI
```

### Testing & Quality

```bash
invoke test-e2e         # End-to-end tests
invoke test-service manager  # Test specific service
invoke coverage-html    # Generate & open coverage report
```

### Logs

```bash
invoke logs-service manager         # Follow manager logs
invoke logs-service manager --no-follow  # Historical logs
```

## Workflow Examples

### Daily Development Workflow

```bash
# Morning: Start fresh
make clean
make up-infra
make dev-manager        # In separate terminals
make dev-downloader
make dev-translator

# During development: Run tests
make test-cov

# Before commit: Format and check
make format
make check

# End of day: Clean up
make down
```

### Debugging a Service

```bash
# Check service health
invoke health

# View logs
invoke logs-service manager --no-follow

# Access container shell
invoke shell manager

# Check Redis data
invoke redis-cli

# View RabbitMQ queues
invoke rabbitmq-ui
```

### Working on Specific Module

```bash
# Test specific service
invoke test-service common

# Build specific service
invoke build-service manager

# Rebuild from scratch
invoke rebuild manager

# View specific service logs
invoke logs-service manager
```

### Preparing for Deployment

```bash
# Complete check
make check

# Test coverage
make test-cov

# Build all images
make build

# Test full Docker mode
make up
invoke health
make down
```

## Tips & Tricks

### 1. Use Tab Completion
Both make and invoke support tab completion for commands (if your shell is configured).

### 2. Combine Commands
```bash
make clean && make test-cov
```

### 3. Watch Mode for TDD
```bash
make test-watch  # Runs tests on file changes
```

### 4. Quick Service Restart
```bash
docker-compose restart manager
# or
make restart
```

### 5. Check What Changed
```bash
git status
make format      # Auto-format new code
make test        # Verify tests pass
```

## Troubleshooting

### "Command not found" Errors

If you see errors like `black: command not found`:
```bash
make install     # Reinstall dependencies
```

### Tests Failing

```bash
make clean       # Clean cache
make install     # Ensure deps are current
make test-cov    # Run with coverage to see what's failing
```

### Docker Issues

```bash
make clean-docker  # Clean Docker resources
make build         # Rebuild images
make up            # Start fresh
```

### Virtual Environment Issues

```bash
rm -rf venv
make setup         # Recreate from scratch
```

## Configuration Files

### Makefile
- Location: `/Makefile`
- Purpose: Simple, fast commands for common operations
- When to use: Daily development tasks

### tasks.py
- Location: `/tasks.py`
- Purpose: Advanced workflows and complex operations
- When to use: Debugging, service-specific operations, automation

### pytest.ini
- Location: `/pytest.ini`
- Purpose: Test configuration
- Coverage reporting enabled by default

### .coveragerc
- Location: `/.coveragerc`
- Purpose: Coverage configuration
- Excludes venv, tests, cache directories

## What's Next?

1. **Explore the help**:
   ```bash
   make help
   invoke --list
   ```

2. **Try the workflows**:
   - Start with `make setup`
   - Try `make up-infra` + `make dev-manager`
   - Run `make test-cov`

3. **Read the full documentation**:
   - See `README.md` for complete reference
   - See `DEV_AUTOMATION_SUMMARY.md` for implementation details

4. **Customize**:
   - Add your own Makefile targets
   - Create custom Invoke tasks
   - Share improvements with the team

## Need Help?

- Run `make help` for Makefile commands
- Run `invoke --list` for Invoke tasks
- Check `README.md` for detailed documentation
- View `tasks.py` for task implementations with docstrings

Happy coding! 🚀

