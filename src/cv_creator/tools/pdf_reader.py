"""PDF reading tool using pdfplumber."""

from pathlib import Path
from typing import Annotated

import pdfplumber
from agent_framework import ai_function
from pydantic import Field


@ai_function(name="read_pdf", description="Extract text content from a PDF file")
def read_pdf(
    file_path: Annotated[str, Field(description="Path to the PDF file to read")],
) -> str:
    """
    Extract text content from a PDF file.

    Returns the extracted text content from the PDF.
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
