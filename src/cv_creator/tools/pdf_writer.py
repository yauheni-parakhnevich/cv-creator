"""PDF generation tool using WeasyPrint."""

from pathlib import Path
from typing import Annotated

from agent_framework import ai_function
from pydantic import Field
from weasyprint import HTML


@ai_function(name="generate_pdf", description="Generate a PDF file from HTML content")
def generate_pdf(
    html_content: Annotated[str, Field(description="The HTML content to convert to PDF")],
    output_path: Annotated[str, Field(description="The file path where the PDF should be saved")],
) -> str:
    """
    Generate a PDF file from HTML content.

    Returns a message indicating success and the output path.
    """
    path = Path(output_path)

    # Ensure the parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Generate PDF from HTML
    html = HTML(string=html_content)
    html.write_pdf(path)

    return f"PDF successfully generated at: {output_path}"
