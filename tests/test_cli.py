"""Tests for the CLI interface."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

from click.testing import CliRunner

from cv_creator.cli import main


@patch("cv_creator.cli.run_cv_optimization", new_callable=AsyncMock)
@patch("cv_creator.cli.run_from_content", new_callable=AsyncMock)
class TestCLI:
    """Tests for the cv-creator CLI."""

    def setup_method(self):
        self.runner = CliRunner()

    # --- Validation / argument errors ---

    def test_missing_output_gives_click_error(self, _mock_fc, _mock_opt):
        result = self.runner.invoke(main, ["--vacancy", "some text", "--cv", "x.pdf"])
        assert result.exit_code == 2

    def test_missing_vacancy_without_from_content(self, _mock_fc, _mock_opt):
        with self.runner.isolated_filesystem():
            Path("resume.pdf").touch()
            result = self.runner.invoke(main, ["--cv", "resume.pdf", "-o", "out.pdf"])
        assert result.exit_code == 1
        assert "--vacancy is required" in result.output

    def test_missing_cv_without_from_content(self, _mock_fc, _mock_opt):
        result = self.runner.invoke(main, ["--vacancy", "some text", "-o", "out.pdf"])
        assert result.exit_code == 1
        assert "--cv is required" in result.output

    def test_cv_not_pdf(self, _mock_fc, _mock_opt):
        with self.runner.isolated_filesystem():
            Path("resume.docx").touch()
            result = self.runner.invoke(
                main, ["--vacancy", "text", "--cv", "resume.docx", "-o", "out.pdf"]
            )
        assert result.exit_code == 1
        assert "must be a PDF" in result.output

    def test_cv_file_not_found(self, _mock_fc, _mock_opt):
        result = self.runner.invoke(
            main, ["--vacancy", "text", "--cv", "nonexistent.pdf", "-o", "out.pdf"]
        )
        assert result.exit_code == 2

    # --- Full optimization workflow ---

    def test_happy_path(self, _mock_fc, mock_opt):
        mock_opt.return_value = "out.pdf"
        with self.runner.isolated_filesystem():
            Path("resume.pdf").touch()
            result = self.runner.invoke(
                main, ["--vacancy", "Engineer at ACME", "--cv", "resume.pdf", "-o", "out.pdf"]
            )
        assert result.exit_code == 0
        assert "Success!" in result.output
        mock_opt.assert_called_once()
        call_kw = mock_opt.call_args.kwargs
        assert call_kw["vacancy_description"] == "Engineer at ACME"
        assert call_kw["verbose"] is True

    def test_vacancy_from_file(self, _mock_fc, mock_opt):
        mock_opt.return_value = "out.pdf"
        with self.runner.isolated_filesystem():
            Path("vacancy.txt").write_text("Job description from file")
            Path("resume.pdf").touch()
            result = self.runner.invoke(
                main, ["--vacancy", "vacancy.txt", "--cv", "resume.pdf", "-o", "out.pdf"]
            )
        assert result.exit_code == 0
        assert mock_opt.call_args.kwargs["vacancy_description"] == "Job description from file"

    def test_with_background(self, _mock_fc, mock_opt):
        mock_opt.return_value = "out.pdf"
        with self.runner.isolated_filesystem():
            Path("resume.pdf").touch()
            Path("bg.txt").write_text("Extra background info")
            result = self.runner.invoke(
                main,
                ["--vacancy", "text", "--cv", "resume.pdf", "-b", "bg.txt", "-o", "out.pdf"],
            )
        assert result.exit_code == 0
        assert mock_opt.call_args.kwargs["background"] == "Extra background info"

    def test_quiet_flag(self, _mock_fc, mock_opt):
        mock_opt.return_value = "out.pdf"
        with self.runner.isolated_filesystem():
            Path("resume.pdf").touch()
            result = self.runner.invoke(
                main, ["--vacancy", "text", "--cv", "resume.pdf", "-q", "-o", "out.pdf"]
            )
        assert result.exit_code == 0
        assert mock_opt.call_args.kwargs["verbose"] is False

    def test_optimization_error(self, _mock_fc, mock_opt):
        mock_opt.side_effect = RuntimeError("API broke")
        with self.runner.isolated_filesystem():
            Path("resume.pdf").touch()
            result = self.runner.invoke(
                main, ["--vacancy", "text", "--cv", "resume.pdf", "-o", "out.pdf"]
            )
        assert result.exit_code == 1
        assert "Error:" in result.output

    # --- From-content workflow ---

    def test_from_content_happy_path(self, mock_fc, _mock_opt):
        mock_fc.return_value = "out.pdf"
        with self.runner.isolated_filesystem():
            Path("saved.content").write_text("saved content")
            result = self.runner.invoke(
                main, ["--from-content", "saved.content", "-o", "out.pdf"]
            )
        assert result.exit_code == 0
        assert "Success!" in result.output
        mock_fc.assert_called_once()

    def test_from_content_with_vacancy_file(self, mock_fc, _mock_opt):
        mock_fc.return_value = "out.pdf"
        with self.runner.isolated_filesystem():
            Path("saved.content").write_text("content")
            Path("vacancy.txt").write_text("Job desc from file")
            result = self.runner.invoke(
                main,
                ["--from-content", "saved.content", "-v", "vacancy.txt", "-o", "out.pdf"],
            )
        assert result.exit_code == 0
        assert mock_fc.call_args.kwargs["vacancy_description"] == "Job desc from file"

    def test_from_content_with_vacancy_inline(self, mock_fc, _mock_opt):
        mock_fc.return_value = "out.pdf"
        with self.runner.isolated_filesystem():
            Path("saved.content").write_text("content")
            result = self.runner.invoke(
                main,
                ["--from-content", "saved.content", "-v", "Inline vacancy text", "-o", "out.pdf"],
            )
        assert result.exit_code == 0
        assert mock_fc.call_args.kwargs["vacancy_description"] == "Inline vacancy text"

    def test_from_content_error(self, mock_fc, _mock_opt):
        mock_fc.side_effect = RuntimeError("PDF generation failed")
        with self.runner.isolated_filesystem():
            Path("saved.content").write_text("content")
            result = self.runner.invoke(
                main, ["--from-content", "saved.content", "-o", "out.pdf"]
            )
        assert result.exit_code == 1
        assert "Error:" in result.output
