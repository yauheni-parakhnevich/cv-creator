"""Document Generator Agent - Creates the final PDF or DOCX from CV content."""

from pathlib import Path

from agent_framework import ChatAgent

from cv_creator.config import get_chat_client
from cv_creator.tools import generate_docx, generate_pdf


def get_cv_template() -> str:
    """Load the CV HTML template."""
    template_path = Path(__file__).parent.parent / "templates" / "cv_template.html"
    if template_path.exists():
        return template_path.read_text()
    # Return a default template if the file doesn't exist
    return """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }
        h1 { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }
        h2 { color: #34495e; margin-top: 20px; }
        .section { margin-bottom: 20px; }
        .contact { color: #7f8c8d; }
        ul { margin: 10px 0; }
        li { margin: 5px 0; }
    </style>
</head>
<body>
{{CV_CONTENT}}
</body>
</html>"""


def _build_instructions(fmt: str) -> str:
    """Build agent instructions for the given output format."""
    template = get_cv_template()
    fmt_upper = fmt.upper()
    tool_name = f"generate_{fmt}"

    return f"""You are an executive CV formatting specialist. Your task is to convert CV content into an elegant, Director/C-level professional HTML format and generate a {fmt_upper} document.

You will receive:
1. The finalized CV content
2. The output file path for the {fmt_upper}

IMPORTANT: Create an EXECUTIVE-LEVEL layout suitable for Director, VP, or C-suite positions.
IMPORTANT: Do not do any of text adjustements or optimizations - the content is already optimized. Your task is purely to format it into a polished {fmt_upper}.

Steps:
1. Convert the CV content into polished, executive-style HTML
2. Use the following HTML template, replacing {{{{CV_CONTENT}}}} with the formatted CV:

{template}

3. Structure the CV HTML with these EXACT sections in order:
   - <h1> for the candidate's name (will render in uppercase, elegant serif font)
   - <p class="contact"> for contact information (email • phone • location • LinkedIn)
   - <h2>Profile</h2> - executive summary emphasizing strategic leadership and impact
   - <h2>Experience</h2> - career history focusing on leadership scope and business outcomes
   - <h2>Selected Competencies</h2> - core competencies and expertise areas
   - <h2>Leadership and Awards</h2> - board positions, executive roles, recognitions
   - <h2>Education and Professional Qualifications</h2> - degrees, executive education, certifications

4. EXECUTIVE FORMATTING RULES:
   - Use <strong> for job titles (e.g., <strong>Chief Technology Officer</strong>)
   - Format each role as: <strong>Title</strong> | Company Name | Dates
   - Bullet points should emphasize: scope, scale, outcomes, and business impact
   - Use metrics and achievements (revenue, team size, % improvements)
   - Competencies should be grouped by category (e.g., Strategic Leadership, Technology, Operations)
   - Keep language authoritative and results-focused
   - Avoid jargon; use clear business language
   - Do not allow experience to be partially on one page and partially on another - keep each role together

5. Use the {tool_name} tool to create the final {fmt_upper}

The output should look polished, sophisticated, and appropriate for senior executive roles."""


def _create_generator_agent(fmt: str) -> ChatAgent:
    """Create a document generator agent for the given format (pdf or docx)."""
    tool = generate_docx if fmt == "docx" else generate_pdf
    name = f"{fmt.upper()} Generator"
    return get_chat_client().create_agent(
        name=name,
        instructions=_build_instructions(fmt),
        tools=[tool],
    )


# Lazy-loaded singletons
_agent: ChatAgent | None = None
_docx_agent: ChatAgent | None = None


def get_pdf_generator_agent() -> ChatAgent:
    """Get the PDF generator agent (lazy loaded)."""
    global _agent
    if _agent is None:
        _agent = _create_generator_agent("pdf")
    return _agent


def get_docx_generator_agent() -> ChatAgent:
    """Get the DOCX generator agent (lazy loaded)."""
    global _docx_agent
    if _docx_agent is None:
        _docx_agent = _create_generator_agent("docx")
    return _docx_agent


def get_document_generator_agent(fmt: str = "pdf") -> ChatAgent:
    """Get the document generator agent for the given format."""
    if fmt == "docx":
        return get_docx_generator_agent()
    return get_pdf_generator_agent()
