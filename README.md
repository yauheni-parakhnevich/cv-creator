# CV Creator

Multi-agent CLI application to optimize CVs based on job descriptions using OpenAI Agents SDK with Azure OpenAI.

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
- `AZURE_OPENAI_API_KEY` - Azure OpenAI API key
- `AZURE_OPENAI_ENDPOINT` - Azure OpenAI endpoint URL
- `AZURE_OPENAI_API_VERSION` - API version (e.g., 2024-08-01-preview)
- `AZURE_OPENAI_DEPLOYMENT` - Deployment name (e.g., gpt-4o)
- `TAVILY_API_KEY` - Tavily API key for web search

## Usage

```bash
cv-creator --vacancy vacancy.txt --cv resume.pdf --output updated_cv.pdf
```

Or with verbose output:

```bash
cv-creator -v "Software Engineer at Google..." -c resume.pdf -o output.pdf --verbose
```

## Architecture

The application uses a multi-agent architecture:

1. **Orchestrator Agent** - Coordinates the workflow
2. **Company Extractor Agent** - Extracts company name from vacancy
3. **Research Agent** - Searches for company information
4. **CV Reader Agent** - Extracts text from PDF CV
5. **CV Writer Agent** - Creates optimized CV content
6. **Validator Agent** - Checks for hallucinations
7. **PDF Generator Agent** - Creates the final PDF
