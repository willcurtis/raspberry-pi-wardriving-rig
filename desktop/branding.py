"""The Tech Shed visual identity used by the desktop controller."""

from pathlib import Path

ASSET_DIR = Path(__file__).resolve().parent / "assets"
LOGO_PATH = ASSET_DIR / "tts-round-outline.png"

# Dominant colours sampled from the supplied The Tech Shed logo.
COLORS = {
    "navy": "#0B1721",
    "navy_alt": "#0C222C",
    "surface": "#102B38",
    "surface_alt": "#153542",
    "border": "#24505E",
    "cyan": "#00B6EF",
    "cyan_dark": "#0090A9",
    "teal": "#00D29C",
    "teal_dark": "#00A981",
    "text": "#F1FAFC",
    "muted": "#9CB7C2",
    "danger": "#E75A70",
    "danger_dark": "#B83B51",
    "warning": "#F2B84B",
}

