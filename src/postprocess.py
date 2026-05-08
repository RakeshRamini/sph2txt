"""
sph2txt — Text post-processing.

Applies additional formatting after Whisper transcription:
  - Trim whitespace
  - Voice command substitution (e.g., "new line" → \\n)
  - Optional sentence case correction
"""

import logging
import re

logger = logging.getLogger(__name__)


def postprocess(text: str, config: dict) -> str:
    """Clean up and apply voice commands to transcribed text."""
    if not text:
        return text

    text = text.strip()
    text = _apply_voice_commands(text, config)
    return text


def _apply_voice_commands(text: str, config: dict) -> str:
    """Replace spoken voice commands with their literal equivalents."""
    commands: dict[str, str] = config.get("voice_commands", {})
    if not commands:
        return text

    for phrase, replacement in commands.items():
        # Match the phrase with optional surrounding whitespace
        pattern = re.compile(r'\s*' + re.escape(phrase) + r'\s*', re.IGNORECASE)
        text = pattern.sub(replacement, text)

    return text
