"""Tests for CV Creator tools."""

import pytest
from pathlib import Path


class TestPdfReader:
    """Tests for the PDF reader tool."""

    def test_read_pdf_file_not_found(self):
        """Test that reading a non-existent PDF raises FileNotFoundError."""
        from cv_creator.tools.pdf_reader import read_pdf

        with pytest.raises(FileNotFoundError):
            read_pdf.fn(file_path="/nonexistent/path/to/file.pdf")

    def test_read_pdf_invalid_extension(self, tmp_path: Path):
        """Test that reading a non-PDF file raises ValueError."""
        from cv_creator.tools.pdf_reader import read_pdf

        # Create a non-PDF file
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        with pytest.raises(ValueError):
            read_pdf.fn(file_path=str(test_file))


class TestPdfWriter:
    """Tests for the PDF writer tool."""

    def test_generate_pdf_creates_file(self, tmp_path: Path):
        """Test that generate_pdf creates a PDF file."""
        from cv_creator.tools.pdf_writer import generate_pdf

        output_path = tmp_path / "output.pdf"
        html_content = "<html><body><h1>Test CV</h1></body></html>"

        result = generate_pdf.fn(html_content=html_content, output_path=str(output_path))

        assert output_path.exists()
        assert "successfully generated" in result

    def test_generate_pdf_creates_parent_dirs(self, tmp_path: Path):
        """Test that generate_pdf creates parent directories if needed."""
        from cv_creator.tools.pdf_writer import generate_pdf

        output_path = tmp_path / "subdir" / "nested" / "output.pdf"
        html_content = "<html><body><h1>Test CV</h1></body></html>"

        generate_pdf.fn(html_content=html_content, output_path=str(output_path))

        assert output_path.exists()
