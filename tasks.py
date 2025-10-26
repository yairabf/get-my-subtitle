"""
Invoke tasks for advanced development workflows.

Usage:
    invoke --list                    # List all available tasks
    invoke dev                       # Start hybrid development environment
    invoke build-service manager     # Build specific service
    invoke shell manager             # Open shell in manager container
    invoke health                    # Check health of all services
"""

import sys
import time
import webbrowser
from pathlib import Path

from invoke import task


# Color codes for terminal output
class Colors:
    BLUE = "\033[0;34m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[0;33m"
    RED = "\033[0;31m"
    NC = "\033[0m"


def print_info(message: str) -> None:
    """Print info message in blue"""
    print(f"{Colors.BLUE}ℹ {message}{Colors.NC}")


def print_success(message: str) -> None:
    """Print success message in green"""
    print(f"{Colors.GREEN}✓ {message}{Colors.NC}")


def print_warning(message: str) -> None:
    """Print warning message in yellow"""
    print(f"{Colors.YELLOW}⚠ {message}{Colors.NC}")


def print_error(message: str) -> None:
    """Print error message in red"""
    print(f"{Colors.RED}✗ {message}{Colors.NC}")


##############################################################################
# Advanced Docker Operations
##############################################################################


@task
def build_service(ctx, service):
    """
    Build specific service.

    Args:
        service: Service name (manager, downloader, translator)

    Example:
        invoke build-service manager
    """
    print_info(f"Building {service} service...")
    ctx.run(f"docker-compose build {service}")
    print_success(f"{service} built successfully!")


@task
def shell(ctx, service):
    """
    Open shell in running container.

    Args:
        service: Service name (manager, downloader, translator, redis, rabbitmq)

    Example:
        invoke shell manager
    """
    print_info(f"Opening shell in {service} container...")

    # Check if container is running
    result = ctx.run(f"docker-compose ps -q {service}", hide=True, warn=True)

    if not result.stdout.strip():
        print_error(f"{service} container is not running!")
        print_warning("Start it with: docker-compose up -d {service}")
        sys.exit(1)

    # Determine shell based on service
    shell_cmd = "/bin/sh" if service in ["redis", "rabbitmq"] else "/bin/bash"
    ctx.run(f"docker-compose exec {service} {shell_cmd}", pty=True)


@task
def rebuild(ctx, service):
    """
    Force rebuild specific service with no-cache.

    Args:
        service: Service name (manager, downloader, translator)

    Example:
        invoke rebuild manager
    """
    print_info(f"Force rebuilding {service} service (no cache)...")
    ctx.run(f"docker-compose build --no-cache {service}")
    print_success(f"{service} rebuilt successfully!")


##############################################################################
# Development Workflows
##############################################################################


@task
def dev(ctx):
    """
    Start hybrid development environment (infra + local services).

    This starts Redis and RabbitMQ in Docker, then provides instructions
    for running Python services locally with hot reload.
    """
    print_info("Starting hybrid development environment...")

    # Start infrastructure
    print_info("Starting Redis and RabbitMQ...")
    ctx.run("docker-compose up -d redis rabbitmq")

    # Wait for services to be healthy
    print_info("Waiting for services to be healthy...")
    wait_for_services(ctx, services=["redis", "rabbitmq"])

    print_success("Infrastructure is ready!")
    print("")
    print_warning("Now run these commands in separate terminals:")
    print("")
    print("  Terminal 1: make dev-manager      # API server with hot reload")
    print("  Terminal 2: make dev-downloader   # Downloader worker")
    print("  Terminal 3: make dev-translator   # Translator worker")
    print("")
    print_info("API will be available at: http://localhost:8000")
    print_info("RabbitMQ UI at: http://localhost:15672")


@task
def dev_full(ctx):
    """
    Start full Docker development environment.

    This starts all services in Docker containers.
    """
    print_info("Starting full Docker development environment...")
    ctx.run("docker-compose up -d")

    print_info("Waiting for services to be healthy...")
    wait_for_services(ctx)

    print_success("All services are ready!")
    print_info("API available at: http://localhost:8000")
    print_info("RabbitMQ UI at: http://localhost:15672")


##############################################################################
# Health Checks
##############################################################################


@task
def health(ctx):
    """
    Check health of all services.

    Displays the status of all running containers and their health checks.
    """
    print_info("Checking service health...")
    ctx.run("docker-compose ps")


@task
def wait_for_services(ctx, services=None, timeout=60):
    """
    Wait for services to be healthy.

    Args:
        services: List of service names to wait for (default: all)
        timeout: Maximum seconds to wait (default: 60)

    Example:
        invoke wait-for-services --services="redis,rabbitmq"
    """
    if services is None:
        services = ["redis", "rabbitmq", "manager"]
    elif isinstance(services, str):
        services = [s.strip() for s in services.split(",")]

    print_info(f"Waiting for services: {', '.join(services)}")

    start_time = time.time()

    for service in services:
        print_info(f"Waiting for {service}...")

        while True:
            if time.time() - start_time > timeout:
                print_error(f"Timeout waiting for {service} to be healthy!")
                sys.exit(1)

            result = ctx.run(
                f"docker-compose ps {service} | grep -E '(healthy|running)'",
                hide=True,
                warn=True,
            )

            if result.ok:
                print_success(f"{service} is ready!")
                break

            time.sleep(2)


##############################################################################
# Database Operations
##############################################################################


@task
def redis_cli(ctx):
    """
    Open Redis CLI.

    Connects to the Redis container and opens an interactive CLI session.
    """
    print_info("Opening Redis CLI...")

    result = ctx.run("docker-compose ps -q redis", hide=True, warn=True)

    if not result.stdout.strip():
        print_error("Redis container is not running!")
        print_warning("Start it with: docker-compose up -d redis")
        sys.exit(1)

    ctx.run("docker-compose exec redis redis-cli", pty=True)


@task
def redis_flush(ctx):
    """
    Flush Redis database.

    WARNING: This will delete all data in Redis!
    """
    print_warning("This will DELETE ALL DATA in Redis!")
    response = input("Are you sure? (yes/no): ")

    if response.lower() != "yes":
        print_info("Operation cancelled.")
        return

    print_info("Flushing Redis database...")
    ctx.run("docker-compose exec redis redis-cli FLUSHALL")
    print_success("Redis database flushed!")


@task
def rabbitmq_ui(ctx):
    """
    Open RabbitMQ management UI in browser.

    Opens http://localhost:15672 in your default browser.
    Default credentials: guest/guest
    """
    url = "http://localhost:15672"
    print_info(f"Opening RabbitMQ UI at {url}")
    print_info("Default credentials: guest/guest")

    webbrowser.open(url)


##############################################################################
# Testing & Quality
##############################################################################


@task
def test_e2e(ctx):
    """
    Run end-to-end tests.

    Runs the end-to-end test suite that tests the entire system.
    """
    print_info("Running end-to-end tests...")
    ctx.run("pytest test_end_to_end.py -v")


@task
def test_service(ctx, service):
    """
    Test specific service.

    Args:
        service: Service name (manager, downloader, translator, common)

    Example:
        invoke test-service manager
    """
    print_info(f"Running tests for {service}...")

    if service == "common":
        ctx.run("pytest tests/common/ -v")
    else:
        ctx.run(f"pytest tests/{service}/ -v")


@task
def coverage_html(ctx):
    """
    Generate HTML coverage report and open in browser.

    Runs tests with coverage and opens the HTML report.
    """
    print_info("Generating coverage report...")
    ctx.run(
        "pytest --cov=common --cov=manager --cov=downloader --cov=translator "
        "--cov-report=html --cov-report=term-missing"
    )

    report_path = Path("htmlcov/index.html").absolute()

    if report_path.exists():
        print_success("Coverage report generated!")
        print_info(f"Opening {report_path}")
        webbrowser.open(f"file://{report_path}")
    else:
        print_error("Coverage report not found!")


##############################################################################
# Utility Tasks
##############################################################################


@task
def logs_service(ctx, service, follow=True):
    """
    View logs for specific service.

    Args:
        service: Service name
        follow: Follow log output (default: True)

    Example:
        invoke logs-service manager
        invoke logs-service manager --no-follow
    """
    cmd = f"docker-compose logs {'-f' if follow else ''} {service}"
    ctx.run(cmd)


@task
def ps(ctx):
    """Show status of all services."""
    ctx.run("docker-compose ps")


@task
def top(ctx):
    """Display running processes in containers."""
    print_info("Container processes:")
    ctx.run("docker-compose top")
