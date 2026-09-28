"""How rendered files look: colours, font, the name in the header, the logo.

Renderers take a Theme, never a brand kit: render/ knows nothing about
formats or GenerationConfig. `Theme()` is the house style. A brand kit gives
two colours, and `Theme.branded()` works out the rest from them with the
same proportions the house palette has, so a kit cannot produce a pale tint
that clashes with its own accent.
"""

import base64
from dataclasses import dataclass

HOUSE_NAME = "Content Transform"
# Always after the kit's font: on every Mac, most Linux boxes, and PowerPoint.
FALLBACK_FONTS = ('"Helvetica Neue"', "Arial", '"DejaVu Sans"', "sans-serif")


def _rgb(hex_colour: str) -> tuple[int, int, int]:
    h = hex_colour.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _hex(rgb: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{round(c):02x}" for c in rgb)


def _towards_white(hex_colour: str, amount: float) -> str:
    """`amount` 0 keeps the colour, 1 is white."""
    return _hex(tuple(c + (255 - c) * amount for c in _rgb(hex_colour)))


def _luminance(hex_colour: str) -> float:
    def channel(c: int) -> float:
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in _rgb(hex_colour))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_with_white(hex_colour: str) -> float:
    """WCAG contrast ratio against white, 1 to 21. Symmetric: it is also how
    readable white text is on this colour."""
    return 1.05 / (_luminance(hex_colour) + 0.05)


@dataclass(frozen=True)
class Theme:
    org_name: str = HOUSE_NAME
    ink: str = "#1a1f2b"  # body text
    muted: str = "#5b6475"  # secondary text: sources, labels, footers
    accent: str = "#0b5cad"  # headings, bullets, the title slide
    accent_soft: str = "#eef4fb"  # tinted panels
    rule: str = "#d8dde6"  # hairlines
    on_accent_muted: str = "#c9dbf0"  # secondary text on an accent background
    font: str | None = None  # tried first; FALLBACK_FONTS after it
    logo: bytes | None = None  # PNG or JPEG
    logo_type: str | None = None  # "image/png" or "image/jpeg"

    @classmethod
    def branded(
        cls, org_name: str, primary: str, ink: str, font: str | None, logo: bytes | None, logo_type: str | None
    ) -> "Theme":
        return cls(
            org_name=org_name,
            ink=ink,
            muted=_towards_white(ink, 0.3),
            accent=primary,
            accent_soft=_towards_white(primary, 0.93),
            rule=_towards_white(ink, 0.85),
            on_accent_muted=_towards_white(primary, 0.78),
            font=font,
            logo=logo,
            logo_type=logo_type,
        )

    @property
    def css_fonts(self) -> str:
        """A CSS font-family list. The kit's font name is checked when the kit
        is saved (letters, digits, spaces, hyphens), so quoting it is safe."""
        return ", ".join(((f'"{self.font}"',) if self.font else ()) + FALLBACK_FONTS)

    @property
    def deck_font(self) -> str:
        return self.font or "Arial"

    @property
    def logo_uri(self) -> str | None:
        """The logo as a data: URI, the only kind of URL the PDF renderer may load."""
        if not self.logo:
            return None
        return f"data:{self.logo_type};base64,{base64.b64encode(self.logo).decode()}"
