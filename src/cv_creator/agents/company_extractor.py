"""Company Extractor Agent - Extracts company name from vacancy description."""

from agent_framework import ChatAgent

from cv_creator.config import get_chat_client


COMPANY_EXTRACTOR_INSTRUCTIONS = """You are a specialist in extracting company information from job vacancy descriptions.

Your task is to identify and extract the company name from the provided vacancy description.

Guidelines:
1. Look for explicit company name mentions
2. Check for company signatures, headers, or "About Us" sections
3. Look for patterns like "Join [Company]" or "[Company] is hiring"
4. If the company name appears multiple times in different forms, use the most formal/complete version
5. If no company name is found, respond with "Unknown Company"

Respond with ONLY the company name, nothing else."""


def create_company_extractor_agent() -> ChatAgent:
    """Create the company extractor agent."""
    return get_chat_client().create_agent(
        name="Company Extractor",
        instructions=COMPANY_EXTRACTOR_INSTRUCTIONS,
    )


# Lazy-loaded singleton
_agent: ChatAgent | None = None


def get_company_extractor_agent() -> ChatAgent:
    """Get the company extractor agent (lazy loaded)."""
    global _agent
    if _agent is None:
        _agent = create_company_extractor_agent()
    return _agent
