"""CLI interface for CV Creator."""

import asyncio
import sys
from pathlib import Path

import click

from cv_creator.agents import run_cv_optimization, run_from_content


@click.command()
@click.option(
    "--vacancy",
    "-v",
    default=None,
    help="Path to vacancy description file or the vacancy text directly.",
)
@click.option(
    "--cv",
    "-c",
    default=None,
    type=click.Path(exists=True, path_type=Path),
    help="Path to the original CV PDF file.",
)
@click.option(
    "--output",
    "-o",
    required=True,
    type=click.Path(path_type=Path),
    help="Path for the output PDF file.",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    default=False,
    help="Suppress detailed progress output.",
)
@click.option(
    "--background",
    "-b",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to file with additional background info extending the CV (projects, details, context).",
)
@click.option(
    "--from-content",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to a .content file to regenerate PDF and summary from, skipping the optimization workflow.",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["pdf", "docx"], case_sensitive=False),
    default="pdf",
    help="Output document format (default: pdf).",
)
def main(
    vacancy: str | None,
    cv: Path | None,
    output: Path,
    quiet: bool,
    background: Path | None,
    from_content: Path | None,
    output_format: str,
) -> None:
    """
    CV Creator - Optimize your CV for specific job opportunities.

    This tool uses AI agents to analyze a job vacancy, research the company,
    and tailor your CV to highlight relevant experience and skills.

    Examples:

        cv-creator --vacancy vacancy.txt --cv resume.pdf --output optimized_cv.pdf

        cv-creator -v "Software Engineer at Google..." -c resume.pdf -o output.pdf

        cv-creator --from-content optimized_cv.pdf.content -o optimized_cv.pdf
    """
    verbose = not quiet

    if from_content:
        # Regenerate PDF (and optionally summary) from existing content file
        vacancy_description = None
        if vacancy:
            vacancy_path = Path(vacancy)
            if vacancy_path.exists() and vacancy_path.is_file():
                vacancy_description = vacancy_path.read_text()
            else:
                vacancy_description = vacancy

        click.echo("Generating PDF from content file...")
        click.echo(f"  Content: {from_content}")
        click.echo(f"  Output: {output}")
        click.echo()

        try:
            result = asyncio.run(
                run_from_content(
                    content_path=str(from_content),
                    output_path=str(output),
                    original_cv_path=str(cv) if cv else None,
                    vacancy_description=vacancy_description,
                    verbose=verbose,
                    output_format=output_format,
                )
            )
            click.echo()
            click.echo(click.style("Success!", fg="green", bold=True))
            click.echo(f"PDF saved to: {result}")
        except Exception as e:
            click.echo()
            click.echo(click.style(f"Error: {e}", fg="red"), err=True)
            sys.exit(1)
        return

    # Full optimization workflow requires --vacancy and --cv
    if not vacancy:
        click.echo("Error: --vacancy is required (unless using --from-content).", err=True)
        sys.exit(1)
    if not cv:
        click.echo("Error: --cv is required (unless using --from-content).", err=True)
        sys.exit(1)

    # Determine if vacancy is a file path or direct text
    vacancy_path = Path(vacancy)
    if vacancy_path.exists() and vacancy_path.is_file():
        vacancy_description = vacancy_path.read_text()
        if verbose:
            click.echo(f"Read vacancy from file: {vacancy_path}")
    else:
        vacancy_description = vacancy
        if verbose:
            click.echo("Using vacancy text provided directly")

    # Validate CV file
    if not cv.suffix.lower() == ".pdf":
        click.echo("Error: CV file must be a PDF.", err=True)
        sys.exit(1)

    # Read background info if provided
    background_text = None
    if background:
        background_text = background.read_text()
        if verbose:
            click.echo(f"Read background info from file: {background}")

    click.echo("Starting CV optimization...")
    click.echo(f"  CV: {cv}")
    click.echo(f"  Output: {output}")
    if background:
        click.echo(f"  Background: {background}")
    click.echo()

    try:
        result = asyncio.run(
            run_cv_optimization(
                vacancy_description=vacancy_description,
                cv_pdf_path=str(cv),
                output_path=str(output),
                background=background_text,
                verbose=verbose,
                output_format=output_format,
            )
        )
        click.echo()
        click.echo(click.style("Success!", fg="green", bold=True))
        click.echo(f"Optimized CV saved to: {result}")

    except Exception as e:
        click.echo()
        click.echo(click.style(f"Error: {e}", fg="red"), err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
