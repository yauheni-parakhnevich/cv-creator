"""Company Extractor Agent - Extracts company name from vacancy description."""

from agents import Agent

from cv_creator.config import get_model


def create_company_extractor_agent() -> Agent:
    """Create the company extractor agent."""
    return Agent(
        name="Company Extractor",
        instructions="""You are a specialist in extracting company information from job vacancy descriptions.

Your task is to identify and extract the company name from the provided vacancy description.

Guidelines:
1. Look for explicit company name mentions
2. Check for company signatures, headers, or "About Us" sections
3. Look for patterns like "Join [Company]" or "[Company] is hiring"
4. If the company name appears multiple times in different forms, use the most formal/complete version
5. If no company name is found, respond with "Unknown Company"

Respond with ONLY the company name, nothing else.""",
        model=get_model(),
    )


# Lazy-loaded singleton
_agent: Agent | None = None


def get_company_extractor_agent() -> Agent:
    """Get the company extractor agent (lazy loaded)."""
    global _agent
    if _agent is None:
        _agent = create_company_extractor_agent()
    return _agent


