"""Pytest fixtures for end-to-end tests with Docker Compose."""

import os
import subprocess
import time
from pathlib import Path
from typing import Generator, List

import httpx
import pytest
import pytest_asyncio

# Get project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent
DOCKER_COMPOSE_FILE = PROJECT_ROOT / "docker-compose.e2e.yml"
TEST_MEDIA_DIR = PROJECT_ROOT / "test-media"
MANAGER_API_URL = "http://localhost:8000"
SCANNER_API_URL = "http://localhost:8001"


def is_service_healthy(url: str, timeout: int = 5) -> bool:
    """Check if a service is healthy by making an HTTP request."""
    try:
        response = httpx.get(f"{url}/health", timeout=timeout)
        return response.status_code == 200
    except Exception:
        return False


def wait_for_service(
    url: str, max_attempts: int = 60, delay: float = 1.0
) -> bool:
    """Wait for a service to become healthy."""
    for attempt in range(max_attempts):
        if is_service_healthy(url):
            if attempt > 0:
                print(f"✅ Service {url} is healthy (attempt {attempt + 1})")
            return True
        if attempt % 10 == 0 and attempt > 0:
            print(f"⏳ Still waiting for {url}... (attempt {attempt + 1}/{max_attempts})")
        time.sleep(delay)
    return False


def run_docker_compose_command(command: List[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a docker-compose command."""
    cmd = ["docker-compose", "-f", str(DOCKER_COMPOSE_FILE)] + command
    result = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=check,
    )
    return result


@pytest.fixture(scope="session")
def docker_compose_up() -> Generator[None, None, None]:
    """Start Docker Compose services for e2e tests."""
    # Ensure test-media directory exists
    TEST_MEDIA_DIR.mkdir(exist_ok=True)

    # Start services
    print("\n🚀 Starting Docker Compose services for e2e tests...")
    # First, try to stop any existing services to avoid conflicts
    run_docker_compose_command(["down", "-v"], check=False)
    # Then start fresh
    run_docker_compose_command(["up", "-d", "--build"])

    try:
        # Wait for services to be healthy
        print("⏳ Waiting for services to be healthy...")
        
        services_ready = []
        services_ready.append(
            ("Manager API", wait_for_service(MANAGER_API_URL, max_attempts=60, delay=0.5))
        )
        services_ready.append(
            ("Scanner API", wait_for_service(SCANNER_API_URL, max_attempts=60, delay=0.5))
        )

        all_ready = all(ready for _, ready in services_ready)
        
        if not all_ready:
            failed_services = [name for name, ready in services_ready if not ready]
            print(f"❌ Services failed to start: {', '.join(failed_services)}")
            # Show logs for debugging
            run_docker_compose_command(["logs", "--tail=50"], check=False)
            pytest.fail(f"Services failed to start: {', '.join(failed_services)}")

        print("✅ All services are healthy")
        
        # Wait for RabbitMQ to be fully ready (health check passes but connections may still fail)
        print("⏳ Waiting for RabbitMQ to be fully ready...")
        time.sleep(10)  # Give RabbitMQ more time to be fully ready
        
        # Restart manager and scanner to ensure they connect to RabbitMQ now that it's ready
        print("⏳ Restarting manager and scanner to establish RabbitMQ connections...")
        run_docker_compose_command(["restart", "manager", "scanner"], check=False)
        time.sleep(10)  # Give services more time to connect after restart
        
        # Verify RabbitMQ connections are established by checking logs
        print("⏳ Verifying RabbitMQ connections...")
        max_retries = 15
        for attempt in range(max_retries):
            manager_logs = run_docker_compose_command(
                ["logs", "manager"], check=False
            )
            scanner_logs = run_docker_compose_command(
                ["logs", "scanner"], check=False
            )
            
            # Check for successful connections (not mock mode)
            manager_connected = (
                "Connected to RabbitMQ successfully" in manager_logs.stdout
                or ("Connected to RabbitMQ" in manager_logs.stdout and "mock mode" not in manager_logs.stdout.lower())
            )
            scanner_connected = (
                "All connections established" in scanner_logs.stdout
                and "Failed to connect to RabbitMQ" not in scanner_logs.stdout
            )
            
            if manager_connected and scanner_connected:
                print("✅ RabbitMQ connections established")
                break
            
            if attempt < max_retries - 1:
                time.sleep(2)
        else:
            print("⚠️ Warning: RabbitMQ connections may not be fully established")
            # Show logs for debugging
            print("\nManager logs (last 15 lines):")
            print(run_docker_compose_command(["logs", "--tail=15", "manager"], check=False).stdout)
            print("\nScanner logs (last 15 lines):")
            print(run_docker_compose_command(["logs", "--tail=15", "scanner"], check=False).stdout)

        yield

    finally:
        # Stop and remove services
        print("\n🛑 Stopping Docker Compose services...")
        run_docker_compose_command(["down", "-v"], check=False)
        print("✅ Services stopped")


@pytest_asyncio.fixture
async def http_client() -> Generator[httpx.AsyncClient, None, None]:
    """Create an HTTP client for API testing."""
    client = httpx.AsyncClient(
        base_url=MANAGER_API_URL,
        timeout=30.0,
        follow_redirects=True,
    )
    yield client
    await client.aclose()


@pytest_asyncio.fixture
async def scanner_http_client() -> Generator[httpx.AsyncClient, None, None]:
    """Create an HTTP client for scanner API testing."""
    client = httpx.AsyncClient(
        base_url=SCANNER_API_URL,
        timeout=30.0,
        follow_redirects=True,
    )
    yield client
    await client.aclose()


@pytest.fixture
def test_media_dir() -> Generator[Path, None, None]:
    """Provide test media directory and clean it up after tests."""
    # Ensure directory exists
    TEST_MEDIA_DIR.mkdir(exist_ok=True)
    
    yield TEST_MEDIA_DIR
    
    # Clean up test files (but keep directory)
    for file in TEST_MEDIA_DIR.glob("*.mp4"):
        try:
            file.unlink()
        except Exception:
            pass
    for file in TEST_MEDIA_DIR.glob("*.mkv"):
        try:
            file.unlink()
        except Exception:
            pass


@pytest.fixture(autouse=True)
def ensure_docker_compose_running(docker_compose_up: None) -> None:
    """Ensure Docker Compose is running before each test."""
    # This fixture depends on docker_compose_up, ensuring services are started
    pass

