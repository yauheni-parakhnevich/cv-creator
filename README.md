# CV Creator

Multi-agent CLI tool that optimizes CVs for specific job vacancies using Microsoft Agent Framework with Azure OpenAI.

It reads a PDF CV, researches the target company, rewrites the CV with executive-level positioning, validates against hallucinations, and outputs a new PDF.

## Installation

Requires Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

For development (adds pytest and ruff):

```bash
pip install -e ".[dev]"
```

### System dependencies

WeasyPrint requires system libraries for PDF generation:

```bash
# macOS
brew install pango libffi

# Ubuntu/Debian
sudo apt-get install -y libpango1.0-dev libharfbuzz-dev libffi-dev
```

## Configuration

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Required environment variables:
- `AZURE_OPENAI_ENDPOINT` — Azure OpenAI endpoint URL
- `AZURE_OPENAI_DEPLOYMENT` — Deployment name (e.g., `gpt-4o`)
- `TAVILY_API_KEY` — Tavily API key for web search

Optional:
- `AZURE_OPENAI_API_KEY` — Azure OpenAI API key (if not using Azure CLI credential)
- `AZURE_OPENAI_API_VERSION` — API version (default: `2024-10-21`)

### Authentication

Two methods are supported:

1. **Azure CLI credential** (recommended) — run `az login` before using the tool
2. **API Key** — set `AZURE_OPENAI_API_KEY` in your `.env` file

## Usage

### Full optimization

```bash
cv-creator --vacancy vacancy.txt --cv resume.pdf --output optimized_cv.pdf
```

With additional background info to enrich the CV:

```bash
cv-creator --vacancy vacancy.txt --cv resume.pdf --background background.txt --output optimized_cv.pdf
```

Pass vacancy text directly instead of a file:

```bash
cv-creator -v "Software Engineer at Google..." -c resume.pdf -o optimized_cv.pdf
```

Suppress progress output with `--quiet`:

```bash
cv-creator --vacancy vacancy.txt --cv resume.pdf --output optimized_cv.pdf --quiet
```

### Regenerate PDF from content

Each run saves a `.content` file with the raw optimized text. You can regenerate the PDF from it:

```bash
cv-creator --from-content optimized_cv.pdf.content -o optimized_cv.pdf
```

## Output

Each run produces three files:

| File | Description |
|------|-------------|
| `<output>.pdf` | Optimized CV as PDF |
| `<output>.pdf.content` | Raw optimized text (can be edited and re-rendered) |
| `<output>.pdf.summary.md` | Summary of changes made to the CV |

## Architecture

The application uses a **workflow with parallel fan-out/fan-in pattern** built on Microsoft Agent Framework.

```
                    ┌─ Company Extractor → Researcher ─┐
Start → Fan-out ──┤                                     ├── Merge → CV Writer → Validator → PDF Generator → Summarizer
                    └─ CV Reader ──────────────────────┘          ↑                │
                                                                   └── retry (max 3) ┘
```

### Agents

| Agent | Role |
|-------|------|
| **Company Extractor** | Extracts company name from the vacancy description |
| **Researcher** | Searches the web for company info using Tavily |
| **CV Reader** | Extracts text from the PDF CV using pdfplumber |
| **CV Writer** | Creates optimized executive-level CV content |
| **Validator** | Checks for hallucinations and fabricated information |
| **PDF Generator** | Renders the final PDF using WeasyPrint |
| **Summarizer** | Produces a summary of changes made |

### Key directories

```
src/cv_creator/
├── agents/          # One file per agent + orchestrator workflow
├── tools/           # Reusable tools: web_search, pdf_reader, pdf_writer
├── config.py        # Azure OpenAI client setup
└── cli.py           # CLI entry point
```

## Development

```bash
# Run tests
pytest tests/ -v

# Run linter
ruff check .

# Run tests with coverage
pytest tests/ --cov=cv_creator --cov-report=term-missing
```
