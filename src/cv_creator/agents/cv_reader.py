"""CV Reader Agent - Extracts and structures CV content from PDF."""

from agents import Agent

from cv_creator.config import get_model
from cv_creator.tools import read_pdf


def create_cv_reader_agent() -> Agent:
    """Create the CV reader agent."""
    return Agent(
        name="CV Reader",
        instructions="""You are a CV parsing specialist. Your task is to extract and structure the content from a PDF CV.

When given a PDF file path, use the read_pdf tool to extract the text, then organize it into these sections:
1. Personal Information (name, contact details)
2. Professional Summary/Objective
3. Work Experience (company, role, dates, responsibilities, achievements)
4. Education (institution, degree, dates)
5. Skills (technical, soft skills, languages)
6. Certifications and Awards
7. Projects (if any)
8. Other relevant sections

Present the extracted information in a clear, structured format. Preserve ALL original content - do not summarize or omit any details. This information will be used to create an optimized version of the CV.""",
        model=get_model(),
        tools=[read_pdf],
    )


# Lazy-loaded singleton
_agent: Agent | None = None


def get_cv_reader_agent() -> Agent:
    """Get the CV reader agent (lazy loaded)."""
    global _agent
    if _agent is None:
        _agent = create_cv_reader_agent()
    return _agent


