"""Research Agent - Searches for company information on the web."""

from agent_framework import ChatAgent

from cv_creator.config import get_chat_client
from cv_creator.tools import web_search

RESEARCHER_INSTRUCTIONS = """You are a company research specialist. Your task is to gather relevant information about companies that can help tailor a CV.

When given a company name, use the web_search tool to find:
1. Company overview and mission
2. Industry and market position
3. Company culture and values
4. Recent news or achievements
5. Key technologies or methodologies they use
6. What they look for in candidates

Compile your findings into a concise summary (max 500 words) that highlights information most relevant for tailoring a CV.

If the company name is "Unknown Company", provide general advice for crafting a strong CV."""


def create_researcher_agent() -> ChatAgent:
    """Create the researcher agent."""
    return get_chat_client().create_agent(
        name="Researcher",
        instructions=RESEARCHER_INSTRUCTIONS,
        tools=[web_search],
    )


# Lazy-loaded singleton
_agent: ChatAgent | None = None


def get_researcher_agent() -> ChatAgent:
    """Get the researcher agent (lazy loaded)."""
    global _agent
    if _agent is None:
        _agent = create_researcher_agent()
    return _agent
