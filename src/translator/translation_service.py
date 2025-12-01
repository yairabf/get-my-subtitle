"""Translation service for subtitle translation using OpenAI GPT-5-nano."""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from openai import AsyncOpenAI

from common.config import settings
from common.gpt_utils import (
    GPTJSONParsingError,
    clean_markdown_code_fences,
    parse_json_robustly,
)
from common.retry_utils import retry_with_exponential_backoff
from common.string_utils import truncate_for_logging
from common.subtitle_parser import TranslationCountMismatchError
from common.utils import LanguageUtils

logger = logging.getLogger(__name__)


class SubtitleTranslator:
    """Handles subtitle translation using OpenAI GPT-5-nano."""

    def __init__(self):
        """Initialize the translator with OpenAI async client."""
        self.client = None
        self._last_parsed_segment_numbers = (
            None  # Store parsed segment numbers for merge_translations
        )
        if settings.openai_api_key:
            # Initialize AsyncOpenAI client with proper configuration
            # Note: Retry logic is handled by retry_with_exponential_backoff decorator
            # Setting max_retries=0 to let our decorator handle all retries
            self.client = AsyncOpenAI(
                api_key=settings.openai_api_key,
                timeout=60.0,  # 60 second timeout for translation requests
                max_retries=0,  # Let retry decorator handle retries
            )
            logger.info(
                f"Initialized OpenAI async client with model: {settings.openai_model}"
            )
        else:
            logger.warning(
                "OpenAI API key not configured - translator will run in mock mode"
            )

    def get_last_parsed_segment_numbers(self) -> Optional[List[int]]:
        """
        Get parsed segment numbers from the last translation call.

        This is used by merge_translations to accurately identify which segments
        were successfully parsed when there's a mismatch in translation count.

        Returns:
            List of parsed segment numbers (1-based) from last translation,
            or None if not available or all translations were parsed successfully.
        """
        return self._last_parsed_segment_numbers

    @property
    def _retry_decorator(self):
        """
        Get retry decorator with OpenAI-specific configuration.

        Returns:
            Decorator function configured with settings from config
        """
        return retry_with_exponential_backoff(
            max_retries=settings.openai_max_retries,
            initial_delay=settings.openai_retry_initial_delay,
            exponential_base=settings.openai_retry_exponential_base,
            max_delay=settings.openai_retry_max_delay,
        )

    async def translate_batch(
        self, texts: List[str], source_language: str, target_language: str
    ) -> List[str]:
        """
        Translate a batch of subtitle texts using GPT-5-nano.

        This method is decorated with retry logic that handles rate limits
        and transient API failures with exponential backoff. Formatting is
        preserved through retry cycles via the translation prompt.

        Args:
            texts: List of subtitle text strings to translate
            source_language: Source language code (e.g., 'en')
            target_language: Target language code (e.g., 'es')

        Returns:
            List of translated text strings
        """
        if not self.client:
            logger.warning(
                "Mock mode: Returning original texts with [TRANSLATED] prefix"
            )
            return [f"[TRANSLATED to {target_language}] {text}" for text in texts]

        # Apply retry decorator dynamically to handle rate limits and API failures
        decorated_method = self._retry_decorator(self._translate_batch_impl)
        return await decorated_method(texts, source_language, target_language)

    async def _translate_batch_impl(
        self, texts: List[str], source_language: str, target_language: str
    ) -> List[str]:
        """
        Internal implementation of batch translation.

        This method contains the actual translation logic and is wrapped
        by the retry decorator. Formatting preservation is ensured through
        the translation prompt which remains consistent across retries.

        Args:
            texts: List of subtitle text strings to translate
            source_language: Source language code (e.g., 'en')
            target_language: Target language code (e.g., 'es')

        Returns:
            List of translated text strings
        """
        # Convert language codes to language names for OpenAI
        source_lang_name = LanguageUtils.iso_to_language_name(source_language)
        target_lang_name = LanguageUtils.iso_to_language_name(target_language)

        # Prepare the prompt for GPT-5-nano
        # Formatting preservation is maintained through this prompt structure
        prompt = self._build_translation_prompt(
            texts, source_lang_name, target_lang_name
        )

        logger.info(
            f"Translating {len(texts)} segments from {source_lang_name} "
            f"({source_language}) to {target_lang_name} ({target_language})"
        )

        # Warn if chunk is very large (might cause API issues)
        # For reasoning models (gpt-5-nano), large chunks may consume all completion tokens
        # For non-reasoning models (gpt-4o-mini), 300-400 segments is typically safe
        if len(texts) > 300:
            logger.warning(
                f"⚠️  Very large translation chunk ({len(texts)} segments). "
                f"This may cause API timeouts or token limit issues. "
                f"Consider reducing max_segments_per_chunk or increasing max_completion_tokens."
            )

        # Build API request parameters
        # Some models (like gpt-5-nano) only support default temperature (1)
        # Only include temperature if model supports custom values
        api_params = {
            "model": settings.openai_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        f"You are a professional subtitle translator. "
                        f"You will receive a JSON object with subtitle segments to translate "
                        f"from {source_lang_name} to {target_lang_name}.\n\n"
                        f"INPUT FORMAT:\n"
                        f'{{"segments": [{{"id": 1, "text": "..."}}, ...], '
                        f'"source": "{source_lang_name}", '
                        f'"target": "{target_lang_name}"}}\n\n'
                        f"OUTPUT FORMAT:\n"
                        f"Return ONLY a JSON array: "
                        f'[{{"id": 1, "text": "translation"}}, '
                        f'{{"id": 2, "text": "translation"}}]\n\n'
                        f"TRANSLATION RULES:\n"
                        f"- Translate naturally and idiomatically, "
                        f"not word-by-word\n"
                        f"- Use appropriate figures of speech and cultural "
                        f"references in {target_lang_name}\n"
                        f"- Preserve all HTML tags exactly as they appear\n"
                        f"- Maintain concise subtitle-appropriate length (2-3 seconds)\n"
                        f"- Keep the original meaning, tone, and style\n"
                        f"- Return ONLY the JSON array, no explanations or markdown fences\n"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            # For reasoning models like gpt-5-nano, need higher token limit
            # Reasoning tokens consume completion budget, so we need more headroom
            # If using gpt-5-nano, consider increasing OPENAI_MAX_TOKENS to 8192 or higher
            "max_completion_tokens": settings.openai_max_tokens,  # Required for gpt-5-nano model
            "timeout": 60.0,  # Per-request timeout override
        }

        # Only include temperature if model supports it (not nano models)
        # Nano models only support default temperature (1)
        if "nano" not in settings.openai_model.lower():
            api_params["temperature"] = settings.openai_temperature

        # Call OpenAI Chat Completions API with proper async configuration
        response = await self.client.chat.completions.create(**api_params)

        # Check if response is valid
        if not response.choices or len(response.choices) == 0:
            raise ValueError("OpenAI API returned no choices in response")

        choice = response.choices[0]
        message_content = choice.message.content

        # Handle truncated responses
        if choice.finish_reason == "length":
            if not message_content:
                # Check if all tokens were used for reasoning (common with reasoning models)
                usage_info = ""
                if hasattr(response, "usage") and response.usage:
                    usage = response.usage
                    reasoning_tokens = (
                        getattr(
                            usage.completion_tokens_details, "reasoning_tokens", None
                        )
                        if hasattr(usage, "completion_tokens_details")
                        else None
                    )
                    if (
                        reasoning_tokens
                        and reasoning_tokens >= usage.completion_tokens * 0.9
                    ):
                        usage_info = (
                            f"⚠️  CRITICAL: {reasoning_tokens}/{usage.completion_tokens} completion tokens "
                            f"({reasoning_tokens/usage.completion_tokens*100:.1f}%) were used for reasoning. "
                            f"This is a known limitation of reasoning models like gpt-5-nano.\n"
                            f"SOLUTIONS:\n"
                            f"  1) Increase OPENAI_MAX_TOKENS in .env to 8192 or 16384 (if model supports it)\n"
                            f"  2) Switch to a non-reasoning model: gpt-4o-mini, gpt-4o, or gpt-3.5-turbo\n"
                            f"  3) Reduce chunk size further (current: {len(texts)} segments, try 10-15)"
                        )
                    else:
                        usage_info = f"Usage: {usage}"

                raise ValueError(
                    f"OpenAI API response was truncated (finish_reason=length) but content is empty. "
                    f"{usage_info} "
                    f"Consider reducing chunk size (current: {len(texts)} segments)."
                )
            else:
                logger.warning(
                    f"⚠️  Response was truncated (finish_reason=length). "
                    f"Received {len(message_content)} characters but may be incomplete. "
                    f"Consider reducing chunk size or increasing max_completion_tokens."
                )
        elif not message_content:
            raise ValueError(
                f"OpenAI API returned empty content. "
                f"Response finish_reason: {choice.finish_reason}, "
                f"Usage: {response.usage if hasattr(response, 'usage') else 'N/A'}"
            )

        # Parse the response (always returns tuple)
        translations, parsed_segment_numbers = self._parse_translation_response(
            message_content, len(texts)
        )

        # Store parsed_segment_numbers for use in merge_translations
        # Will be None if all translations parsed successfully, or a list if there was a mismatch
        self._last_parsed_segment_numbers = parsed_segment_numbers

        logger.info(f"Successfully translated {len(translations)} segments")
        return translations

    def _build_translation_prompt(
        self, texts: List[str], source_language: str, target_language: str
    ) -> str:
        """
        Build the translation prompt for GPT-5-nano using JSON format.

        This method constructs a JSON-formatted prompt that reduces token consumption
        compared to the previous numbered text format while maintaining parsing reliability.

        Args:
            texts: List of texts to translate
            source_language: Source language name (e.g., 'English')
            target_language: Target language name (e.g., 'Hebrew')

        Returns:
            Formatted prompt string with JSON structure
        """
        # Build JSON structure with segment IDs and text
        segments = [{"id": i, "text": text} for i, text in enumerate(texts, 1)]
        json_input = {
            "segments": segments,
            "source": source_language,
            "target": target_language,
        }

        prompt = (
            f"Translate the subtitle segments in the JSON below from {source_language} to {target_language}.\n\n"
            f"INPUT:\n{json.dumps(json_input, ensure_ascii=False, indent=2)}\n\n"
            f"OUTPUT FORMAT: Return ONLY a JSON array with translated segments.\n"
            f'Example: [{{"id": 1, "text": "translation"}}, {{"id": 2, "text": "translation"}}]\n\n'
            f"TRANSLATION STYLE:\n"
            f"- Translate each subtitle as a complete sentence or phrase, not word-by-word\n"
            f"- Use natural, idiomatic expressions and figures of speech in {target_language}\n"
            f"- Adapt cultural references and idioms to be natural in {target_language}\n"
            f"- Maintain the original meaning and tone while making it sound natural in {target_language}\n"
            f"- Keep translations concise and suitable for subtitle display (readable in 2-3 seconds)\n\n"
            f"FORMATTING REQUIREMENTS:\n"
            f"- Preserve all HTML tags (like <i>, <b>, <u>, etc.) exactly as they appear\n"
            f"- Only translate the text content inside the tags, not the tags themselves\n"
            f"- Maintain segment IDs in your response\n"
            f"- Return ONLY the JSON array, no markdown code fences or additional commentary\n"
        )

        return prompt

    def _parse_translation_response(
        self, response: str, expected_count: int
    ) -> Tuple[List[str], Optional[List[int]]]:
        """
        Parse GPT-5-nano's JSON translation response.

        This method parses JSON-formatted responses from the translation model,
        with robust handling of markdown code fences and malformed responses.

        Args:
            response: Raw JSON response from GPT-5-nano
            expected_count: Expected number of translations

        Returns:
            Tuple of (translations, parsed_segment_numbers):
            - translations: List of translated texts
            - parsed_segment_numbers: List of parsed segment numbers (1-based),
              or None when all translations were parsed successfully

        Raises:
            TranslationCountMismatchError: If the number of parsed translations
                doesn't match the expected count. This is a transient error that
                should be retried.
            ValueError: If JSON parsing fails or response format is invalid
        """
        cleaned_response = clean_markdown_code_fences(response)
        translations_data = self._parse_json_safely(cleaned_response)
        self._validate_json_structure(translations_data)

        translation_map, parsed_segment_numbers = self._build_translation_map(
            translations_data
        )
        translations = self._extract_ordered_translations(
            translation_map, expected_count
        )

        return self._handle_translation_count_mismatch(
            translations, parsed_segment_numbers, expected_count, response
        )

    def _parse_json_safely(self, response: str) -> List[dict]:
        """
        Parse JSON response with error handling and recovery strategies.

        Uses robust JSON parsing that can handle common GPT formatting issues
        like missing commas and invalid escape sequences.

        Args:
            response: Cleaned response text to parse

        Returns:
            Parsed JSON data as list

        Raises:
            ValueError: If JSON parsing fails with all recovery strategies
        """
        try:
            return parse_json_robustly(response)
        except GPTJSONParsingError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            # Log MORE of the response for debugging (first 1000 chars)
            logger.error(f"Response preview (first 1000 chars): {response[:1000]}")
            # Also log the end of the response
            if len(response) > 1000:
                logger.error(f"Response end (last 500 chars): ...{response[-500:]}")
            # Re-raise as transient error so it will be retried
            raise GPTJSONParsingError(f"Invalid JSON response from model: {e}") from e

    def _validate_json_structure(self, data: Any) -> None:
        """
        Validate that JSON data has the expected structure.

        Args:
            data: Parsed JSON data to validate

        Raises:
            GPTJSONParsingError: If data is not a list (transient error, will retry)
        """
        if not isinstance(data, list):
            raise GPTJSONParsingError(f"Expected JSON array, got {type(data).__name__}")

    def _build_translation_map(
        self, translations_data: List[dict]
    ) -> Tuple[Dict[int, str], List[int]]:
        """
        Build mapping of segment IDs to translations.

        Iterates through the translation data and extracts valid items,
        skipping any malformed entries with warnings.

        Args:
            translations_data: List of translation objects from JSON

        Returns:
            Tuple of (translation_map, parsed_segment_numbers):
            - translation_map: Dictionary mapping segment ID to translation text
            - parsed_segment_numbers: List of successfully parsed segment IDs
        """
        translation_map = {}
        parsed_segment_numbers = []

        for item in translations_data:
            if not isinstance(item, dict):
                logger.warning(f"Skipping non-dict item in response: {item}")
                continue

            if "id" not in item or "text" not in item:
                logger.warning(f"Skipping item missing id or text fields: {item}")
                continue

            try:
                segment_id = int(item["id"])
                translation_map[segment_id] = item["text"]
                parsed_segment_numbers.append(segment_id)
            except (ValueError, TypeError) as e:
                logger.warning(f"Skipping item with invalid id: {item}, error: {e}")
                continue

        return translation_map, parsed_segment_numbers

    def _extract_ordered_translations(
        self, translation_map: Dict[int, str], expected_count: int
    ) -> List[str]:
        """
        Extract translations in sequential order.

        Args:
            translation_map: Dictionary mapping segment ID to translation
            expected_count: Expected number of translations

        Returns:
            List of translations in order (may be incomplete if some IDs missing)
        """
        translations = []
        for i in range(1, expected_count + 1):
            if i in translation_map:
                translations.append(translation_map[i])
        return translations

    def _handle_translation_count_mismatch(
        self,
        translations: List[str],
        parsed_segment_numbers: List[int],
        expected_count: int,
        original_response: str,
    ) -> Tuple[List[str], Optional[List[int]]]:
        """
        Handle cases where translation count doesn't match expected count.

        Args:
            translations: List of extracted translations
            parsed_segment_numbers: List of successfully parsed segment IDs
            expected_count: Expected number of translations
            original_response: Original response for debugging

        Returns:
            Tuple of (translations, parsed_segment_numbers or None)

        Raises:
            TranslationCountMismatchError: If more than 1 translation is missing
        """
        if len(translations) == expected_count:
            # All translations parsed successfully
            return (translations, None)

        missing_count = expected_count - len(translations)

        # Allow 1 missing translation as tolerance for minor parsing issues
        if missing_count == 1:
            logger.warning(
                f"⚠️  Translation parsing: expected {expected_count} translations, "
                f"but parsed {len(translations)} (missing 1). "
                f"This is acceptable - will use original text for the missing segment. "
                f"Parsed segment numbers: {sorted(parsed_segment_numbers) if parsed_segment_numbers else 'none'}"
            )
            return (translations, parsed_segment_numbers)

        # For more than 1 missing, log details and raise error
        self._log_translation_mismatch_details(
            expected_count, translations, parsed_segment_numbers, original_response
        )

        raise TranslationCountMismatchError(
            expected_count=expected_count,
            actual_count=len(translations),
            parsed_segment_numbers=parsed_segment_numbers,
            response_sample=truncate_for_logging(original_response),
        )

    def _log_translation_mismatch_details(
        self,
        expected_count: int,
        translations: List[str],
        parsed_segment_numbers: List[int],
        response: str,
    ) -> None:
        """
        Log detailed information about translation count mismatch.

        Args:
            expected_count: Expected number of translations
            translations: List of extracted translations
            parsed_segment_numbers: List of successfully parsed segment IDs
            response: Original response for debugging
        """
        missing_count = expected_count - len(translations)
        logger.warning(
            f"⚠️  Translation parsing mismatch: expected {expected_count} translations, "
            f"but parsed {len(translations)} (missing {missing_count}). "
            f"Parsed segment numbers: {sorted(parsed_segment_numbers) if parsed_segment_numbers else 'none'}"
        )
        logger.debug(
            f"Response sample (for debugging):\n{truncate_for_logging(response)}"
        )
