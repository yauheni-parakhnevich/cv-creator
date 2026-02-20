"""Validator Agent - Checks CV for hallucinations and verifies facts."""

import json

from pydantic import BaseModel
from agents import Agent

from cv_creator.config import get_model


class ValidationResult(BaseModel):
    """Structured validation result."""

    valid: bool
    issues: list[str]


def create_validator_agent() -> Agent:
    """Create the validator agent."""
    return Agent(
        name="Validator",
        instructions="""You are a CV validation specialist. Your task is to ensure the optimized CV contains ONLY information from the original CV.

You will receive:
1. The original CV content
2. The optimized/updated CV content

Your job is to verify that:
1. All skills listed exist in the original CV
2. All work experiences (companies, roles, dates) match the original
3. All educational qualifications match the original
4. All certifications and awards are from the original
5. All projects and achievements are based on the original
6. No fabricated or exaggerated information has been added

IMPORTANT: Rewording, reorganizing, and emphasizing information is ALLOWED. Only flag issues where:
- Completely new skills/technologies are added that weren't mentioned
- Job titles or company names are changed
- Dates are altered
- New experiences or qualifications are invented
- Achievements are significantly exaggerated beyond reasonable rewording

Respond with a JSON object containing:
- "valid": true if no issues found, false otherwise
- "issues": array of strings describing each issue found (empty if valid)

Example responses:
{"valid": true, "issues": []}
{"valid": false, "issues": ["Added 'Kubernetes' skill not in original", "Changed job title from 'Developer' to 'Senior Developer'"]}""",
        model=get_model(),
        output_type=ValidationResult,
    )


# Lazy-loaded singleton
_agent: Agent | None = None


def get_validator_agent() -> Agent:
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
        data = json.loads(result)
        return ValidationResult(**data)
    except (json.JSONDecodeError, TypeError):
        # If parsing fails, assume there are issues
        return ValidationResult(valid=False, issues=[f"Failed to parse validation result: {result}"])


