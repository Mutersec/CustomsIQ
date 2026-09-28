"""Generate the site icons from the CustomsIQ shield emblem.

Writes, into src/customsiq/static/:

- favicon.svg              the vector emblem, for browsers that take SVG icons
- favicon.ico              16, 32 and 48 px in one file, served at /favicon.ico
- favicon.png              48 x 48 (Google Search needs a multiple of 48 px)
- favicon-96.png           96 x 96
- favicon-192.png          192 x 192 (Android, and Google's preferred size)
- apple-touch-icon.png     180 x 180 on a solid background (iOS ignores alpha)

The emblem is the same one the pages draw inline: a navy shield with a gold
rim, a gold container and a white bar. It is drawn here with Pillow at 16x
the target size and scaled down, which is what keeps the small sizes crisp.
Pillow is a one-off asset tool, not a project dependency:

    pip install pillow
    python scripts/make_favicons.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

STATIC = Path(__file__).resolve().parent.parent / "src" / "customsiq" / "static"

NAVY = (11, 37, 69, 255)
NAVY_2 = (19, 49, 92, 255)
GOLD = (201, 162, 39, 255)
WHITE = (255, 255, 255, 255)

#: The emblem's own coordinate system (the inline SVGs use viewBox 0 0 40 44),
#: placed in a 44 x 44 square so the icon is centred.
VIEW = 44.0
X_OFFSET = 2.0

SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 44 44">
  <g transform="translate(2 0)">
    <path d="M20 2 L37 8 V22 C37 32 29.5 39.5 20 42 C10.5 39.5 3 32 3 22 V8 Z"
          fill="#13315c" stroke="#c9a227" stroke-width="2.5"/>
    <rect x="10" y="17" width="20" height="12" rx="1.5" fill="#c9a227"/>
    <path d="M14 19 V27 M18 19 V27 M22 19 V27 M26 19 V27" stroke="#13315c" stroke-width="1.6"/>
    <path d="M11 13 H29" stroke="#fff" stroke-width="2" stroke-linecap="round"/>
  </g>
</svg>
"""


def _cubic(p0: tuple, p1: tuple, p2: tuple, p3: tuple, steps: int = 24) -> list:
    """Points along one cubic Bezier segment (endpoint excluded)."""
    points = []
    for i in range(steps):
        t = i / steps
        u = 1 - t
        x = u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0]
        y = u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1]
        points.append((x, y))
    return points


def _shield(inset: float = 0.0) -> list:
    """The shield outline in emblem units, optionally shrunk towards its centre."""
    outline = [(20, 2), (37, 8), (37, 22)]
    outline += _cubic((37, 22), (37, 32), (29.5, 39.5), (20, 42))
    outline += _cubic((20, 42), (10.5, 39.5), (3, 32), (3, 22))
    outline += [(3, 8)]
    if not inset:
        return outline
    cx, cy = 20.0, 22.0
    scale = 1 - inset
    return [(cx + (x - cx) * scale, cy + (y - cy) * scale) for x, y in outline]


def draw(size: int, background: tuple = (0, 0, 0, 0)) -> Image.Image:
    """Render the emblem at `size` px, supersampled 16x for smooth edges."""
    big = size * 16
    unit = big / VIEW
    image = Image.new("RGBA", (big, big), background)
    pen = ImageDraw.Draw(image)

    def pt(x: float, y: float) -> tuple:
        return ((x + X_OFFSET) * unit, y * unit)

    # Gold rim, then the navy body inset inside it: the stroke of the SVG.
    pen.polygon([pt(x, y) for x, y in _shield()], fill=GOLD)
    pen.polygon([pt(x, y) for x, y in _shield(inset=0.075)], fill=NAVY_2)

    x0, y0 = pt(10, 17)
    x1, y1 = pt(30, 29)
    pen.rounded_rectangle((x0, y0, x1, y1), radius=1.5 * unit, fill=GOLD)
    for x in (14, 18, 22, 26):
        a, b = pt(x - 0.8, 19), pt(x + 0.8, 27)
        pen.rectangle((a[0], a[1], b[0], b[1]), fill=NAVY_2)
    a, b = pt(11, 12), pt(29, 14)
    pen.rounded_rectangle((a[0], a[1], b[0], b[1]), radius=1 * unit, fill=WHITE)

    return image.resize((size, size), Image.Resampling.LANCZOS)


def main() -> None:
    (STATIC / "favicon.svg").write_text(SVG, encoding="utf-8")
    draw(48).save(STATIC / "favicon.png")
    draw(96).save(STATIC / "favicon-96.png")
    draw(192).save(STATIC / "favicon-192.png")
    draw(180, background=NAVY).save(STATIC / "apple-touch-icon.png")
    draw(48).save(STATIC / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    print(f"wrote icons to {STATIC}")


if __name__ == "__main__":
    main()
