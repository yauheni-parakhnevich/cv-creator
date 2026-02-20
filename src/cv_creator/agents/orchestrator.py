"""Orchestrator Agent - Coordinates the CV optimization workflow using tools."""

from datetime import date
from pathlib import Path

from agents import Agent, Runner, function_tool

from cv_creator.config import get_model, initialize
from .company_extractor import get_company_extractor_agent
from .researcher import get_researcher_agent
from .cv_reader import get_cv_reader_agent
from .cv_writer import get_cv_writer_agent
from .validator import get_validator_agent, parse_validation_result
from .pdf_generator import get_pdf_generator_agent
from .summarizer import get_summarizer_agent


MAX_VALIDATION_RETRIES = 3


def create_orchestrator_tools(cv_pdf_path: str, output_path: str):
    """Create function tools that wrap each sub-agent for the orchestrator to use."""

    @function_tool
    async def extract_company_name(vacancy_description: str) -> str:
        """
        Extract the company name from a job vacancy description.

        Args:
            vacancy_description: The full text of the job vacancy.

        Returns:
            The extracted company name.
        """
        agent = get_company_extractor_agent()
        result = await Runner.run(
            agent,
            f"Extract the company name from this vacancy description:\n\n{vacancy_description}",
        )
        return result.final_output

    @function_tool
    async def research_company(company_name: str, vacancy_context: str) -> str:
        """
        Research a company to gather information for CV tailoring.

        Args:
            company_name: The name of the company to research.
            vacancy_context: Brief context from the job posting.

        Returns:
            Research findings about the company.
        """
        agent = get_researcher_agent()
        result = await Runner.run(
            agent,
            f"Research the company '{company_name}' and provide relevant information for tailoring a CV. "
            f"Context from job posting:\n{vacancy_context}",
        )
        return result.final_output

    @function_tool
    async def read_cv() -> str:
        """
        Read and extract text content from the original CV PDF.

        Returns:
            The extracted CV content as structured text.
        """
        agent = get_cv_reader_agent()
        result = await Runner.run(
            agent,
            f"Read and extract the content from the CV at: {cv_pdf_path}",
        )
        return result.final_output

    @function_tool
    async def write_optimized_cv(
        original_cv: str,
        vacancy_description: str,
        company_research: str,
        validation_issues: str = "",
    ) -> str:
        """
        Write an optimized CV tailored for the job.

        Args:
            original_cv: The original CV content.
            vacancy_description: The job vacancy description.
            company_research: Research findings about the company.
            validation_issues: Optional - issues from previous validation to fix.

        Returns:
            The optimized CV content.
        """
        agent = get_cv_writer_agent()
        current_date = date.today().strftime("%B %Y")
        prompt = f"""Create an optimized CV based on:

CURRENT DATE: {current_date}

ORIGINAL CV:
{original_cv}

JOB VACANCY:
{vacancy_description}

COMPANY RESEARCH:
{company_research}
"""
        if validation_issues:
            prompt += f"""
VALIDATION ISSUES TO FIX:
{validation_issues}

Please fix these issues while maintaining the quality of the CV.
"""
        result = await Runner.run(agent, prompt)
        return result.final_output

    @function_tool
    async def validate_cv(original_cv: str, optimized_cv: str) -> str:
        """
        Validate the optimized CV to ensure no hallucinations.

        Args:
            original_cv: The original CV content.
            optimized_cv: The optimized CV content to validate.

        Returns:
            JSON with 'valid' (bool) and 'issues' (list of strings).
        """
        agent = get_validator_agent()
        result = await Runner.run(
            agent,
            f"""Validate the optimized CV against the original.

ORIGINAL CV:
{original_cv}

OPTIMIZED CV:
{optimized_cv}
""",
        )
        # Parse and return structured result
        parsed = parse_validation_result(result.final_output)
        if parsed.valid:
            return '{"valid": true, "issues": []}'
        else:
            issues_str = ", ".join(f'"{issue}"' for issue in parsed.issues)
            return f'{{"valid": false, "issues": [{issues_str}]}}'

    @function_tool
    async def generate_cv_pdf(cv_content: str) -> str:
        """
        Generate a PDF from the optimized CV content.

        Args:
            cv_content: The optimized CV content to convert to PDF.

        Returns:
            Confirmation message with the output path.
        """
        agent = get_pdf_generator_agent()
        await Runner.run(
            agent,
            f"""Convert the following CV content into a professional PDF.

CV CONTENT:
{cv_content}

OUTPUT PATH: {output_path}
""",
        )
        return f"PDF successfully generated at: {output_path}"

    @function_tool
    async def summarize_changes(
        original_cv: str,
        optimized_cv: str,
        vacancy_description: str,
    ) -> str:
        """
        Create a summary of changes made to the CV.

        Args:
            original_cv: The original CV content.
            optimized_cv: The optimized CV content.
            vacancy_description: The job vacancy for context.

        Returns:
            A markdown summary of the changes made.
        """
        agent = get_summarizer_agent()
        result = await Runner.run(
            agent,
            f"""Compare these two CV versions and summarize the changes made.

TARGET JOB:
{vacancy_description[:1000]}

ORIGINAL CV:
{original_cv}

OPTIMIZED CV:
{optimized_cv}

Provide a clear summary of what was changed and why.""",
        )
        # Save the summary to file
        summary_path = Path(output_path + ".summary.md")
        summary_path.write_text(result.final_output)
        return f"Summary saved to {summary_path}:\n\n{result.final_output}"

    return [
        extract_company_name,
        research_company,
        read_cv,
        write_optimized_cv,
        validate_cv,
        generate_cv_pdf,
        summarize_changes,
    ]


def create_orchestrator_agent(cv_pdf_path: str, output_path: str) -> Agent:
    """
    Create the orchestrator agent with tools for coordinating sub-agents.
    """
    tools = create_orchestrator_tools(cv_pdf_path, output_path)

    return Agent(
        name="CV Optimization Orchestrator",
        instructions=f"""You are the orchestrator for a CV optimization workflow. You have tools to delegate work to specialized agents.

## CONFIGURATION
- CV PDF Path: {cv_pdf_path}
- Output PDF Path: {output_path}
- Max Validation Retries: {MAX_VALIDATION_RETRIES}

## AVAILABLE TOOLS
1. `extract_company_name` - Get company name from vacancy
2. `research_company` - Research company information
3. `read_cv` - Read the original CV PDF
4. `write_optimized_cv` - Create optimized CV content
5. `validate_cv` - Check CV for hallucinations
6. `generate_cv_pdf` - Create the final PDF
7. `summarize_changes` - Document what changed

## WORKFLOW - Execute in this order:

### Step 1: Extract Company
Call `extract_company_name` with the vacancy description.

### Step 2: Research Company
Call `research_company` with the company name and vacancy context.

### Step 3: Read Original CV
Call `read_cv` to get the original CV content.

### Step 4: Write Optimized CV
Call `write_optimized_cv` with:
- original_cv: from step 3
- vacancy_description: the full vacancy
- company_research: from step 2

### Step 5: Validate CV
Call `validate_cv` with original and optimized CV.
- If valid=false, call `write_optimized_cv` again with the issues
- Retry up to {MAX_VALIDATION_RETRIES} times

### Step 6: Generate PDF
Call `generate_cv_pdf` with the validated CV content.

### Step 7: Summarize Changes
Call `summarize_changes` with original CV, optimized CV, and vacancy.

## IMPORTANT
- Execute steps IN ORDER
- Store results from each step to use in later steps
- If validation fails, include the issues when rewriting
- Report final status when complete""",
        model=get_model(),
        tools=tools,
    )


async def run_cv_optimization(
    vacancy_description: str,
    cv_pdf_path: str,
    output_path: str,
    verbose: bool = False,
) -> str:
    """
    Run the complete CV optimization workflow using the orchestrator agent.

    Args:
        vacancy_description: The job vacancy description text.
        cv_pdf_path: Path to the original CV PDF file.
        output_path: Path where the optimized CV PDF should be saved.
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
        log("")
        log("Starting Orchestrator Agent with tools...")
        log("Tools available:")
        log("  • extract_company_name")
        log("  • research_company")
        log("  • read_cv")
        log("  • write_optimized_cv")
        log("  • validate_cv")
        log("  • generate_cv_pdf")
        log("  • summarize_changes")
        log("")

        # Create and run the orchestrator
        orchestrator = create_orchestrator_agent(cv_pdf_path, output_path)

        result = await Runner.run(
            orchestrator,
            f"""Execute the complete CV optimization workflow.

VACANCY DESCRIPTION:
{vacancy_description}

Follow all steps in order using the available tools.""",
        )

        log("")
        log("=" * 60)
        log("WORKFLOW COMPLETE")
        log("=" * 60)
        log(f"✓ Output: {output_path}")
        log(f"✓ Summary: {output_path}.summary.md")

        if verbose:
            print("\n" + "-" * 60)
            print("ORCHESTRATOR FINAL OUTPUT:")
            print("-" * 60)
            print(result.final_output[:1500] + "..." if len(result.final_output) > 1500 else result.final_output)

        return output_path

    except Exception as e:
        error_msg = f"Error during CV optimization: {str(e)}"
        log(f"✗ {error_msg}")
        raise RuntimeError(error_msg) from e


def get_orchestrator_agent(cv_pdf_path: str, output_path: str) -> Agent:
    """Get the orchestrator agent configured for a specific task."""
    return create_orchestrator_agent(cv_pdf_path, output_path)
