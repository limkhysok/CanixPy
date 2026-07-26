from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QMarginsF, QRectF, QSize, QSizeF, Qt
from PySide6.QtGui import QBrush, QImage, QPageSize, QPainter, QPdfWriter
from PySide6.QtSvg import QSvgGenerator
from PySide6.QtWidgets import QGraphicsScene

if TYPE_CHECKING:
    from src.features.editor.canvas.page import Page

# PDF points are defined as 1/72 inch; pinning the writer's resolution to 72
# DPI makes "1 point" and "1 device pixel" the same number, so the page can
# be sized directly in the canvas's own width/height without a conversion.
_PDF_POINTS_PER_INCH = 72

# The canvas's own pixel dimensions are treated as a 72 DPI ("1 CSS px = 1
# point") baseline, same assumption as the PDF writer above -- so a chosen
# export DPI translates to a pixel scale via dpi / 72, and that scale is what
# actually grows the rendered image; the DPI value itself is then just
# embedded as metadata (see _set_image_dpi) for print software to read.
BASELINE_DPI = 72


def _set_image_dpi(image: QImage, dpi: int) -> None:
    dots_per_meter = round(dpi / 0.0254)
    image.setDotsPerMeterX(dots_per_meter)
    image.setDotsPerMeterY(dots_per_meter)


def _page_source_rect(page: "Page") -> QRectF:
    """The exported page's region within the shared multi-page scene --
    pages are freely positioned, not all anchored at the scene origin, so
    this can't just be QRectF(0, 0, width, height)."""
    return QRectF(page.x_offset, page.y_offset, page.width, page.height)


def _hide_page_background(scene: QGraphicsScene, page: "Page") -> tuple[bool, QBrush]:
    """Temporarily strip this page's white fill/shadow and the gray canvas
    surround so a render captures only the actual content, for transparent
    exports. Only this page's frame needs hiding -- it's the only one inside
    the render's source rect. Returns what to restore afterward."""
    was_visible = page.frame.isVisible()
    previous_brush = scene.backgroundBrush()
    page.frame.setVisible(False)
    scene.setBackgroundBrush(QBrush(Qt.GlobalColor.transparent))
    return was_visible, previous_brush


def _restore_page_background(scene: QGraphicsScene, page: "Page", was_visible: bool, previous_brush: QBrush) -> None:
    page.frame.setVisible(was_visible)
    scene.setBackgroundBrush(previous_brush)


def export_scene_to_png(
    scene: QGraphicsScene, file_path: str, page: "Page", transparent: bool = False, dpi: int = BASELINE_DPI
) -> None:
    scale = dpi / BASELINE_DPI
    width, height = round(page.width * scale), round(page.height * scale)
    # Hide selection boundaries temporarily so handles aren't baked into the image
    scene.clearSelection()

    restore_state = _hide_page_background(scene, page) if transparent else None
    try:
        if transparent:
            image = QImage(width, height, QImage.Format.Format_ARGB32)
            image.fill(Qt.GlobalColor.transparent)
        else:
            image = QImage(width, height, QImage.Format.Format_RGB32)
            image.fill(Qt.GlobalColor.white)

        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        scene.render(painter, QRectF(0, 0, width, height), _page_source_rect(page))
        painter.end()
    finally:
        if restore_state is not None:
            _restore_page_background(scene, page, *restore_state)

    _set_image_dpi(image, dpi)
    image.save(file_path, "PNG")


def export_scene_to_jpg(scene: QGraphicsScene, file_path: str, page: "Page", dpi: int = BASELINE_DPI) -> None:
    scale = dpi / BASELINE_DPI
    width, height = round(page.width * scale), round(page.height * scale)
    scene.clearSelection()

    # JPEG has no alpha channel, so this always renders on an opaque white page.
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.white)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    scene.render(painter, QRectF(0, 0, width, height), _page_source_rect(page))
    painter.end()

    _set_image_dpi(image, dpi)
    image.save(file_path, "JPG", quality=92)


def export_scene_to_svg(scene: QGraphicsScene, file_path: str, page: "Page") -> None:
    width, height = int(page.width), int(page.height)
    scene.clearSelection()

    generator = QSvgGenerator()
    generator.setFileName(file_path)
    generator.setSize(QSize(width, height))
    generator.setViewBox(QRectF(0, 0, width, height))
    generator.setTitle(Path(file_path).stem)

    painter = QPainter(generator)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    scene.render(painter, QRectF(0, 0, width, height), _page_source_rect(page))
    painter.end()


def export_scene_to_pdf(scene: QGraphicsScene, file_path: str, page: "Page") -> None:
    width, height = int(page.width), int(page.height)
    scene.clearSelection()

    writer = QPdfWriter(file_path)
    writer.setResolution(_PDF_POINTS_PER_INCH)
    writer.setPageSize(QPageSize(QSizeF(width, height), QPageSize.Unit.Point))
    writer.setPageMargins(QMarginsF(0, 0, 0, 0))

    painter = QPainter(writer)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    scene.render(painter, QRectF(0, 0, width, height), _page_source_rect(page))
    painter.end()


# Format key -> (file extension, export function, whether it accepts a `dpi`
# kwarg) -- shared by export_all_pages so the "export every page" flow reuses
# the exact same per-page renderers as the single-page Export dialog instead
# of a separate implementation. Defined after every export_scene_to_* function
# above so this dict can reference them directly. PDF/SVG are vector formats
# with no per-pixel resolution to vary, so they don't take a `dpi` kwarg.
_EXPORTERS = {
    "png": ("png", export_scene_to_png, True),
    "png_transparent": (
        "png",
        lambda scene, path, page, dpi=BASELINE_DPI: export_scene_to_png(scene, path, page, transparent=True, dpi=dpi),
        True,
    ),
    "jpg": ("jpg", export_scene_to_jpg, True),
    "pdf": ("pdf", export_scene_to_pdf, False),
    "svg": ("svg", export_scene_to_svg, False),
}


def export_page(scene: QGraphicsScene, file_path: str, page: "Page", fmt: str, dpi: int = BASELINE_DPI) -> None:
    """Exports a single page to `file_path` under the given format key (an
    _EXPORTERS key) -- the single-page counterpart to export_all_pages,
    sharing the same format dispatch."""
    _extension, export_one, accepts_dpi = _EXPORTERS[fmt]
    if accepts_dpi:
        export_one(scene, file_path, page, dpi=dpi)
    else:
        export_one(scene, file_path, page)


def export_extension(fmt: str) -> str:
    """The file extension (no leading dot) an _EXPORTERS key writes."""
    return _EXPORTERS[fmt][0]


def export_all_pages(
    scene: QGraphicsScene,
    pages: list["Page"],
    directory: str,
    fmt: str,
    base_name: str = "design_page",
    dpi: int = BASELINE_DPI,
    on_progress: Callable[[int, int], bool] | None = None,
    page_numbers: list[int] | None = None,
) -> list[str]:
    """Exports each of `pages` to its own file in `directory`, named
    "{base_name}_{n}.{ext}". Returns the written paths.

    `pages` doesn't have to be the document's full page list -- it can be an
    arbitrary subset (e.g. just the ones a user checked in the Export
    dialog). `page_numbers`, if given, supplies the `n` for each entry (so
    filenames reflect a page's real position in the document, e.g. exporting
    only pages 2 and 4 still writes "..._2" and "..._4", not "..._1"/"..._2");
    it defaults to sequential numbering starting at 1.

    `on_progress`, if given, is called after each page as
    (pages_done, pages_total) so a caller can drive a progress dialog; it
    returns whether to keep going, so returning False (e.g. the user hit
    Cancel) stops the export early with whatever's been written so far."""
    extension, export_one, accepts_dpi = _EXPORTERS[fmt]
    numbers = page_numbers if page_numbers is not None else list(range(1, len(pages) + 1))
    paths: list[str] = []
    total = len(pages)
    for done, (page, number) in enumerate(zip(pages, numbers), start=1):
        file_path = str(Path(directory) / f"{base_name}_{number}.{extension}")
        if accepts_dpi:
            export_one(scene, file_path, page, dpi=dpi)
        else:
            export_one(scene, file_path, page)
        paths.append(file_path)
        if on_progress is not None and not on_progress(done, total):
            break
    return paths
