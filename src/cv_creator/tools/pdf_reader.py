"""PDF reading tool using pdfplumber."""

from pathlib import Path

import pdfplumber
from agents import function_tool


@function_tool
def read_pdf(file_path: str) -> str:
    """
    Extract text content from a PDF file.

    Args:
        file_path: Path to the PDF file to read.

    Returns:
        The extracted text content from the PDF.
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {file_path}")

    if not path.suffix.lower() == ".pdf":
        raise ValueError(f"File is not a PDF: {file_path}")

    text_content = []

    with pdfplumber.open(path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            page_text = page.extract_text()
            if page_text:
                text_content.append(f"--- Page {page_num} ---\n{page_text}")

    if not text_content:
        return "No text content could be extracted from the PDF."

    return "\n\n".join(text_content)
