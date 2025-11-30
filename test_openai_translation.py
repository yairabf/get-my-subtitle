#!/usr/bin/env python3
"""Test script for OpenAI translation API."""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from openai import AsyncOpenAI
from common.config import settings


async def test_translation():
    """Test OpenAI translation API with a simple example."""
    
    if not settings.openai_api_key:
        print("❌ OPENAI_API_KEY not set in environment")
        return
    
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    
    # Test with a simple subtitle example
    test_texts = [
        "Hello, how are you?",
        "<i>like a lord or a king</i>",
        "This is a test subtitle.",
    ]
    
    source_language = "English"
    target_language = "Hebrew"
    
    # Build prompt similar to our translation service
    numbered_texts = []
    for i, text in enumerate(test_texts, 1):
        numbered_texts.append(f"[{i}]\n{text}")
    
    prompt = (
        f"Translate the following {len(test_texts)} subtitle segments "
        f"from {source_language} to {target_language}.\n\n"
        f"IMPORTANT: Preserve all HTML tags (like <i>, <b>, <u>, etc.) exactly as they appear. "
        f"Only translate the text content inside the tags, not the tags themselves.\n\n"
        f"For example:\n"
        f"Source: <i>like a lord or a king</i>\n"
        f"Target: <i>[translated text in {target_language}]</i>\n\n"
        f"Return ONLY the translations, numbered the same way, "
        f"with no additional commentary.\n\n"
        f"Format your response exactly like this:\n"
        f"[1]\nTranslated text with preserved HTML tags\n\n"
        f"[2]\nTranslated text with preserved HTML tags\n\n"
        f"etc.\n\n"
        f"Subtitles to translate:\n\n" + "\n\n".join(numbered_texts)
    )
    
    print("=" * 60)
    print("Testing OpenAI Translation API")
    print("=" * 60)
    print(f"Model: {settings.openai_model}")
    print(f"Source: {source_language}")
    print(f"Target: {target_language}")
    print(f"Number of segments: {len(test_texts)}")
    print(f"Max tokens: {settings.openai_max_tokens}")
    print("=" * 60)
    print("\nSending request...\n")
    
    try:
        # Build API parameters
        api_params = {
            "model": settings.openai_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        f"You are a professional subtitle translator. "
                        f"Translate subtitles from {source_language} to {target_language}. "
                        f"Maintain the same tone, style, and timing suitability. "
                        f"Keep translations concise for subtitle display. "
                        f"Preserve all formatting including line breaks and HTML tags like <i>, <b>, <u>, etc. "
                        f"Translate the content inside HTML tags but keep the tags themselves unchanged. "
                        f"For example, if you see '<i>like a lord</i>', translate it to '<i>[translated text]</i>' "
                        f"where [translated text] is the translation in {target_language}."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "max_completion_tokens": settings.openai_max_tokens,  # Required for gpt-5-nano model
            "timeout": 60.0,
        }
        
        # Only include temperature if model supports it
        if "nano" not in settings.openai_model.lower():
            api_params["temperature"] = settings.openai_temperature
        
        print(f"API Parameters:")
        print(f"  Model: {api_params['model']}")
        print(f"  Max completion tokens: {api_params['max_completion_tokens']}")
        print(f"  Temperature: {api_params.get('temperature', 'default (1.0 for nano)')}")
        print(f"  Messages: {len(api_params['messages'])} messages")
        print()
        
        # Make the API call
        response = await client.chat.completions.create(**api_params)
        
        # Check response
        print("=" * 60)
        print("Response received!")
        print("=" * 60)
        
        if not response.choices or len(response.choices) == 0:
            print("❌ ERROR: No choices in response")
            return
        
        choice = response.choices[0]
        message_content = choice.message.content
        
        print(f"Finish reason: {choice.finish_reason}")
        print(f"Response length: {len(message_content) if message_content else 0} characters")
        
        if hasattr(response, 'usage') and response.usage:
            print(f"\nUsage:")
            print(f"  Prompt tokens: {response.usage.prompt_tokens}")
            print(f"  Completion tokens: {response.usage.completion_tokens}")
            print(f"  Total tokens: {response.usage.total_tokens}")
        
        if not message_content:
            print("\n❌ ERROR: Empty response content!")
            print(f"Finish reason: {choice.finish_reason}")
            if choice.finish_reason == "length":
                print("⚠️  Response was truncated - increase max_tokens")
            return
        
        print(f"\n✅ Response content ({len(message_content)} chars):")
        print("-" * 60)
        print(message_content)
        print("-" * 60)
        
        # Try to parse the response
        print("\nParsing response...")
        translations = []
        segments = message_content.split("[")
        
        for segment in segments:
            if not segment.strip():
                continue
            parts = segment.split("]", 1)
            if len(parts) == 2:
                try:
                    int(parts[0].strip())
                    text = parts[1].strip()
                    translations.append(text)
                except ValueError:
                    continue
        
        print(f"✅ Parsed {len(translations)} translations:")
        for i, trans in enumerate(translations, 1):
            print(f"  [{i}] {trans}")
        
        if len(translations) != len(test_texts):
            print(f"\n⚠️  WARNING: Expected {len(test_texts)} translations, got {len(translations)}")
        else:
            print(f"\n✅ SUCCESS: All {len(test_texts)} translations received!")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_translation())
