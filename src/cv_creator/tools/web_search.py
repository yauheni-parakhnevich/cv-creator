"""Web search tool using Tavily API."""

from typing import Annotated

from agent_framework import ai_function
from pydantic import Field

from cv_creator.config import get_tavily_client


@ai_function(name="web_search", description="Search the web for information about a company or topic")
def web_search(
    query: Annotated[str, Field(description="The search query string")],
    max_results: Annotated[int, Field(description="Maximum number of results to return")] = 5,
) -> str:
    """
    Search the web for information about a company or topic.

    Returns a formatted string containing search results with titles, URLs, and content snippets.
    """
    client = get_tavily_client()

    response = client.search(
        query=query,
        max_results=max_results,
        search_depth="advanced",
        include_answer=True,
    )

    results = []

    if response.get("answer"):
        results.append(f"Summary: {response['answer']}\n")

    for idx, result in enumerate(response.get("results", []), 1):
        title = result.get("title", "No title")
        url = result.get("url", "")
        content = result.get("content", "No content available")
        results.append(f"{idx}. {title}\n   URL: {url}\n   {content}\n")

    return "\n".join(results) if results else "No results found."
