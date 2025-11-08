#!/usr/bin/env python3
"""
End-to-end test script for translation service.

This script:
1. Checks if Docker is running
2. Checks if RabbitMQ and Redis are running in Docker
3. Creates a fake English SRT subtitle file
4. Calls the manager API endpoint /subtitles/translate
5. Monitors the job status and checks the output
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from uuid import UUID

import httpx


def check_docker_running():
    """Check if Docker is running."""
    print("🔍 Step 1: Checking if Docker is running...")
    try:
        result = subprocess.run(
            ["docker", "info"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            print("✅ Docker is running")
            return True
        else:
            print("❌ Docker is not running")
            print(f"Error: {result.stderr}")
            return False
    except FileNotFoundError:
        print("❌ Docker is not installed or not in PATH")
        return False
    except subprocess.TimeoutExpired:
        print("❌ Docker check timed out")
        return False
    except Exception as e:
        print(f"❌ Error checking Docker: {e}")
        return False


def check_containers_running():
    """Check if RabbitMQ and Redis containers are running."""
    print("\n🔍 Step 2: Checking if RabbitMQ and Redis are running...")
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            print("❌ Failed to check Docker containers")
            return False

        running_containers = result.stdout.strip().split("\n")
        running_containers = [c for c in running_containers if c]

        rabbitmq_running = any("rabbitmq" in c.lower() for c in running_containers)
        redis_running = any("redis" in c.lower() for c in running_containers)

        if rabbitmq_running:
            print("✅ RabbitMQ container is running")
        else:
            print("❌ RabbitMQ container is not running")
            print("   Run: docker-compose up -d rabbitmq")

        if redis_running:
            print("✅ Redis container is running")
        else:
            print("❌ Redis container is not running")
            print("   Run: docker-compose up -d redis")

        if rabbitmq_running and redis_running:
            return True
        else:
            print("\n💡 To start services: docker-compose up -d rabbitmq redis")
            return False

    except Exception as e:
        print(f"❌ Error checking containers: {e}")
        return False


def create_test_srt_file():
    """Create a fake English SRT subtitle file."""
    print("\n🔍 Step 3: Creating test English SRT file...")

    # Create storage directory if it doesn't exist
    storage_dir = Path("storage/subtitles")
    storage_dir.mkdir(parents=True, exist_ok=True)

    # Create test SRT content
    srt_content = """1
00:00:01,000 --> 00:00:04,000
Hello and welcome to this video.

2
00:00:04,500 --> 00:00:08,000
Today we're going to learn something new.

3
00:00:08,500 --> 00:00:12,000
Let's get started with our first lesson.

4
00:00:12,500 --> 00:00:16,000
This is a test subtitle file for translation.

5
00:00:16,500 --> 00:00:20,000
Thank you for watching!
"""

    srt_file = storage_dir / "test_english.srt"
    srt_file.write_text(srt_content, encoding="utf-8")

    # Return Docker container path (translator runs in Docker)
    container_path = f"/app/storage/subtitles/{srt_file.name}"

    print(f"✅ Created test SRT file: {srt_file.absolute()}")
    print(f"   File size: {srt_file.stat().st_size} bytes")
    print(f"   Container path: {container_path}")
    return container_path


def check_api_health(base_url: str = "http://localhost:8000"):
    """Check if the API is healthy."""
    print(f"\n🔍 Checking API health at {base_url}...")
    try:
        response = httpx.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            print("✅ API is healthy")
            return True
        else:
            print(f"❌ API health check failed: {response.status_code}")
            return False
    except httpx.ConnectError:
        print(f"❌ Cannot connect to API at {base_url}")
        print("   Make sure the manager service is running:")
        print("   docker-compose up -d manager")
        return False
    except Exception as e:
        print(f"❌ Error checking API health: {e}")
        return False


def translate_subtitle(
    subtitle_path: str,
    source_language: str = "en",
    target_language: str = "heb",  # Hebrew
    base_url: str = "http://localhost:8000",
):
    """Call the translation API endpoint."""
    print(f"\n🔍 Step 4: Calling translation API endpoint...")
    print(f"   Endpoint: {base_url}/subtitles/translate")
    print(f"   Subtitle path: {subtitle_path}")
    print(f"   Source language: {source_language}")
    print(f"   Target language: {target_language}")

    request_data = {
        "subtitle_path": subtitle_path,
        "source_language": source_language,
        "target_language": target_language,
        "video_title": "Test Video - Translation",
    }

    try:
        response = httpx.post(
            f"{base_url}/subtitles/translate",
            json=request_data,
            timeout=10,
        )

        if response.status_code == 200:
            data = response.json()
            print("✅ Translation request created successfully")
            print(f"   Job ID: {data.get('id')}")
            print(f"   Status: {data.get('status')}")
            return data
        else:
            print(f"❌ Translation request failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return None

    except Exception as e:
        print(f"❌ Error calling translation API: {e}")
        return None


def check_job_status(job_id: str, base_url: str = "http://localhost:8000"):
    """Check the status of a translation job."""
    print(f"\n🔍 Step 5: Checking job status...")
    print(f"   Job ID: {job_id}")

    max_attempts = 60  # Wait up to 5 minutes
    attempt = 0

    while attempt < max_attempts:
        try:
            response = httpx.get(
                f"{base_url}/subtitles/status/{job_id}",
                timeout=5,
            )

            if response.status_code == 200:
                data = response.json()
                status = data.get("status", "unknown")
                print(f"   Attempt {attempt + 1}/{max_attempts}: Status = {status}")

                if status == "completed":
                    print("✅ Translation completed!")
                    print(f"   Translated path: {data.get('translated_path', 'N/A')}")
                    return data
                elif status == "done":
                    print("✅ Translation completed!")
                    print(f"   Translated path: {data.get('translated_path', 'N/A')}")
                    return data
                elif status == "failed":
                    print("❌ Translation failed!")
                    print(f"   Error: {data.get('error_message', 'Unknown error')}")
                    return data
                elif status in ["pending", "translate_in_progress", "translate_queued"]:
                    # Still processing, wait and retry
                    time.sleep(5)
                    attempt += 1
                    continue
                else:
                    print(f"   Unknown status: {status}")
                    time.sleep(5)
                    attempt += 1
                    continue
            else:
                print(f"   Failed to get status: {response.status_code}")
                time.sleep(5)
                attempt += 1
                continue

        except Exception as e:
            print(f"   Error checking status: {e}")
            time.sleep(5)
            attempt += 1
            continue

    print("⏱️  Timeout waiting for translation to complete")
    return None


def check_output_file(subtitle_path: str, target_language: str):
    """Check if the translated output file exists."""
    print(f"\n🔍 Step 6: Checking output file...")

    # Expected output file name: original_path with target language suffix
    # Handle both container paths (/app/storage/...) and host paths
    if subtitle_path.startswith("/app/"):
        # Container path - check in host storage directory
        container_path = Path(subtitle_path)
        host_storage = Path("storage/subtitles")
        output_path = (
            host_storage
            / f"{container_path.stem}.{target_language}{container_path.suffix}"
        )
    else:
        # Host path
        original_path = Path(subtitle_path)
        output_path = (
            original_path.parent
            / f"{original_path.stem}.{target_language}{original_path.suffix}"
        )

    if output_path.exists():
        print(f"✅ Output file found: {output_path}")
        print(f"   File size: {output_path.stat().st_size} bytes")

        # Read and display first few lines
        content = output_path.read_text(encoding="utf-8")
        lines = content.split("\n")[:20]  # First 20 lines
        print("\n   First 20 lines of translated file:")
        print("   " + "-" * 60)
        for i, line in enumerate(lines, 1):
            print(f"   {i:2d}: {line}")
        print("   " + "-" * 60)

        return True
    else:
        print(f"❌ Output file not found: {output_path}")
        return False


def main():
    """Main test function."""
    print("=" * 70)
    print("🧪 End-to-End Translation Service Test")
    print("=" * 70)

    # Step 1: Check Docker
    if not check_docker_running():
        print("\n❌ Test failed: Docker is not running")
        sys.exit(1)

    # Step 2: Check containers
    if not check_containers_running():
        print("\n❌ Test failed: Required containers are not running")
        sys.exit(1)

    # Step 3: Create test SRT file
    subtitle_path = create_test_srt_file()

    # Check API health
    if not check_api_health():
        print("\n❌ Test failed: API is not healthy")
        sys.exit(1)

    # Step 4: Call translation API
    job_data = translate_subtitle(
        subtitle_path=subtitle_path,
        source_language="en",
        target_language="heb",  # Hebrew
    )

    if not job_data:
        print("\n❌ Test failed: Translation request failed")
        sys.exit(1)

    job_id = job_data.get("id")
    if not job_id:
        print("\n❌ Test failed: No job ID returned")
        sys.exit(1)

    # Step 5: Check job status
    final_status = check_job_status(job_id)

    if not final_status:
        print("\n⏱️  Test incomplete: Could not get final status")
        sys.exit(1)

    # Step 6: Check output file
    target_language = job_data.get("target_language", "heb")
    output_exists = check_output_file(subtitle_path, target_language)

    # Summary
    print("\n" + "=" * 70)
    print("📊 Test Summary")
    print("=" * 70)
    print(f"✅ Docker: Running")
    print(f"✅ Containers: RabbitMQ and Redis running")
    print(f"✅ Test file: Created at {subtitle_path}")
    print(f"✅ API call: Translation request created")
    print(f"✅ Job status: {final_status.get('status', 'unknown')}")
    if output_exists:
        print(f"✅ Output file: Found")
    else:
        print(f"❌ Output file: Not found")
    print("=" * 70)

    if final_status.get("status") == "completed" and output_exists:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    elif final_status.get("status") == "done" and output_exists:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print("\n⚠️  Some checks failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
