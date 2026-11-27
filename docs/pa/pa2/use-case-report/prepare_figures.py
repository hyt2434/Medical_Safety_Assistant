"""Convert the overview and 18 SVG use-case diagrams to vector PDF for XeLaTeX."""
from pathlib import Path
from io import BytesIO
import os
import pymupdf
from reportlab.graphics import renderPDF
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from svglib.svglib import svg2rlg


def main():
    # Use the diagram font when available on Windows. svglib otherwise uses
    # its normal font fallback on other platforms.
    fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    for name, filename in (
        ("Arial", "arial.ttf"),
        ("Arial-Bold", "arialbd.ttf"),
        ("Arial-Italic", "ariali.ttf"),
        ("Arial-BoldItalic", "arialbi.ttf"),
    ):
        if (fonts / filename).is_file():
            pdfmetrics.registerFont(TTFont(name, str(fonts / filename)))
    if all(name in pdfmetrics.getRegisteredFontNames() for name in
           ("Arial", "Arial-Bold", "Arial-Italic", "Arial-BoldItalic")):
        pdfmetrics.registerFontFamily(
            "Arial", normal="Arial", bold="Arial-Bold",
            italic="Arial-Italic", boldItalic="Arial-BoldItalic",
        )
    images = Path(__file__).resolve().parent / "sections" / "images"
    diagram_sources = Path(__file__).resolve().parents[3] / "design" / "use-cases" / "plantuml"
    sources = [diagram_sources / f"UC_{number:02d}.svg" for number in range(1, 19)]
    sources.insert(0, diagram_sources / "UC_00_Overview.svg")
    missing = [str(source) for source in sources if not source.is_file()]
    if missing:
        raise FileNotFoundError("Missing diagrams: " + ", ".join(missing))
    for source in sources:
        target = images / source.with_suffix(".pdf").name
        # Preserve SVG stroke-dasharray: UML include/extend must stay dashed.
        drawing = svg2rlg(str(source))
        if drawing is None:
            raise ValueError(f"Could not convert diagram: {source}")
        buffer = BytesIO()
        renderPDF.drawToFile(drawing, buffer)
        with pymupdf.open(stream=buffer.getvalue(), filetype="pdf") as pdf:
            pdf.save(target, garbage=4, deflate=True)
        print(f"Prepared {target.name}")


if __name__ == "__main__":
    main()
