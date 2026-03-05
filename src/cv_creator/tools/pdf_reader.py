"""PDF reading tool using pdfplumber."""

from pathlib import Path
from typing import Annotated

import pdfplumber
from agent_framework import ai_function
from pydantic import Field


@ai_function(name="read_cv", description="Extract text content from a CV file (PDF or Markdown)")
def read_pdf(
    file_path: Annotated[str, Field(description="Path to the CV file to read (PDF or Markdown)")],
) -> str:
    """
    Extract text content from a CV file.

    Supports PDF and Markdown (.md) formats.
    Returns the extracted text content.
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"CV file not found: {file_path}")

    suffix = path.suffix.lower()

    if suffix == ".md":
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            return "No text content could be extracted from the Markdown file."
        return text

    if suffix == ".pdf":
        text_content = []
        with pdfplumber.open(path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                page_text = page.extract_text()
                if page_text:
                    text_content.append(f"--- Page {page_num} ---\n{page_text}")
        if not text_content:
            return "No text content could be extracted from the PDF."
        return "\n\n".join(text_content)

    raise ValueError(f"Unsupported file format: {suffix}. Use PDF or Markdown (.md).")
