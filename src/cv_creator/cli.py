"""CLI interface for CV Creator."""

import asyncio
import sys
from pathlib import Path

import click

from cv_creator.agents import run_cv_optimization


@click.command()
@click.option(
    "--vacancy",
    "-v",
    required=True,
    help="Path to vacancy description file or the vacancy text directly.",
)
@click.option(
    "--cv",
    "-c",
    required=True,
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
def main(vacancy: str, cv: Path, output: Path, quiet: bool) -> None:
    """
    CV Creator - Optimize your CV for specific job opportunities.

    This tool uses AI agents to analyze a job vacancy, research the company,
    and tailor your CV to highlight relevant experience and skills.

    Examples:

        cv-creator --vacancy vacancy.txt --cv resume.pdf --output optimized_cv.pdf

        cv-creator -v "Software Engineer at Google..." -c resume.pdf -o output.pdf
    """
    verbose = not quiet

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

    # Ensure output has .pdf extension
    if not output.suffix.lower() == ".pdf":
        output = output.with_suffix(".pdf")

    click.echo("Starting CV optimization...")
    click.echo(f"  CV: {cv}")
    click.echo(f"  Output: {output}")
    click.echo()

    try:
        result = asyncio.run(
            run_cv_optimization(
                vacancy_description=vacancy_description,
                cv_pdf_path=str(cv),
                output_path=str(output),
                verbose=verbose,
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
