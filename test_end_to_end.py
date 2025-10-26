#!/usr/bin/env python3
"""Test script to verify end-to-end message flow."""

import asyncio
import json
import time
from typing import Any, Dict

import aio_pika
import requests


async def test_message_flow() -> None:
    """Test the complete message flow from API to worker."""
    print("🧪 Testing End-to-End Message Flow")
    print("=" * 50)

    # Test 1: Send a test message via API
    print("1️⃣ Sending test message via API...")
    response = requests.post(
        "http://localhost:8000/test/queue-message",
        headers={"accept": "application/json"},
    )

    if response.status_code == 200:
        data = response.json()
        print(f"✅ API Response: {data['message']}")
        print(f"   Request ID: {data['request_id']}")
    else:
        print(f"❌ API Error: {response.status_code} - {response.text}")
        return

    # Test 2: Send a real subtitle request
    print("\n2️⃣ Sending real subtitle request...")
    subtitle_request = {
        "video_url": "https://example.com/test-video.mp4",
        "video_title": "Test Video for E2E",
        "language": "en",
        "target_language": "es",
        "preferred_sources": ["opensubtitles"],
    }

    response = requests.post(
        "http://localhost:8000/subtitles/request",
        headers={"accept": "application/json", "Content-Type": "application/json"},
        json=subtitle_request,
    )

    if response.status_code == 201:
        data = response.json()
        print(f"✅ Subtitle Request Created: {data['id']}")
        print(f"   Status: {data['status']}")
    else:
        print(f"❌ API Error: {response.status_code} - {response.text}")
        return

    # Test 3: Check queue status
    print("\n3️⃣ Checking queue status...")
    response = requests.get(
        "http://localhost:8000/queue/status", headers={"accept": "application/json"}
    )

    if response.status_code == 200:
        data = response.json()
        print(f"✅ Queue Status:")
        print(f"   Download Queue: {data['download_queue_size']} messages")
        print(f"   Translation Queue: {data['translation_queue_size']} messages")
    else:
        print(f"❌ Queue Status Error: {response.status_code} - {response.text}")

    print("\n🎉 End-to-end test completed!")
    print("Check the debug worker output to see if messages were consumed.")


if __name__ == "__main__":
    asyncio.run(test_message_flow())
