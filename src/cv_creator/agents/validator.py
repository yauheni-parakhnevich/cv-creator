"""Validator Agent - Checks CV for hallucinations and verifies facts."""

import json

from agent_framework import ChatAgent
from pydantic import BaseModel

from cv_creator.config import get_chat_client


class ValidationResult(BaseModel):
    """Structured validation result."""

    valid: bool
    issues: list[str]


VALIDATOR_INSTRUCTIONS = """You are a CV validation specialist. Your task is to ensure the optimized CV contains ONLY information from the provided source materials.

You will receive:
1. The original CV content
2. (Optional) Additional background info - this is ALSO valid source material
3. The optimized/updated CV content

IMPORTANT: Information from BOTH the original CV AND the additional background info (if provided) is considered valid. The background info extends the CV with more details about projects, skills, and experiences.

Your job is to verify that:
1. All skills listed exist in EITHER the original CV OR the background info
2. All work experiences (companies, roles, dates) match the source materials
3. All educational qualifications match the source materials
4. All certifications and awards are from the source materials
5. All projects and achievements are based on the source materials
6. No fabricated or exaggerated information has been added

IMPORTANT: Rewording, reorganizing, and emphasizing information is ALLOWED. Only flag issues where:
- Completely new skills/technologies are added that weren't in ANY source material
- Job titles or company names are changed
- Dates are altered
- New experiences or qualifications are invented (not in any source)
- Achievements are significantly exaggerated beyond reasonable rewording

Respond with a JSON object containing:
- "valid": true if no issues found, false otherwise
- "issues": array of strings describing each issue found (empty if valid)

Example responses:
{"valid": true, "issues": []}
{"valid": false, "issues": ["Added 'Kubernetes' skill not in any source", "Changed job title from 'Developer' to 'Senior Developer'"]}"""


def create_validator_agent() -> ChatAgent:
    """Create the validator agent."""
    return get_chat_client().create_agent(
        name="Validator",
        instructions=VALIDATOR_INSTRUCTIONS,
    )


# Lazy-loaded singleton
_agent: ChatAgent | None = None


def get_validator_agent() -> ChatAgent:
    """Get the validator agent (lazy loaded)."""
    global _agent
    if _agent is None:
        _agent = create_validator_agent()
    return _agent


def parse_validation_result(result: str | ValidationResult) -> ValidationResult:
    """Parse the validation result from the agent."""
    if isinstance(result, ValidationResult):
        return result

    # Try to parse as JSON if it's a string
    try:
        # Handle case where result might be wrapped in markdown code block
        text = result.strip()
        if text.startswith("```"):
            # Remove markdown code block
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

        data = json.loads(text)
        return ValidationResult(**data)
    except (json.JSONDecodeError, TypeError, ValueError):
        # If parsing fails, assume there are issues
        return ValidationResult(valid=False, issues=[f"Failed to parse validation result: {result}"])
