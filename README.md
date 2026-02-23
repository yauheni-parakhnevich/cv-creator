# CV Creator

Multi-agent CLI application to optimize CVs based on job descriptions using Microsoft Agent Framework with Azure OpenAI.

## Installation

```bash
python -m venv venv
source venv/bin/activate
pip install -e .
```

## Configuration

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Required environment variables:
- `AZURE_OPENAI_ENDPOINT` - Azure OpenAI endpoint URL
- `AZURE_OPENAI_DEPLOYMENT` - Deployment name (e.g., gpt-4o)
- `TAVILY_API_KEY` - Tavily API key for web search

Optional environment variables:
- `AZURE_OPENAI_API_KEY` - Azure OpenAI API key (if not using Azure CLI credential)
- `AZURE_OPENAI_API_VERSION` - API version (default: 2024-10-21)

### Authentication

The application supports two authentication methods:

1. **Azure CLI credential** (recommended): Run `az login` before using the application
2. **API Key**: Set `AZURE_OPENAI_API_KEY` in your `.env` file

## Usage

```bash
cv-creator --vacancy vacancy.txt --cv resume.pdf --output updated_cv.pdf
```

Or with verbose output:

```bash
cv-creator -v "Software Engineer at Google..." -c resume.pdf -o output.pdf
```

Use `--quiet` flag to suppress detailed progress output:

```bash
cv-creator --vacancy vacancy.txt --cv resume.pdf --output updated_cv.pdf --quiet
```

## Architecture

The application uses Microsoft Agent Framework with a multi-agent architecture:

1. **Orchestrator Agent** - Coordinates the workflow using agent-as-tool pattern
2. **Company Extractor Agent** - Extracts company name from vacancy
3. **Research Agent** - Searches for company information using Tavily API
4. **CV Reader Agent** - Extracts text from PDF CV using pdfplumber
5. **CV Writer Agent** - Creates optimized executive-level CV content
6. **Validator Agent** - Checks for hallucinations and fabricated information
7. **PDF Generator Agent** - Creates the final PDF using WeasyPrint
8. **Summarizer Agent** - Creates a summary of changes made to the CV

## Output

The application generates:
- An optimized PDF CV at the specified output path
- A summary of changes at `<output_path>.summary.md`
