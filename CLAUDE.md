# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

CV Creator is a multi-agent AI tool that optimizes resumes/CVs for specific job vacancies. It reads a PDF CV, researches the target company, rewrites the CV with executive-level positioning, validates against hallucinations, and outputs a new PDF.

## Commands

```bash
# Install (editable mode)
pip install -e .

# Run full optimization
cv-creator --vacancy vacancy.txt --cv resume.pdf --output updated_cv.pdf

# With background info
cv-creator --vacancy vacancy.txt --cv resume.pdf --background background.txt --output updated_cv.pdf

# Regenerate PDF from saved content file
cv-creator --from-content optimized_cv.pdf.content -o optimized_cv.pdf

# Tests
pytest tests/
```

## Architecture

**Microsoft Agent Framework workflow with parallel fan-out/fan-in pattern.**

Entry: `cli.py` → `orchestrator.py` defines the workflow graph.

### Workflow Steps (defined in `src/cv_creator/agents/orchestrator.py`)

1. **Parallel branch**:
   - Branch A: `company_extractor` → `researcher` (extract company name, then web search for info)
   - Branch B: `cv_reader` (extract text from PDF)
2. **Sequential after merge**: `cv_writer` → `validator` → `pdf_generator` → `summarizer`
3. **Retry loop**: Validator checks for hallucinations; if failed, routes back to cv_writer (max 3 retries)

### Key Directories

- `src/cv_creator/agents/` — One file per agent, each exposes a lazy `get_*_agent()` function
- `src/cv_creator/tools/` — Reusable tools: `web_search.py` (Tavily), `pdf_reader.py` (pdfplumber), `pdf_writer.py` (WeasyPrint)
- `src/cv_creator/config.py` — Azure OpenAI client setup, model configuration

### Patterns

- **Executor pattern**: Workflow steps are `@executor(id="...")` decorated async functions in `orchestrator.py`
- **State sharing**: `ctx.set_shared_state(key, value)` / `ctx.get_shared_state(key)` for inter-step data
- **Lazy agent init**: Each agent module uses `get_*_agent()` singleton pattern
- **Output files**: Each run produces `.pdf`, `.pdf.content` (raw text), and `.pdf.summary.md`

## Environment Variables (.env)

- `AZURE_OPENAI_ENDPOINT` — Azure OpenAI service URL
- `AZURE_OPENAI_DEPLOYMENT` — Model deployment name (e.g., gpt-4o)
- `AZURE_OPENAI_API_VERSION` — API version (default: 2024-10-21)
- `TAVILY_API_KEY` — Tavily web search API key
- `AZURE_OPENAI_API_KEY` — Optional; defaults to Azure CLI credential
