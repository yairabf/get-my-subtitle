"""String manipulation utilities."""


def truncate_for_logging(
    text: str, max_length: int = 1000, edge_length: int = 500
) -> str:
    """
    Truncate text for logging, showing beginning and end.

    Long text is truncated to show the first and last portions,
    with an ellipsis in the middle. Useful for logging large responses
    or data where the beginning and end are most informative.

    Args:
        text: Text to truncate
        max_length: Maximum length before truncation is applied
        edge_length: Number of characters to show from start and end

    Returns:
        Truncated text with ellipsis if needed, or original text if short enough

    Examples:
        >>> short_text = "Hello"
        >>> truncate_for_logging(short_text, max_length=100)
        'Hello'
        >>> long_text = "x" * 2000
        >>> result = truncate_for_logging(long_text, max_length=1000, edge_length=10)
        >>> len(result) < len(long_text)
        True
        >>> "..." in result
        True
    """
    if len(text) <= max_length:
        return text
    return f"{text[:edge_length]}...\n...{text[-edge_length:]}"
