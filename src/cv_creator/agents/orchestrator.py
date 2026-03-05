"""Orchestrator - Coordinates the CV optimization workflow using Microsoft Agent Framework Workflows."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Never

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

from cv_creator.config import get_chat_client, initialize

from .company_extractor import get_company_extractor_agent
from .cover_letter_writer import get_cover_letter_writer_agent
from .cv_reader import get_cv_reader_agent
from .cv_writer import get_cv_writer_agent
from .pdf_generator import get_document_generator_agent, get_pdf_generator_agent
from .researcher import get_researcher_agent
from .summarizer import get_summarizer_agent
from .validator import get_validator_agent, parse_validation_result

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
STATE_OUTPUT_FORMAT = "output_format"
STATE_CV_STYLE = "cv_style"
STATE_COVER_LETTER = "cover_letter"
STATE_COVER_LETTER_PATH = "cover_letter_path"


@dataclass
class WorkflowInput:
    """Input to start the CV optimization workflow."""
    vacancy_description: str
    cv_pdf_path: str
    output_path: str
    background: str | None = None
    output_format: str = "pdf"
    cv_style: str = "executive"


@dataclass
class BranchTrigger:
    """Trigger message for parallel branches."""
    pass


@dataclass
class BranchComplete:
    """Signal that a parallel branch has completed."""
    branch: str


@dataclass
class DocumentBranchTrigger:
    """Trigger message for document generation fan-out (CV doc + cover letter)."""
    pass


@dataclass
class DocumentBranchComplete:
    """Signal that a document generation branch has completed."""
    branch: str


@dataclass
class ValidationStepResult:
    """Result from validation step with retry logic."""
    valid: bool
    issues: list[str]
    retry_count: int


# ============================================================================
# Prompt Builders
# ============================================================================

def build_cv_writer_prompt(
    original_cv: str,
    vacancy: str,
    company_research: str,
    background: str = "",
    validation_issues: str = "",
) -> str:
    """Build the prompt for the CV writer agent."""
    current_date = date.today().strftime("%B %Y")

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

    return prompt


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
    await ctx.set_shared_state(STATE_OUTPUT_FORMAT, input_data.output_format)
    await ctx.set_shared_state(STATE_CV_STYLE, input_data.cv_style)
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

    prompt = build_cv_writer_prompt(
        original_cv=original_cv,
        vacancy=vacancy,
        company_research=company_research,
        background=background,
        validation_issues=validation_issues,
    )

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
    result: ValidationStepResult, ctx: WorkflowContext[DocumentBranchTrigger]
) -> None:
    """Validation passed - save content and trigger document generation fan-out."""
    _ = result  # Used for type routing
    optimized_cv = await ctx.get_shared_state(STATE_OPTIMIZED_CV)
    output_path = await ctx.get_shared_state(STATE_OUTPUT_PATH)

    # Save finalized CV content before document generation
    Path(output_path + ".content").write_text(optimized_cv)

    # Compute cover letter output path
    output = Path(output_path)
    ext = output.suffix  # .pdf or .docx
    cl_stem = output.stem.replace("optimized_cv", "cover_letter") if "optimized_cv" in output.stem else f"{output.stem}.cover_letter"
    cl_output_path = str(output.parent / f"{cl_stem}{ext}")
    await ctx.set_shared_state(STATE_COVER_LETTER_PATH, cl_output_path)

    # Trigger document generation fan-out
    await ctx.send_message(DocumentBranchTrigger())


@executor(id="handle_validation_retry")
async def handle_validation_retry(
    result: ValidationStepResult, ctx: WorkflowContext[AgentExecutorRequest]
) -> None:
    """Validation failed - retry CV writing with issues."""
    # Update retry count and store issues
    new_retry_count = result.retry_count + 1
    validation_issues = "\n".join(result.issues)
    await ctx.set_shared_state(STATE_VALIDATION_RETRIES, new_retry_count)
    await ctx.set_shared_state(STATE_VALIDATION_ISSUES, validation_issues)

    # Get data for rewriting
    original_cv = await ctx.get_shared_state(STATE_ORIGINAL_CV)
    vacancy = await ctx.get_shared_state(STATE_VACANCY)
    company_research = await ctx.get_shared_state(STATE_COMPANY_RESEARCH)
    background = await ctx.get_shared_state(STATE_BACKGROUND) or ""

    prompt = build_cv_writer_prompt(
        original_cv=original_cv,
        vacancy=vacancy,
        company_research=company_research,
        background=background,
        validation_issues=validation_issues,
    )

    # Send back to CV writer agent
    await ctx.send_message(
        AgentExecutorRequest(
            messages=[ChatMessage(role="user", text=prompt)],
            should_respond=True,
        )
    )


@executor(id="handle_validation_failed")
async def handle_validation_failed(
    result: ValidationStepResult, ctx: WorkflowContext[Never, str]
) -> None:
    """Validation failed after max retries - save content and exit workflow."""
    optimized_cv = await ctx.get_shared_state(STATE_OPTIMIZED_CV)
    output_path = await ctx.get_shared_state(STATE_OUTPUT_PATH)

    # Save whatever we have so the user can regenerate later with --from-content
    Path(output_path + ".content").write_text(optimized_cv)

    issues = "\n".join(result.issues)
    await ctx.yield_output(
        f"CV optimization FAILED after {MAX_VALIDATION_RETRIES} validation retries.\n"
        f"Validation issues:\n{issues}\n\n"
        f"Content saved to: {output_path}.content\n"
        f"You can retry document generation with: cv-creator --from-content {output_path}.content -o {output_path}"
    )


@executor(id="start_cv_doc_branch")
async def start_cv_doc_branch(
    trigger: DocumentBranchTrigger, ctx: WorkflowContext[AgentExecutorRequest]
) -> None:
    """Start the CV document generation branch."""
    _ = trigger
    optimized_cv = await ctx.get_shared_state(STATE_OPTIMIZED_CV)
    output_path = await ctx.get_shared_state(STATE_OUTPUT_PATH)

    await ctx.send_message(
        AgentExecutorRequest(
            messages=[ChatMessage(role="user", text=
                f"""Convert the following CV content into a professional document.

CV CONTENT:
{optimized_cv}

OUTPUT PATH: {output_path}
"""
            )],
            should_respond=True,
        )
    )


@executor(id="process_cv_doc_generated")
async def process_cv_doc_generated(
    response: AgentExecutorResponse, ctx: WorkflowContext[DocumentBranchComplete]
) -> None:
    """CV document generated - signal branch completion."""
    _ = response
    await ctx.send_message(DocumentBranchComplete(branch="cv_doc"))


@executor(id="start_cover_letter_branch")
async def start_cover_letter_branch(
    trigger: DocumentBranchTrigger, ctx: WorkflowContext[AgentExecutorRequest]
) -> None:
    """Start the cover letter generation branch."""
    _ = trigger
    optimized_cv = await ctx.get_shared_state(STATE_OPTIMIZED_CV)
    vacancy = await ctx.get_shared_state(STATE_VACANCY)
    company_name = await ctx.get_shared_state(STATE_COMPANY_NAME) or "the company"

    current_date = date.today().strftime("%B %d, %Y")
    await ctx.send_message(
        AgentExecutorRequest(
            messages=[ChatMessage(role="user", text=
                f"""Write a cover letter for this candidate.

CURRENT DATE: {current_date}

COMPANY: {company_name}

JOB VACANCY:
{vacancy}

CANDIDATE'S CV:
{optimized_cv}
"""
            )],
            should_respond=True,
        )
    )


@executor(id="process_cover_letter")
async def process_cover_letter(
    response: AgentExecutorResponse, ctx: WorkflowContext[AgentExecutorRequest]
) -> None:
    """Store cover letter text and trigger document rendering."""
    cover_letter_text = response.agent_run_response.text
    await ctx.set_shared_state(STATE_COVER_LETTER, cover_letter_text)

    cl_output_path = await ctx.get_shared_state(STATE_COVER_LETTER_PATH)
    # Save cover letter content file
    Path(cl_output_path + ".content").write_text(cover_letter_text)

    await ctx.send_message(
        AgentExecutorRequest(
            messages=[ChatMessage(role="user", text=
                f"""Convert the following COVER LETTER (not a CV) into a professional document.

This is a cover letter — format it as a simple business letter. Do NOT apply CV formatting
(no role-header divs, no experience sections, no competencies sections).
Use clean paragraph formatting with the header/contact info at the top, then flowing paragraphs.

COVER LETTER CONTENT:
{cover_letter_text}

OUTPUT PATH: {cl_output_path}
"""
            )],
            should_respond=True,
        )
    )


@executor(id="process_cover_letter_doc")
async def process_cover_letter_doc(
    response: AgentExecutorResponse, ctx: WorkflowContext[DocumentBranchComplete]
) -> None:
    """Cover letter document generated - signal branch completion."""
    _ = response
    await ctx.send_message(DocumentBranchComplete(branch="cover_letter"))


@executor(id="merge_document_branches")
async def merge_document_branches(
    branches: list[DocumentBranchComplete], ctx: WorkflowContext[AgentExecutorRequest]
) -> None:
    """Fan-in from both document branches, then trigger summarization."""
    _ = branches
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
    cl_output_path = await ctx.get_shared_state(STATE_COVER_LETTER_PATH)
    summary_path = Path(output_path + ".summary.md")
    summary_path.write_text(response.agent_run_response.text)

    msg = (
        f"CV optimization complete!\n"
        f"CV: {output_path}\n"
        f"Cover letter: {cl_output_path}\n"
        f"Summary: {summary_path}"
    )
    await ctx.yield_output(msg)


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

def create_cv_optimization_workflow(cv_pdf_path: str, output_path: str, output_format: str = "pdf", cv_style: str = "executive"):
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
        get_cv_writer_agent(cv_style),
        id="cv_writer_agent",
    )
    validator = AgentExecutor(
        get_validator_agent(),
        id="validator_agent",
    )
    pdf_generator = AgentExecutor(
        get_document_generator_agent(output_format, cv_style),
        id="pdf_generator_agent",
    )
    cover_letter_writer = AgentExecutor(
        get_cover_letter_writer_agent(cv_style),
        id="cover_letter_writer_agent",
    )
    cl_doc_generator = AgentExecutor(
        get_document_generator_agent(output_format, cv_style),
        id="cl_doc_generator_agent",
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

        # Document generation fan-out (from validation success only)
        .add_fan_out_edges(handle_validation_success, [start_cv_doc_branch, start_cover_letter_branch])

        # Validation failed after max retries → exits workflow (no outgoing edges)

        # CV document branch
        .add_edge(start_cv_doc_branch, pdf_generator)
        .add_edge(pdf_generator, process_cv_doc_generated)

        # Cover letter branch
        .add_edge(start_cover_letter_branch, cover_letter_writer)
        .add_edge(cover_letter_writer, process_cover_letter)
        .add_edge(process_cover_letter, cl_doc_generator)
        .add_edge(cl_doc_generator, process_cover_letter_doc)

        # Fan-in both document branches
        .add_fan_in_edges([process_cv_doc_generated, process_cover_letter_doc], merge_document_branches)

        # Summarization
        .add_edge(merge_document_branches, summarizer)
        .add_edge(summarizer, finalize_workflow)

        .build()
    )

    return workflow


async def run_from_content(
    content_path: str,
    output_path: str,
    original_cv_path: str | None = None,
    vacancy_description: str | None = None,
    verbose: bool = False,
    output_format: str = "pdf",
    cv_style: str = "executive",
) -> str:
    """
    Generate document and summary from an existing .content file.

    Args:
        content_path: Path to the .content file with finalized CV text.
        output_path: Path where the output document should be saved.
        original_cv_path: Optional path to original CV PDF (for summary generation).
        vacancy_description: Optional vacancy text (for summary generation).
        verbose: If True, print progress updates.
        output_format: Output format, either "pdf" or "docx".
        cv_style: CV style, either "executive" or "normal".

    Returns:
        The path to the generated document.
    """
    initialize()

    def log(message: str) -> None:
        if verbose:
            print(f"[CV Creator] {message}")

    cv_content = Path(content_path).read_text()
    if not cv_content.strip():
        raise RuntimeError(f"Content file is empty: {content_path}")

    # Compute cover letter output path
    output = Path(output_path)
    ext = output.suffix  # .pdf or .docx
    cl_stem = output.stem.replace("optimized_cv", "cover_letter") if "optimized_cv" in output.stem else f"{output.stem}.cover_letter"
    cl_output_path = str(output.parent / f"{cl_stem}{ext}")

    log(f"Generating {output_format.upper()} from content file...")
    log(f"  Content: {content_path}")
    log(f"  Output: {output_path}")
    log(f"  Cover letter: {cl_output_path}")

    # Document generation (CV)
    pdf_agent = get_document_generator_agent(output_format, cv_style)
    await pdf_agent.run(
        f"""Convert the following CV content into a professional document.

CV CONTENT:
{cv_content}

OUTPUT PATH: {output_path}
"""
    )
    log(f"  CV {output_format.upper()} generated.")

    # Cover letter generation
    if vacancy_description:
        try:
            cl_agent = get_cover_letter_writer_agent(cv_style)
            current_date = date.today().strftime("%B %d, %Y")
            cl_result = await cl_agent.run(
                f"""Write a cover letter for this candidate.

CURRENT DATE: {current_date}

JOB VACANCY:
{vacancy_description}

CANDIDATE'S CV:
{cv_content}
"""
            )
            cover_letter_text = cl_result.text
            Path(cl_output_path + ".content").write_text(cover_letter_text)

            cl_doc_agent = get_document_generator_agent(output_format, cv_style)
            await cl_doc_agent.run(
                f"""Convert the following COVER LETTER (not a CV) into a professional document.

This is a cover letter — format it as a simple business letter. Do NOT apply CV formatting
(no role-header divs, no experience sections, no competencies sections).
Use clean paragraph formatting with the header/contact info at the top, then flowing paragraphs.

COVER LETTER CONTENT:
{cover_letter_text}

OUTPUT PATH: {cl_output_path}
"""
            )
            log(f"  Cover letter {output_format.upper()} generated.")
        except Exception as e:
            log(f"  Cover letter generation failed: {e}")

    # Summary generation (if original CV and vacancy are available)
    if original_cv_path and vacancy_description:
        from cv_creator.tools import read_pdf
        original_cv = read_pdf(original_cv_path)

        summarizer = get_summarizer_agent()
        summary_result = await summarizer.run(
            f"""Compare these two CV versions and summarize the changes made.

TARGET JOB:
{vacancy_description[:1000]}

ORIGINAL CV:
{original_cv}

OPTIMIZED CV:
{cv_content}

Provide a clear summary of what was changed and why."""
        )
        summary_path = Path(output_path + ".summary.md")
        summary_path.write_text(summary_result.text)
        log(f"  Summary: {summary_path}")

    log("Done.")
    return output_path


async def run_cv_optimization(
    vacancy_description: str,
    cv_pdf_path: str,
    output_path: str,
    background: str | None = None,
    verbose: bool = False,
    output_format: str = "pdf",
    cv_style: str = "executive",
) -> str:
    """
    Run the complete CV optimization workflow.

    Args:
        vacancy_description: The job vacancy description text.
        cv_pdf_path: Path to the original CV PDF file.
        output_path: Path where the optimized CV document should be saved.
        background: Optional additional background info to extend the CV.
        verbose: If True, print progress updates.
        output_format: Output format, either "pdf" or "docx".
        cv_style: CV style, either "executive" or "normal".

    Returns:
        The path to the generated document.
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
        log(f"Output ({output_format.upper()}): {output_path}")
        log(f"Vacancy: {len(vacancy_description)} characters")
        if background:
            log(f"Background: {len(background)} characters")
        log("")
        log("Building workflow with parallel execution...")
        log("Parallel branches:")
        log("  Branch 1: Company Extractor → Researcher")
        log("  Branch 2: CV Reader")
        log("Sequential after merge:")
        log("  CV Writer → Validator → [CV Doc + Cover Letter] → Summarizer")
        log("")

        # Create and run the workflow
        workflow = create_cv_optimization_workflow(cv_pdf_path, output_path, output_format, cv_style)

        # Create workflow input
        workflow_input = WorkflowInput(
            vacancy_description=vacancy_description,
            cv_pdf_path=cv_pdf_path,
            output_path=output_path,
            background=background,
            output_format=output_format,
            cv_style=cv_style,
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
        log(f"✓ Content: {output_path}.content")
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
