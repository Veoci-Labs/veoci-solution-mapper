"""Build script - injects Gemini API key into config.py before PyInstaller runs."""
import os
import sys
from pathlib import Path


def inject_key():
    """Inject GEMINI_API_KEY from environment into config.py."""
    key = os.environ.get('GEMINI_API_KEY')
    if not key:
        print("WARNING: GEMINI_API_KEY not set - embedded key will be None")
        print("         Dashboard AI features will not work in the built executable")
        return

    config_path = Path('src/veoci_mapper/config.py')
    if not config_path.exists():
        print(f"ERROR: {config_path} not found")
        sys.exit(1)

    content = config_path.read_text()

    # Check if placeholder exists
    placeholder = '_EMBEDDED_GEMINI_KEY: str | None = None'
    if placeholder not in content:
        print(f"ERROR: Placeholder not found in {config_path}")
        print("       Expected: {placeholder}")
        sys.exit(1)

    # Replace placeholder with actual key
    new_content = content.replace(
        placeholder,
        f'_EMBEDDED_GEMINI_KEY: str | None = "{key}"'
    )

    config_path.write_text(new_content)
    print(f"✓ Injecting API key into {config_path}")
    print(f"✓ Updated {config_path}")


if __name__ == '__main__':
    inject_key()
