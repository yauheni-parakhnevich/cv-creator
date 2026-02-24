"""Summarizer Agent - Summarizes changes between original and optimized CV."""

from pathlib import Path

from agent_framework import ChatAgent

from cv_creator.config import get_chat_client

SUMMARIZER_INSTRUCTIONS = """You are a CV changes summarizer. Your task is to compare the original CV with the optimized CV and provide a clear, concise summary of the changes made.

Create a summary that includes:

1. **Professional Summary**: What was changed in the summary/objective section
2. **Skills**: Any skills that were reordered, emphasized, or reformatted
3. **Experience**: How job descriptions were reworded or reorganized
4. **Keywords**: What keywords from the job posting were incorporated
5. **Formatting**: Any structural changes made

Format your summary as a readable markdown document with clear sections.
Be specific about what changed - don't just say "improved wording", explain HOW it was improved.
Note any content that was emphasized or de-emphasized for this specific role.

Keep the summary concise but informative (around 200-400 words)."""


def create_summarizer_agent() -> ChatAgent:
    """Create an agent that summarizes changes between original and optimized CV."""
    return get_chat_client().create_agent(
        name="CV Changes Summarizer",
        instructions=SUMMARIZER_INSTRUCTIONS,
    )


_agent: ChatAgent | None = None


def get_summarizer_agent() -> ChatAgent:
    """Get the summarizer agent (lazy loaded)."""
    global _agent
    if _agent is None:
        _agent = create_summarizer_agent()
    return _agent


async def generate_changes_summary(
    original: str, optimized: str, vacancy: str, output_path: str
) -> str:
    """
    Generate a summary of changes between original and optimized CV.

    Args:
        original: The original CV content.
        optimized: The optimized CV content.
        vacancy: The job vacancy description.
        output_path: The PDF output path (summary will be saved as *.pdf.summary.md).

    Returns:
        The path to the generated summary file.
    """
    summary_path = Path(output_path + ".summary.md")

    summarizer = get_summarizer_agent()
    result = await summarizer.run(
        f"""Compare these two CV versions and summarize the changes made to tailor it for the job.

TARGET JOB:
{vacancy[:1000]}

ORIGINAL CV:
{original}

OPTIMIZED CV:
{optimized}

Provide a clear summary of what was changed and why.""",
    )

    summary_path.write_text(result.text)
    return str(summary_path)
