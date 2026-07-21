from __future__ import annotations

import io
from pathlib import Path

from PySide6.QtGui import QColor, QImage, QPixmap

RASTER_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".gif"}
VECTOR_EXTENSIONS = {".svg"}
# .ai files saved with Illustrator's "PDF compatible" option are valid PDFs
# under the hood, so they ride the same rasterization path as .pdf.
PDF_EXTENSIONS = {".pdf", ".ai"}
PSD_EXTENSIONS = {".psd"}
PILLOW_EXTENSIONS = {".webp", ".tiff", ".tif", ".heic", ".heif"}
MARKDOWN_EXTENSIONS = {".md"}

SUPPORTED_EXTENSIONS = (
    RASTER_EXTENSIONS | VECTOR_EXTENSIONS | PDF_EXTENSIONS | PSD_EXTENSIONS | PILLOW_EXTENSIONS | MARKDOWN_EXTENSIONS
)

IMPORT_FILE_FILTER = (
    "All Supported Files (*.png *.jpg *.jpeg *.bmp *.gif *.svg *.pdf *.ai *.psd *.webp *.tiff *.tif *.heic *.heif *.md);;"
    "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tiff *.tif *.heic *.heif);;"
    "Vector (*.svg);;"
    "Documents (*.pdf *.ai *.md);;"
    "Photoshop (*.psd)"
)

_PDF_RENDER_DPI = 150


def load_pixmap(file_path: str) -> QPixmap | None:
    """Load any supported design/image file, flattened to a single QPixmap
    for canvas use. Returns None if the file is missing, unreadable, or an
    unsupported format."""
    extension = Path(file_path).suffix.lower()

    if extension in VECTOR_EXTENSIONS:
        return _load_svg(file_path)
    if extension in PDF_EXTENSIONS:
        return _load_pdf_page(file_path)
    if extension in PSD_EXTENSIONS:
        return _load_psd(file_path)
    if extension in PILLOW_EXTENSIONS:
        return _load_via_pillow(file_path)
    if extension in MARKDOWN_EXTENSIONS:
        return _load_markdown(file_path)

    pixmap = QPixmap(file_path)
    return pixmap if not pixmap.isNull() else None


def _load_svg(file_path: str) -> QPixmap | None:
    from PySide6.QtCore import QSize
    from PySide6.QtGui import QPainter
    from PySide6.QtSvg import QSvgRenderer

    renderer = QSvgRenderer(file_path)
    if not renderer.isValid():
        return None

    size = renderer.defaultSize()
    if size.isEmpty():
        size = QSize(512, 512)

    image = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(0)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    return QPixmap.fromImage(image)


def _load_pdf_page(file_path: str) -> QPixmap | None:
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return None

    try:
        with fitz.open(file_path) as document:
            if document.page_count == 0:
                return None
            page = document.load_page(0)
            png_bytes = page.get_pixmap(dpi=_PDF_RENDER_DPI).tobytes("png")
    except Exception:
        return None

    image = QImage.fromData(png_bytes, "PNG")
    return QPixmap.fromImage(image) if not image.isNull() else None


def _load_psd(file_path: str) -> QPixmap | None:
    try:
        from psd_tools import PSDImage
    except ImportError:
        return None

    try:
        composite = PSDImage.open(file_path).composite()
    except Exception:
        return None
    if composite is None:
        return None
    return _pil_to_pixmap(composite)


def _load_via_pillow(file_path: str) -> QPixmap | None:
    try:
        from PIL import Image
    except ImportError:
        return None

    if Path(file_path).suffix.lower() in {".heic", ".heif"}:
        try:
            import pillow_heif

            pillow_heif.register_heif_opener()
        except ImportError:
            return None

    try:
        with Image.open(file_path) as pil_image:
            return _pil_to_pixmap(pil_image)
    except Exception:
        return None


def _load_markdown(file_path: str) -> QPixmap | None:
    """Render Markdown text as a flattened page image via Qt's built-in
    Markdown-to-rich-text support, so it slots into the same pixmap-based
    canvas pipeline as every other import format."""
    from PySide6.QtGui import QPainter, QTextDocument

    try:
        text = Path(file_path).read_text(encoding="utf-8")
    except OSError:
        return None

    document = QTextDocument()
    document.setTextWidth(800)
    document.setMarkdown(text)

    size = document.size().toSize()
    if size.isEmpty():
        return None

    image = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor("white"))
    painter = QPainter(image)
    document.drawContents(painter)
    painter.end()
    return QPixmap.fromImage(image)


def _pil_to_pixmap(pil_image) -> QPixmap | None:
    buffer = io.BytesIO()
    pil_image.convert("RGBA").save(buffer, format="PNG")
    image = QImage.fromData(buffer.getvalue(), "PNG")
    return QPixmap.fromImage(image) if not image.isNull() else None
