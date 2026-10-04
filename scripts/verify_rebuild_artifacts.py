"""Inspect browser canvas pixels and render the exported PDF for visual review."""
import json
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageChops, ImageStat
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1] / "artifacts" / "rebuild"
results = {}
for name in ("canvas-still", "canvas-moving", "canvas-mobile", "canvas-mobile-375", "canvas-wide"):
    image = Image.open(ROOT / f"{name}.png").convert("RGB")
    saturation = [max(pixel) - min(pixel) for pixel in image.getdata()]
    fraction = sum(value > 20 for value in saturation) / len(saturation)
    assert fraction > .01, f"{name}: anatomy appears blank"
    results[name] = {"width": image.width, "height": image.height, "anatomy_pixel_fraction": round(fraction, 4)}
still = Image.open(ROOT / "canvas-still.png").convert("RGB")
moving = Image.open(ROOT / "canvas-moving.png").convert("RGB")
difference = ImageChops.difference(still, moving)
assert difference.getbbox(), "The 3D scene did not change during playback"
results["motion_mean_difference"] = sum(ImageStat.Stat(difference).mean) / 3

pdf = ROOT / "browser-report.pdf"
reader = PdfReader(pdf)
text = "\n".join(page.extract_text() for page in reader.pages)
for expected in ("Amina Khan", "39 years", "400", "118", "76", "Recorded administrations", "not a laboratory", "NIDDK"):
    assert expected in text, f"PDF missing {expected}"
document = pdfium.PdfDocument(str(pdf))
for index, page in enumerate(document):
    bitmap = page.render(scale=1.5)
    image = bitmap.to_pil().convert("RGB")
    assert min(ImageStat.Stat(image).stddev) > 5, f"PDF page {index+1} appears blank"
    image.save(ROOT / f"report-page-{index+1}.png")
    page.close()
document.close()
results["pdf_pages"] = len(reader.pages)
(ROOT / "artifact-checks.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
print(json.dumps(results, indent=2))
