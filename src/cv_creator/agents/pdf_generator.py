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


_EXECUTIVE_SECTIONS = """3. Structure the CV HTML with these EXACT sections in order:
   - <h1> for the candidate's name (will render in uppercase, elegant serif font)
   - <p class="contact"> for contact information (email • phone • location • LinkedIn)
   - <h2>Profile</h2> - executive summary emphasizing strategic leadership and impact
   - <h2>Experience</h2> - career history focusing on leadership scope and business outcomes
   - <h2>Selected Competencies</h2> - core competencies and expertise areas
   - <h2>Leadership and Awards</h2> - board positions, executive roles, recognitions
   - <h2>Education and Professional Qualifications</h2> - degrees, executive education, certifications"""

_NORMAL_SECTIONS = """3. Structure the CV HTML with these EXACT sections in order:
   - <h1> for the candidate's name (will render in uppercase, elegant serif font)
   - <p class="contact"> for contact information (email • phone • location • LinkedIn)
   - <h2>Profile</h2> - professional summary highlighting skills and experience
   - <h2>Experience</h2> - career history focusing on responsibilities and achievements
   - <h2>Key Skills</h2> - technical and professional skills
   - <h2>Education</h2> - degrees, certifications, and training"""


def _build_instructions(fmt: str, style: str = "executive") -> str:
    """Build agent instructions for the given output format and style."""
    template = get_cv_template()
    fmt_upper = fmt.upper()
    tool_name = f"generate_{fmt}"

    if style == "executive":
        level_desc = "an executive CV formatting specialist"
        layout_desc = "an EXECUTIVE-LEVEL layout suitable for Director, VP, or C-suite positions"
        sections = _EXECUTIVE_SECTIONS
        closing = "The output should look polished, sophisticated, and appropriate for senior executive roles."
    else:
        level_desc = "a professional CV formatting specialist"
        layout_desc = "a professional layout suitable for mid-to-senior level positions"
        sections = _NORMAL_SECTIONS
        closing = "The output should look clean, professional, and well-structured."

    return f"""You are {level_desc}. Your task is to convert CV content into an elegant, professional HTML format and generate a {fmt_upper} document.

You will receive:
1. The finalized CV content
2. The output file path for the {fmt_upper}

IMPORTANT: Create {layout_desc}.
IMPORTANT: Do not do any of text adjustements or optimizations - the content is already optimized. Your task is purely to format it into a polished {fmt_upper}.

Steps:
1. Convert the CV content into polished, professional HTML
2. Use the following HTML template, replacing {{{{CV_CONTENT}}}} with the formatted CV:

{template}

{sections}

4. FORMATTING RULES:
   - Format each experience role using this EXACT HTML structure:
     <div class="role-header">
       <span class="role-title">Job Title</span>
       <span class="role-date">Start Date – End Date</span>
     </div>
     <p class="company">Company Name</p>
     Then follow with a <ul> of achievements/responsibilities.
   - Do NOT use plain text pipes (|) to separate title, company, and dates. Always use the HTML structure above.
   - Bullet points should emphasize: scope, scale, outcomes, and business impact
   - Use metrics and achievements (revenue, team size, % improvements)
   - Keep language authoritative and results-focused
   - Avoid jargon; use clear business language
   - Do not allow experience to be partially on one page and partially on another - keep each role together

5. Use the {tool_name} tool to create the final {fmt_upper}

{closing}"""


def _create_generator_agent(fmt: str, style: str = "executive") -> ChatAgent:
    """Create a document generator agent for the given format and style."""
    tool = generate_docx if fmt == "docx" else generate_pdf
    name = f"{fmt.upper()} Generator"
    return get_chat_client().create_agent(
        name=name,
        instructions=_build_instructions(fmt, style),
        tools=[tool],
    )


# Lazy-loaded cache keyed by (fmt, style)
_agents: dict[tuple[str, str], ChatAgent] = {}


def get_document_generator_agent(fmt: str = "pdf", style: str = "executive") -> ChatAgent:
    """Get the document generator agent for the given format and style."""
    key = (fmt, style)
    if key not in _agents:
        _agents[key] = _create_generator_agent(fmt, style)
    return _agents[key]


def get_pdf_generator_agent(style: str = "executive") -> ChatAgent:
    """Get the PDF generator agent (lazy loaded)."""
    return get_document_generator_agent("pdf", style)


def get_docx_generator_agent(style: str = "executive") -> ChatAgent:
    """Get the DOCX generator agent (lazy loaded)."""
    return get_document_generator_agent("docx", style)
