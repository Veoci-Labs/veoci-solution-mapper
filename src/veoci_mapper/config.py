"""Configuration and secret handling for veoci-mapper."""
import os

# Placeholder for build-time injection. PyInstaller hook replaces this value.
# Do NOT put actual keys here - this is replaced during the build process.
_EMBEDDED_GEMINI_KEY: str | None = None

def get_gemini_key() -> str | None:
    """Get Gemini API key, preferring embedded over env var.

    Build-time embedded key takes precedence (for packaged distribution).
    Falls back to GEMINI_API_KEY environment variable (for development).
    """
    return _EMBEDDED_GEMINI_KEY or os.getenv("GEMINI_API_KEY")
