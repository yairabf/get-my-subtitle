"""Translation service for subtitle translation using OpenAI GPT-5-nano."""

import logging
from typing import List

from openai import AsyncOpenAI

from common.config import settings
from common.retry_utils import retry_with_exponential_backoff

logger = logging.getLogger(__name__)


class SubtitleTranslator:
    """Handles subtitle translation using OpenAI GPT-5-nano."""

    def __init__(self):
        """Initialize the translator with OpenAI async client."""
        self.client = None
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
        # Prepare the prompt for GPT-5-nano
        # Formatting preservation is maintained through this prompt structure
        prompt = self._build_translation_prompt(texts, source_language, target_language)

        logger.info(
            f"Translating {len(texts)} segments from {source_language} to {target_language}"
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
                        f"Translate subtitles from {source_language} to {target_language}. "
                        f"Maintain the same tone, style, and timing suitability. "
                        f"Keep translations concise for subtitle display. "
                        f"Preserve formatting like line breaks."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "max_completion_tokens": settings.openai_max_tokens,  # Use max_completion_tokens for newer models
            "timeout": 60.0,  # Per-request timeout override
        }

        # Only include temperature if model supports it (not nano models)
        # Nano models only support default temperature (1)
        if "nano" not in settings.openai_model.lower():
            api_params["temperature"] = settings.openai_temperature

        # Call OpenAI Chat Completions API with proper async configuration
        response = await self.client.chat.completions.create(**api_params)

        # Parse the response
        translations = self._parse_translation_response(
            response.choices[0].message.content, len(texts)
        )

        logger.info(f"Successfully translated {len(translations)} segments")
        return translations

    def _build_translation_prompt(
        self, texts: List[str], source_language: str, target_language: str
    ) -> str:
        """
        Build the translation prompt for GPT-5-nano.

        Args:
            texts: List of texts to translate
            source_language: Source language code
            target_language: Target language code

        Returns:
            Formatted prompt string
        """
        # Number each text for easy parsing
        numbered_texts = []
        for i, text in enumerate(texts, 1):
            numbered_texts.append(f"[{i}]\n{text}")

        prompt = (
            f"Translate the following {len(texts)} subtitle segments "
            f"from {source_language} to {target_language}.\n\n"
            f"Return ONLY the translations, numbered the same way, "
            f"with no additional commentary.\n\n"
            f"Format your response exactly like this:\n"
            f"[1]\nTranslated text\n\n"
            f"[2]\nTranslated text\n\n"
            f"etc.\n\n"
            f"Subtitles to translate:\n\n" + "\n\n".join(numbered_texts)
        )

        return prompt

    def _parse_translation_response(
        self, response: str, expected_count: int
    ) -> List[str]:
        """
        Parse GPT-5-nano's translation response.

        Args:
            response: Raw response from GPT-5-nano
            expected_count: Expected number of translations

        Returns:
            List of translated texts
        """
        translations = []

        # Split by numbered segments
        segments = response.split("[")

        for segment in segments:
            if not segment.strip():
                continue

            # Extract number and text
            parts = segment.split("]", 1)
            if len(parts) == 2:
                try:
                    number = int(parts[0].strip())
                    text = parts[1].strip()
                    translations.append(text)
                except ValueError:
                    continue

        if len(translations) != expected_count:
            logger.warning(
                f"Expected {expected_count} translations but got {len(translations)}"
            )

        return translations
