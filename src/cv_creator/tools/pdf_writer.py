"""PDF generation tool using WeasyPrint."""

from pathlib import Path

from weasyprint import HTML
from agents import function_tool


@function_tool
def generate_pdf(html_content: str, output_path: str) -> str:
    """
    Generate a PDF file from HTML content.

    Args:
        html_content: The HTML content to convert to PDF.
        output_path: The file path where the PDF should be saved.

    Returns:
        A message indicating success and the output path.
    """
    path = Path(output_path)

    # Ensure the parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Generate PDF from HTML
    html = HTML(string=html_content)
    html.write_pdf(path)

    return f"PDF successfully generated at: {output_path}"
