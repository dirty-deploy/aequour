"""Font lookup for the synthetic images (quotes, demo plates). Searches the usual font folders of Windows, Linux and macOS and
falls back to Pillow's built-in font, so no path is hard-coded and the tools run anywhere."""
import os
from pathlib import Path

from PIL import ImageFont

_DIRS = [Path(os.environ.get("WINDIR", "")) / "Fonts", Path("/usr/share/fonts/truetype/dejavu"), Path("/usr/share/fonts/truetype/liberation"),
         Path("/usr/share/fonts/dejavu"), Path("/System/Library/Fonts/Supplemental"), Path("/Library/Fonts"), Path.home() / ".fonts"]
FAMILIES = {
    "sans": ["arial.ttf", "Arial.ttf", "LiberationSans-Regular.ttf", "DejaVuSans.ttf"],
    "bold": ["arialbd.ttf", "Arial Bold.ttf", "LiberationSans-Bold.ttf", "DejaVuSans-Bold.ttf"],
    "mono": ["consola.ttf", "Courier New.ttf", "LiberationMono-Regular.ttf", "DejaVuSansMono.ttf"],
    "serif": ["times.ttf", "Times New Roman.ttf", "LiberationSerif-Regular.ttf", "DejaVuSerif.ttf"],
    "humanist": ["calibri.ttf", "segoeui.ttf", "LiberationSans-Regular.ttf", "DejaVuSans.ttf"],
}


def find(family):
    """Path of the first installed font of that family, or None."""
    for name in FAMILIES[family]:
        for d in _DIRS:
            p = d / name
            if p.exists():
                return str(p)
    return None


def available():
    """Families that have an installed font (always at least one entry: the built-in fallback is 'builtin')."""
    got = [f for f in FAMILIES if find(f)]
    return got or ["builtin"]


def load(family, size):
    path = find(family) if family != "builtin" else None
    return ImageFont.truetype(path, size) if path else ImageFont.load_default(size=size)
