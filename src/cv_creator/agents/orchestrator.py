"""Orchestrator - Coordinates the CV optimization workflow using Microsoft Agent Framework Workflows."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from agent_framework import (
    AgentExecutor,
    AgentExecutorRequest,
    AgentExecutorResponse,
    ChatAgent,
    ChatMessage,
    WorkflowBuilder,
    WorkflowContext,
    WorkflowEvent,
    executor,
)
from typing_extensions import Never

from cv_creator.config import get_chat_client, initialize
from .company_extractor import get_company_extractor_agent
from .researcher import get_researcher_agent
from .cv_reader import get_cv_reader_agent
from .cv_writer import get_cv_writer_agent
from .validator import get_validator_agent, parse_validation_result
from .pdf_generator import get_pdf_generator_agent
from .summarizer import get_summarizer_agent


MAX_VALIDATION_RETRIES = 3

# State keys for workflow context
STATE_VACANCY = "vacancy"
STATE_COMPANY_NAME = "company_name"
STATE_COMPANY_RESEARCH = "company_research"
STATE_ORIGINAL_CV = "original_cv"
STATE_OPTIMIZED_CV = "optimized_cv"
STATE_VALIDATION_ISSUES = "validation_issues"
STATE_VALIDATION_RETRIES = "validation_retries"
STATE_CV_PDF_PATH = "cv_pdf_path"
STATE_OUTPUT_PATH = "output_path"
STATE_RESEARCH_READY = "research_ready"
STATE_CV_READY = "cv_ready"
STATE_BACKGROUND = "background"


@dataclass
class WorkflowInput:
    """Input to start the CV optimization workflow."""
    vacancy_description: str
    cv_pdf_path: str
    output_path: str
    background: str | None = None


@dataclass
class BranchTrigger:
    """Trigger message for parallel branches."""
    pass


@dataclass
class BranchComplete:
    """Signal that a parallel branch has completed."""
    branch: str


@dataclass
class ValidationStepResult:
    """Result from validation step with retry logic."""
    valid: bool
    issues: list[str]
    retry_count: int


# ============================================================================
# Workflow Executors
# ============================================================================

@executor(id="start_workflow")
async def start_workflow(
    input_data: WorkflowInput, ctx: WorkflowContext[BranchTrigger]
) -> None:
    """Initialize workflow state and trigger parallel branches."""
    # Store workflow configuration in state
    await ctx.set_shared_state(STATE_VACANCY, input_data.vacancy_description)
    await ctx.set_shared_state(STATE_CV_PDF_PATH, input_data.cv_pdf_path)
    await ctx.set_shared_state(STATE_OUTPUT_PATH, input_data.output_path)
    await ctx.set_shared_state(STATE_BACKGROUND, input_data.background or "")
    await ctx.set_shared_state(STATE_VALIDATION_RETRIES, 0)
    await ctx.set_shared_state(STATE_VALIDATION_ISSUES, "")
    await ctx.set_shared_state(STATE_RESEARCH_READY, False)
    await ctx.set_shared_state(STATE_CV_READY, False)

    # Trigger parallel branches (fan-out will send to both)
    await ctx.send_message(BranchTrigger())


@executor(id="start_company_branch")
async def start_company_branch(
    trigger: BranchTrigger, ctx: WorkflowContext[AgentExecutorRequest]
) -> None:
    """Start the company extraction branch."""
    _ = trigger  # Used for type routing
    vacancy = await ctx.get_shared_state(STATE_VACANCY)

    await ctx.send_message(
        AgentExecutorRequest(
            messages=[ChatMessage(role="user", text=
                f"Extract the company name from this vacancy description:\n\n{vacancy}"
            )],
            should_respond=True,
        )
    )


@executor(id="start_cv_branch")
async def start_cv_branch(
    trigger: BranchTrigger, ctx: WorkflowContext[AgentExecutorRequest]
) -> None:
    """Start the CV reading branch."""
    _ = trigger  # Used for type routing
    cv_pdf_path = await ctx.get_shared_state(STATE_CV_PDF_PATH)

    await ctx.send_message(
        AgentExecutorRequest(
            messages=[ChatMessage(role="user", text=
                f"Read and extract the content from the CV at: {cv_pdf_path}"
            )],
            should_respond=True,
        )
    )


@executor(id="process_company_name")
async def process_company_name(
    response: AgentExecutorResponse, ctx: WorkflowContext[AgentExecutorRequest]
) -> None:
    """Store company name and trigger research."""
    company_name = response.agent_run_response.text.strip()
    await ctx.set_shared_state(STATE_COMPANY_NAME, company_name)
    vacancy = await ctx.get_shared_state(STATE_VACANCY)

    # Send to researcher agent
    await ctx.send_message(
        AgentExecutorRequest(
            messages=[ChatMessage(role="user", text=
                f"Research the company '{company_name}' and provide relevant information for tailoring a CV. "
                f"Context from job posting:\n{vacancy[:1000]}"
            )],
            should_respond=True,
        )
    )


@executor(id="process_research")
async def process_research(
    response: AgentExecutorResponse, ctx: WorkflowContext[BranchComplete]
) -> None:
    """Store research results and signal branch completion."""
    await ctx.set_shared_state(STATE_COMPANY_RESEARCH, response.agent_run_response.text)
    await ctx.set_shared_state(STATE_RESEARCH_READY, True)

    # Signal that company/research branch is complete
    await ctx.send_message(BranchComplete(branch="company"))


@executor(id="process_cv_content")
async def process_cv_content(
    response: AgentExecutorResponse, ctx: WorkflowContext[BranchComplete]
) -> None:
    """Store original CV and signal branch completion."""
    original_cv = response.agent_run_response.text
    await ctx.set_shared_state(STATE_ORIGINAL_CV, original_cv)
    await ctx.set_shared_state(STATE_CV_READY, True)

    # Signal that CV branch is complete
    await ctx.send_message(BranchComplete(branch="cv"))


@executor(id="merge_branches")
async def merge_branches(
    branches: list[BranchComplete], ctx: WorkflowContext[AgentExecutorRequest]
) -> None:
    """Merge parallel branches and trigger CV writing."""
    _ = branches  # All branches complete at this point

    # Get all required data from state
    original_cv = await ctx.get_shared_state(STATE_ORIGINAL_CV)
    vacancy = await ctx.get_shared_state(STATE_VACANCY)
    company_research = await ctx.get_shared_state(STATE_COMPANY_RESEARCH)
    background = await ctx.get_shared_state(STATE_BACKGROUND) or ""
    validation_issues = await ctx.get_shared_state(STATE_VALIDATION_ISSUES) or ""
    current_date = date.today().strftime("%B %Y")

    # Build prompt for CV writer
    prompt = f"""Create an optimized CV based on:

CURRENT DATE: {current_date}

ORIGINAL CV:
{original_cv}

JOB VACANCY:
{vacancy}

COMPANY RESEARCH:
{company_research}
"""
    if background:
        prompt += f"""
ADDITIONAL BACKGROUND (use this to enrich the CV with more details. Use it as a selectable pool of extended experience. Only include bullets relevant to the target role.):
{background}
"""
    if validation_issues:
        prompt += f"""
VALIDATION ISSUES TO FIX:
{validation_issues}

Please fix these issues while maintaining the quality of the CV.
"""

    # Send to CV writer agent
    await ctx.send_message(
        AgentExecutorRequest(
            messages=[ChatMessage(role="user", text=prompt)],
            should_respond=True,
        )
    )


@executor(id="process_optimized_cv")
async def process_optimized_cv(
    response: AgentExecutorResponse, ctx: WorkflowContext[AgentExecutorRequest]
) -> None:
    """Store optimized CV and trigger validation."""
    optimized_cv = response.agent_run_response.text
    await ctx.set_shared_state(STATE_OPTIMIZED_CV, optimized_cv)
    original_cv = await ctx.get_shared_state(STATE_ORIGINAL_CV)
    background = await ctx.get_shared_state(STATE_BACKGROUND) or ""

    # Build validation prompt
    validation_prompt = f"""Validate the optimized CV against the source materials.

ORIGINAL CV:
{original_cv}
"""
    if background:
        validation_prompt += f"""
ADDITIONAL BACKGROUND INFO (also valid source material):
{background}
"""
    validation_prompt += f"""
OPTIMIZED CV:
{optimized_cv}
"""

    # Send to validator agent
    await ctx.send_message(
        AgentExecutorRequest(
            messages=[ChatMessage(role="user", text=validation_prompt)],
            should_respond=True,
        )
    )


@executor(id="process_validation")
async def process_validation(
    response: AgentExecutorResponse, ctx: WorkflowContext[ValidationStepResult]
) -> None:
    """Process validation result and decide next step."""
    validation_result = parse_validation_result(response.agent_run_response.text)
    retry_count = await ctx.get_shared_state(STATE_VALIDATION_RETRIES) or 0

    await ctx.send_message(
        ValidationStepResult(
            valid=validation_result.valid,
            issues=validation_result.issues,
            retry_count=retry_count,
        )
    )


@executor(id="handle_validation_success")
async def handle_validation_success(
    result: ValidationStepResult, ctx: WorkflowContext[AgentExecutorRequest]
) -> None:
    """Validation passed - trigger PDF generation."""
    _ = result  # Used for type routing
    optimized_cv = await ctx.get_shared_state(STATE_OPTIMIZED_CV)
    output_path = await ctx.get_shared_state(STATE_OUTPUT_PATH)

    # Send to PDF generator agent
    await ctx.send_message(
        AgentExecutorRequest(
            messages=[ChatMessage(role="user", text=
                f"""Convert the following CV content into a professional PDF.

CV CONTENT:
{optimized_cv}

OUTPUT PATH: {output_path}
"""
            )],
            should_respond=True,
        )
    )


@executor(id="handle_validation_retry")
async def handle_validation_retry(
    result: ValidationStepResult, ctx: WorkflowContext[AgentExecutorRequest]
) -> None:
    """Validation failed - retry CV writing with issues."""
    # Update retry count and store issues
    new_retry_count = result.retry_count + 1
    await ctx.set_shared_state(STATE_VALIDATION_RETRIES, new_retry_count)
    await ctx.set_shared_state(STATE_VALIDATION_ISSUES, "\n".join(result.issues))

    # Get data for rewriting
    original_cv = await ctx.get_shared_state(STATE_ORIGINAL_CV)
    vacancy = await ctx.get_shared_state(STATE_VACANCY)
    company_research = await ctx.get_shared_state(STATE_COMPANY_RESEARCH)
    background = await ctx.get_shared_state(STATE_BACKGROUND) or ""
    current_date = date.today().strftime("%B %Y")

    # Build prompt with validation issues
    prompt = f"""Create an optimized CV based on:

CURRENT DATE: {current_date}

ORIGINAL CV:
{original_cv}

JOB VACANCY:
{vacancy}

COMPANY RESEARCH:
{company_research}
"""
    if background:
        prompt += f"""
ADDITIONAL BACKGROUND (use this to enrich the CV with more details):
{background}
"""
    prompt += f"""
VALIDATION ISSUES TO FIX:
{"\n".join(result.issues)}

Please fix these issues while maintaining the quality of the CV.
"""

    # Send back to CV writer agent
    await ctx.send_message(
        AgentExecutorRequest(
            messages=[ChatMessage(role="user", text=prompt)],
            should_respond=True,
        )
    )


@executor(id="handle_validation_failed")
async def handle_validation_failed(
    result: ValidationStepResult, ctx: WorkflowContext[AgentExecutorRequest]
) -> None:
    """Validation failed after max retries - generate PDF anyway with warning."""
    optimized_cv = await ctx.get_shared_state(STATE_OPTIMIZED_CV)
    output_path = await ctx.get_shared_state(STATE_OUTPUT_PATH)

    # Add warning about validation issues
    await ctx.add_event(WorkflowEvent(
        "warning",
        data=f"CV generated with validation issues after {MAX_VALIDATION_RETRIES} retries: {result.issues}"
    ))

    # Still generate PDF
    await ctx.send_message(
        AgentExecutorRequest(
            messages=[ChatMessage(role="user", text=
                f"""Convert the following CV content into a professional PDF.

CV CONTENT:
{optimized_cv}

OUTPUT PATH: {output_path}
"""
            )],
            should_respond=True,
        )
    )


@executor(id="process_pdf_generated")
async def process_pdf_generated(
    response: AgentExecutorResponse, ctx: WorkflowContext[AgentExecutorRequest]
) -> None:
    """PDF generated - trigger summarization."""
    _ = response  # Used for type routing
    original_cv = await ctx.get_shared_state(STATE_ORIGINAL_CV)
    optimized_cv = await ctx.get_shared_state(STATE_OPTIMIZED_CV)
    vacancy = await ctx.get_shared_state(STATE_VACANCY)

    # Send to summarizer agent
    await ctx.send_message(
        AgentExecutorRequest(
            messages=[ChatMessage(role="user", text=
                f"""Compare these two CV versions and summarize the changes made.

TARGET JOB:
{vacancy[:1000]}

ORIGINAL CV:
{original_cv}

OPTIMIZED CV:
{optimized_cv}

Provide a clear summary of what was changed and why."""
            )],
            should_respond=True,
        )
    )


@executor(id="finalize_workflow")
async def finalize_workflow(
    response: AgentExecutorResponse, ctx: WorkflowContext[Never, str]
) -> None:
    """Save summary and yield final output."""
    output_path = await ctx.get_shared_state(STATE_OUTPUT_PATH)
    summary_path = Path(output_path + ".summary.md")
    summary_path.write_text(response.agent_run_response.text)

    await ctx.yield_output(
        f"CV optimization complete!\n"
        f"PDF: {output_path}\n"
        f"Summary: {summary_path}"
    )


# ============================================================================
# Condition Functions for Routing
# ============================================================================

def is_validation_success(result: Any) -> bool:
    """Check if validation passed."""
    return isinstance(result, ValidationStepResult) and result.valid


def is_validation_retry(result: Any) -> bool:
    """Check if validation failed but can retry."""
    return (
        isinstance(result, ValidationStepResult)
        and not result.valid
        and result.retry_count < MAX_VALIDATION_RETRIES
    )


def is_validation_failed(result: Any) -> bool:
    """Check if validation failed after max retries."""
    return (
        isinstance(result, ValidationStepResult)
        and not result.valid
        and result.retry_count >= MAX_VALIDATION_RETRIES
    )


# ============================================================================
# Workflow Builder
# ============================================================================

def create_cv_optimization_workflow(cv_pdf_path: str, output_path: str):
    """Create the CV optimization workflow with parallel execution."""
    # Parameters kept for API consistency; paths are passed via WorkflowInput
    _ = cv_pdf_path, output_path

    # Create agent executors
    company_extractor = AgentExecutor(
        get_company_extractor_agent(),
        id="company_extractor_agent",
    )
    researcher = AgentExecutor(
        get_researcher_agent(),
        id="researcher_agent",
    )
    cv_reader = AgentExecutor(
        get_cv_reader_agent(),
        id="cv_reader_agent",
    )
    cv_writer = AgentExecutor(
        get_cv_writer_agent(),
        id="cv_writer_agent",
    )
    validator = AgentExecutor(
        get_validator_agent(),
        id="validator_agent",
    )
    pdf_generator = AgentExecutor(
        get_pdf_generator_agent(),
        id="pdf_generator_agent",
    )
    summarizer = AgentExecutor(
        get_summarizer_agent(),
        id="summarizer_agent",
    )

    # Build workflow with parallel execution
    workflow = (
        WorkflowBuilder()
        .set_start_executor(start_workflow)

        # Fan-out: Start triggers both branches in parallel
        .add_fan_out_edges(start_workflow, [start_company_branch, start_cv_branch])

        # Branch 1: Company Extraction -> Research
        .add_edge(start_company_branch, company_extractor)
        .add_edge(company_extractor, process_company_name)
        .add_edge(process_company_name, researcher)
        .add_edge(researcher, process_research)

        # Branch 2: CV Reading (parallel with Branch 1)
        .add_edge(start_cv_branch, cv_reader)
        .add_edge(cv_reader, process_cv_content)

        # Fan-in: Both branches merge before CV writing
        .add_fan_in_edges([process_research, process_cv_content], merge_branches)

        # CV Writing
        .add_edge(merge_branches, cv_writer)
        .add_edge(cv_writer, process_optimized_cv)

        # Validation
        .add_edge(process_optimized_cv, validator)
        .add_edge(validator, process_validation)

        # Validation routing (conditional)
        .add_edge(process_validation, handle_validation_success, condition=is_validation_success)
        .add_edge(process_validation, handle_validation_retry, condition=is_validation_retry)
        .add_edge(process_validation, handle_validation_failed, condition=is_validation_failed)

        # Retry loop: back to CV writer
        .add_edge(handle_validation_retry, cv_writer)

        # PDF Generation (from success or failed max retries)
        .add_edge(handle_validation_success, pdf_generator)
        .add_edge(handle_validation_failed, pdf_generator)
        .add_edge(pdf_generator, process_pdf_generated)

        # Summarization
        .add_edge(process_pdf_generated, summarizer)
        .add_edge(summarizer, finalize_workflow)

        .build()
    )

    return workflow


async def run_cv_optimization(
    vacancy_description: str,
    cv_pdf_path: str,
    output_path: str,
    background: str | None = None,
    verbose: bool = False,
) -> str:
    """
    Run the complete CV optimization workflow.

    Args:
        vacancy_description: The job vacancy description text.
        cv_pdf_path: Path to the original CV PDF file.
        output_path: Path where the optimized CV PDF should be saved.
        background: Optional additional background info to extend the CV.
        verbose: If True, print progress updates.

    Returns:
        The path to the generated PDF.
    """
    initialize()

    def log(message: str) -> None:
        if verbose:
            print(f"[CV Creator] {message}")

    try:
        log("=" * 60)
        log("CV OPTIMIZATION WORKFLOW")
        log("=" * 60)
        log(f"CV Input: {cv_pdf_path}")
        log(f"PDF Output: {output_path}")
        log(f"Vacancy: {len(vacancy_description)} characters")
        if background:
            log(f"Background: {len(background)} characters")
        log("")
        log("Building workflow with parallel execution...")
        log("Parallel branches:")
        log("  Branch 1: Company Extractor → Researcher")
        log("  Branch 2: CV Reader")
        log("Sequential after merge:")
        log("  CV Writer → Validator → PDF Generator → Summarizer")
        log("")

        # Create and run the workflow
        workflow = create_cv_optimization_workflow(cv_pdf_path, output_path)

        # Create workflow input
        workflow_input = WorkflowInput(
            vacancy_description=vacancy_description,
            cv_pdf_path=cv_pdf_path,
            output_path=output_path,
            background=background,
        )

        log("Executing workflow...")

        # Run workflow with streaming to see events
        last_executor = None
        async for event in workflow.run_stream(workflow_input):
            # Safely get executor_id if available
            executor_id = getattr(event, "executor_id", None)
            if verbose and executor_id and executor_id != last_executor:
                log(f"  → {executor_id}")
                last_executor = executor_id

            # Check event type safely
            event_type = getattr(event, "type", None)
            if event_type == "warning":
                log(f"  ⚠ Warning: {getattr(event, 'data', '')}")

            if event_type == "output":
                if verbose:
                    print("\n" + "-" * 60)
                    print("WORKFLOW OUTPUT:")
                    print("-" * 60)
                    print(getattr(event, "data", ""))

        log("")
        log("=" * 60)
        log("WORKFLOW COMPLETE")
        log("=" * 60)
        log(f"✓ Output: {output_path}")
        log(f"✓ Summary: {output_path}.summary.md")

        return output_path

    except Exception as e:
        error_msg = f"Error during CV optimization: {str(e)}"
        log(f"✗ {error_msg}")
        raise RuntimeError(error_msg) from e


def get_orchestrator_agent(cv_pdf_path: str, output_path: str) -> ChatAgent:
    """
    Get an orchestrator agent (for backward compatibility).

    Note: The new implementation uses workflows, but this function
    returns a simple agent wrapper for API compatibility.
    """
    # Parameters are kept for API compatibility but not used
    _ = cv_pdf_path, output_path
    return get_chat_client().create_agent(
        name="CV Optimization Orchestrator",
        instructions="This is a placeholder. Use run_cv_optimization() for the workflow-based implementation.",
    )
