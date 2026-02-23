"""PDF text extraction via pymupdf."""

from __future__ import annotations

from pathlib import Path

from keel.utils.console import warn


def extract_pdf_text(pdf_path: Path) -> str | None:
    """Extract text content from a PDF file.

    Returns the extracted text, or None if extraction fails.
    """
    try:
        import pymupdf
    except ImportError:
        try:
            import fitz as pymupdf  # type: ignore[no-redef]
        except ImportError:
            warn("pymupdf not installed. Run: uv add pymupdf")
            return None

    try:
        doc = pymupdf.open(str(pdf_path))
        pages: list[str] = []

        for page in doc:
            text = page.get_text()
            if text.strip():
                pages.append(text)

        doc.close()

        if not pages:
            warn(
                f"No text extracted from {pdf_path.name}. "
                "It may be a scanned PDF — try an OCR tool like Adobe Acrobat or ocrmypdf."
            )
            return None

        return "\n\n---\n\n".join(pages)

    except Exception as exc:
        warn(f"Failed to extract text from {pdf_path.name}: {exc}")
        return None
