"""Rasterize the original document mark using the project's existing Pillow."""
from pathlib import Path

from PIL import Image, ImageDraw

target = Path(__file__).resolve().parents[1] / "public"
image = Image.new("RGBA", (256, 256))
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((8, 8, 248, 248), radius=48, fill="#e5e5e5", outline="#171717", width=12)
draw.polygon(((79, 60), (159, 60), (191, 92), (191, 208), (79, 208)), fill="#171717")
draw.polygon(((61, 44), (141, 44), (173, 76), (173, 192), (61, 192)), fill="#ffffff")
draw.line(((61, 44), (141, 44), (173, 76), (173, 192), (61, 192), (61, 44)), fill="#171717", width=10, joint="curve")
draw.polygon(((141, 44), (141, 76), (173, 76)), fill="#b3b3b3")
draw.line(((141, 44), (141, 76), (173, 76)), fill="#171717", width=10, joint="curve")
for start, end, y in ((88, 145, 104), (88, 136, 129), (88, 119, 154)):
    draw.line(((start, y), (end, y)), fill="#171717", width=12)
image.save(target / "icon.png")
image.save(target / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
