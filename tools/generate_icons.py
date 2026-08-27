from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "assets"
SIZE = 256
ICON_SIZES = (16, 32, 48, 256)


def load_font(size: int) -> ImageFont.FreeTypeFont:
    font_paths = (
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("C:/Windows/Fonts/segoeuib.ttf"),
    )
    for font_path in font_paths:
        if font_path.exists():
            return ImageFont.truetype(str(font_path), size)
    return ImageFont.load_default()


def create_icon(name: str, top_color: tuple[int, int, int], bottom_color: tuple[int, int, int]) -> None:
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    pixels = image.load()
    for y in range(SIZE):
        ratio = y / (SIZE - 1)
        color = tuple(
            round(top_color[channel] * (1 - ratio) + bottom_color[channel] * ratio)
            for channel in range(3)
        )
        for x in range(SIZE):
            pixels[x, y] = (*color, 255)

    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).rounded_rectangle((8, 8, 247, 247), radius=54, fill=255)
    image.putalpha(mask)

    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((8, 8, 247, 247), radius=54, outline=(255, 255, 255, 105), width=5)
    font = load_font(64)
    label = "DDNS"
    bounds = draw.textbbox((0, 0), label, font=font)
    x = (SIZE - (bounds[2] - bounds[0])) // 2
    y = (SIZE - (bounds[3] - bounds[1])) // 2 - 5
    draw.text((x + 2, y + 3), label, font=font, fill=(30, 30, 30, 100))
    draw.text((x, y), label, font=font, fill=(245, 247, 248, 255))

    png_path = ASSET_DIR / f"ddns-{name}.png"
    ico_path = ASSET_DIR / f"ddns-{name}.ico"
    image.save(png_path)
    image.save(ico_path, format="ICO", sizes=[(size, size) for size in ICON_SIZES])


ASSET_DIR.mkdir(exist_ok=True)
create_icon("neutral", (105, 112, 120), (52, 58, 65))
create_icon("healthy", (48, 190, 103), (17, 116, 69))
create_icon("fail", (238, 103, 91), (165, 37, 45))
