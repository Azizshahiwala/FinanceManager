"""
pdf.py — HTML → PDF via WeasyPrint.

render_pdf(html_string, base_url) -> bytes

If WeasyPrint is not installed, raises ImportError — callers should
catch it and return a friendly fallback response.
"""
from __future__ import annotations


def render_pdf(html: str, base_url: str) -> bytes:
    """
    Convert an HTML string to PDF bytes using WeasyPrint.
    Raises ImportError if WeasyPrint is not available.
    Raises any WeasyPrint error transparently.
    """
    try:
        from weasyprint import HTML  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            'WeasyPrint is not installed. Run: pip install weasyprint'
        ) from exc

    return HTML(string=html, base_url=base_url).write_pdf()
