"""Version checking for veoci-mapper."""
import json
import urllib.request
from typing import Optional

# Current version - updated on release
__version__ = "0.1.0"

REPO = "Veoci-Labs/veoci-solution-mapper"
RELEASES_URL = f"https://api.github.com/repos/{REPO}/releases/latest"


def check_for_update() -> Optional[str]:
    """Check GitHub for newer version.

    Returns new version string if available, None otherwise.
    Non-blocking - returns None on any error (network, parse, etc.)
    """
    try:
        req = urllib.request.Request(
            RELEASES_URL,
            headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "veoci-map"},
        )
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode())
            latest = data.get("tag_name", "").lstrip("v")
            if latest and latest != __version__:
                return latest
    except Exception:
        pass  # Silently fail - don't interrupt user
    return None


def get_download_url() -> str:
    """Get the releases page URL."""
    return f"https://github.com/{REPO}/releases/latest"
