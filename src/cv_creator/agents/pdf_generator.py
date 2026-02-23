"""PDF Generator Agent - Creates the final PDF from CV content."""

from pathlib import Path

from agent_framework import ChatAgent

from cv_creator.config import get_chat_client
from cv_creator.tools import generate_pdf


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


def create_pdf_generator_agent() -> ChatAgent:
    """Create the PDF generator agent."""
    template = get_cv_template()

    instructions = f"""You are an executive CV formatting specialist. Your task is to convert CV content into an elegant, Director/C-level professional HTML format and generate a PDF.

You will receive:
1. The finalized CV content
2. The output file path for the PDF

IMPORTANT: Create an EXECUTIVE-LEVEL layout suitable for Director, VP, or C-suite positions.

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

5. Use the generate_pdf tool to create the final PDF

The output should look polished, sophisticated, and appropriate for senior executive roles."""

    return get_chat_client().create_agent(
        name="PDF Generator",
        instructions=instructions,
        tools=[generate_pdf],
    )


# Lazy-loaded singleton
_agent: ChatAgent | None = None


def get_pdf_generator_agent() -> ChatAgent:
    """Get the PDF generator agent (lazy loaded)."""
    global _agent
    if _agent is None:
        _agent = create_pdf_generator_agent()
    return _agent
