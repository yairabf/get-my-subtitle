"""Utilities for handling GPT API responses."""

import json
import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)


class GPTJSONParsingError(Exception):
    """
    Exception for GPT JSON parsing failures.

    This is a transient error that should be retried, as GPT may return
    properly formatted JSON on subsequent attempts.
    """

    pass


def clean_markdown_code_fences(response: str) -> str:
    """
    Remove markdown code fences from GPT response.

    GPT models often wrap JSON responses in markdown code blocks like:
    ```json
    {...}
    ```

    This function removes those fences and language tags.

    Args:
        response: Raw response text from GPT

    Returns:
        Cleaned response without markdown fences

    Examples:
        >>> clean_markdown_code_fences('```json\\n{"key": "value"}\\n```')
        '{"key": "value"}'
        >>> clean_markdown_code_fences('```\\n{"key": "value"}\\n```')
        '{"key": "value"}'
        >>> clean_markdown_code_fences('{"key": "value"}')
        '{"key": "value"}'
    """
    cleaned_response = response.strip()

    if cleaned_response.startswith("```"):
        lines = cleaned_response.split("\n")
        lines = lines[1:]  # Remove opening fence

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]  # Remove closing fence

        cleaned_response = "\n".join(lines).strip()

    # Remove language tag (e.g., "json") if present after opening fence
    if cleaned_response.startswith("json"):
        cleaned_response = cleaned_response[4:].strip()

    return cleaned_response


def parse_json_robustly(text: str) -> Optional[Any]:
    """
    Parse JSON with error recovery for common GPT formatting issues.

    This function attempts multiple strategies to parse potentially malformed
    JSON responses from GPT models, which often include:
    - Missing commas between objects
    - Invalid escape sequences
    - Extra whitespace or formatting issues

    Args:
        text: JSON text to parse

    Returns:
        Parsed JSON data, or None if parsing fails with all strategies

    Raises:
        ValueError: If all parsing strategies fail
    """
    # Strategy 1: Try standard JSON parsing first
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.debug(
            f"Standard JSON parsing failed: {e}. Trying recovery strategies..."
        )

    # Strategy 2: Fix common issues with missing commas between objects
    try:
        # Add commas between }{ patterns (missing commas between objects)
        fixed_text = re.sub(r"\}\s*\{", "},{", text)
        return json.loads(fixed_text)
    except json.JSONDecodeError:
        logger.debug("Comma insertion strategy failed")

    # Strategy 3: Fix extra quotes and double braces (GPT formatting issues)
    try:
        # Fix patterns like "text""}}, to "text"},
        fixed_text = text.replace('""}},', '"},').replace('""}}', '"}')
        # Replace double braces }}, with single brace },
        # Also fix }}] to }] and standalone }} before ]
        fixed_text = fixed_text.replace("}},", "},").replace("}}]", "}]")
        fixed_text = re.sub(r"\}\}(?=\s*[\],])", "}", fixed_text)
        return json.loads(fixed_text)
    except json.JSONDecodeError:
        logger.debug("Double brace fix strategy failed")

    # Strategy 4: Fix invalid escape sequences
    try:
        # Replace invalid escape sequences with valid ones
        # Common issue: \x in text where it should be \\x
        fixed_text = text
        # Fix invalid \x sequences but keep valid JSON escapes
        valid_escapes = {'"', "\\", "/", "b", "f", "n", "r", "t", "u"}

        # Find all backslash sequences
        def fix_escape(match):
            char = match.group(1)
            if char in valid_escapes or char.startswith("u"):
                return match.group(0)  # Valid escape, keep it
            return "\\\\" + char  # Invalid escape, double the backslash

        fixed_text = re.sub(r"\\(.)", fix_escape, text)
        return json.loads(fixed_text)
    except (json.JSONDecodeError, Exception) as e:
        logger.debug(f"Escape sequence fix strategy failed: {e}")

    # Strategy 5: Combined fixes - all patterns together
    try:
        fixed_text = text
        # Fix extra quotes before braces
        fixed_text = fixed_text.replace('""}},', '"},').replace('""}}', '"}')
        # Fix double braces
        fixed_text = fixed_text.replace("}},", "},").replace("}}]", "}]")
        # Fix }} followed by space and then { (double brace + missing comma)
        fixed_text = re.sub(r"\}\}\s*\{", "},{", fixed_text)
        # Fix any remaining }} before ] or ,
        fixed_text = re.sub(r"\}\}(?=\s*[\],])", "}", fixed_text)
        # Fix missing commas between normal }{ patterns
        fixed_text = re.sub(r"\}(\s*)\{", r"},\1{", fixed_text)
        return json.loads(fixed_text)
    except json.JSONDecodeError:
        logger.debug("Combined fix strategy failed")

    # Strategy 6: Fix truncated JSON at the end
    try:
        # If JSON starts with [ but doesn't end properly, try to close it
        if text.startswith("[") and not text.rstrip().endswith("]"):
            # Find the last complete object by looking for the last }
            last_brace = text.rfind("}")
            if last_brace > 0:
                # Close the array after the last complete object
                fixed_text = text[: last_brace + 1] + "]"
                return json.loads(fixed_text)
    except json.JSONDecodeError:
        logger.debug("Truncation fix strategy failed")

    # Strategy 7: Try to extract array content if wrapped incorrectly
    try:
        # Look for array pattern in text
        array_match = re.search(r"\[\s*\{.*\}\s*\]", text, re.DOTALL)
        if array_match:
            array_text = array_match.group(0)
            # Try all fix strategies on extracted array
            for strategy_text in [
                array_text,
                re.sub(r"\}\s*\{", "},{", array_text),
                array_text.replace("}},", "},").replace("}}]", "}]"),
                re.sub(
                    r"\}(\s*)\{",
                    r"},\1{",
                    array_text.replace("}},", "},").replace("}}]", "}]"),
                ),
            ]:
                try:
                    return json.loads(strategy_text)
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        logger.debug(f"Array extraction strategy failed: {e}")

    # All strategies failed
    raise GPTJSONParsingError(
        "Failed to parse JSON after trying all recovery strategies"
    )
