"""Credential storage for veoci-map."""

import json
import os
import sys
from pathlib import Path


def get_config_dir() -> Path:
    """Get platform-appropriate config directory."""
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path.home() / ".config"

    config_dir = base / "veoci-map"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_saved_pat() -> str | None:
    """Get saved PAT from config file."""
    config_file = get_config_dir() / "config.json"
    if config_file.exists():
        try:
            data = json.loads(config_file.read_text())
            return data.get("pat")
        except Exception:
            pass
    return None


def save_pat(pat: str) -> None:
    """Save PAT to config file."""
    config_file = get_config_dir() / "config.json"
    config_file.write_text(json.dumps({"pat": pat}))
    # Set restrictive permissions on Unix
    if sys.platform != "win32":
        config_file.chmod(0o600)


def mask_pat(pat: str) -> str:
    """Return masked PAT for display (last 4 chars visible)."""
    if len(pat) <= 4:
        return "****"
    return "*" * (len(pat) - 4) + pat[-4:]
