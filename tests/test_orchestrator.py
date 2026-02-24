"""Tests for the CV optimization orchestrator."""

from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cv_creator.agents.orchestrator import (
    MAX_VALIDATION_RETRIES,
    STATE_BACKGROUND,
    STATE_COMPANY_NAME,
    STATE_COMPANY_RESEARCH,
    STATE_CV_PDF_PATH,
    STATE_CV_READY,
    STATE_OPTIMIZED_CV,
    STATE_ORIGINAL_CV,
    STATE_OUTPUT_PATH,
    STATE_RESEARCH_READY,
    STATE_VACANCY,
    STATE_VALIDATION_ISSUES,
    STATE_VALIDATION_RETRIES,
    BranchComplete,
    BranchTrigger,
    ValidationStepResult,
    WorkflowInput,
    build_cv_writer_prompt,
    finalize_workflow as _finalize_workflow,
    handle_validation_failed as _handle_validation_failed,
    handle_validation_retry as _handle_validation_retry,
    handle_validation_success as _handle_validation_success,
    is_validation_failed,
    is_validation_retry,
    is_validation_success,
    merge_branches as _merge_branches,
    process_company_name as _process_company_name,
    process_cv_content as _process_cv_content,
    process_optimized_cv as _process_optimized_cv,
    process_pdf_generated as _process_pdf_generated,
    process_research as _process_research,
    process_validation as _process_validation,
    start_company_branch as _start_company_branch,
    start_cv_branch as _start_cv_branch,
    start_workflow as _start_workflow,
)

# The @executor decorator wraps functions into FunctionExecutor objects.
# Access the underlying async function via _original_func for direct testing.
start_workflow = _start_workflow._original_func
start_company_branch = _start_company_branch._original_func
start_cv_branch = _start_cv_branch._original_func
process_company_name = _process_company_name._original_func
process_research = _process_research._original_func
process_cv_content = _process_cv_content._original_func
merge_branches = _merge_branches._original_func
process_optimized_cv = _process_optimized_cv._original_func
process_validation = _process_validation._original_func
handle_validation_success = _handle_validation_success._original_func
handle_validation_retry = _handle_validation_retry._original_func
handle_validation_failed = _handle_validation_failed._original_func
process_pdf_generated = _process_pdf_generated._original_func
finalize_workflow = _finalize_workflow._original_func


# ============================================================================
# Helpers
# ============================================================================


def make_ctx(**state_overrides):
    """Create a mock WorkflowContext with configurable shared state."""
    state = {}
    state.update(state_overrides)

    ctx = AsyncMock()
    ctx.get_shared_state = AsyncMock(side_effect=lambda key: state.get(key))
    ctx.set_shared_state = AsyncMock(side_effect=lambda key, value: state.__setitem__(key, value))
    ctx.send_message = AsyncMock()
    ctx.add_event = AsyncMock()
    ctx.yield_output = AsyncMock()

    # Expose state dict for assertions
    ctx._state = state
    return ctx


def make_agent_response(text: str):
    """Create a mock AgentExecutorResponse."""
    response = MagicMock()
    response.agent_run_response.text = text
    return response


# ============================================================================
# 1. Pure Functions
# ============================================================================


class TestBuildCvWriterPrompt:
    def test_basic(self):
        prompt = build_cv_writer_prompt(
            original_cv="My CV",
            vacancy="Job posting",
            company_research="Company info",
        )
        assert "My CV" in prompt
        assert "Job posting" in prompt
        assert "Company info" in prompt
        assert "ADDITIONAL BACKGROUND" not in prompt
        assert "VALIDATION ISSUES" not in prompt

    def test_with_background(self):
        prompt = build_cv_writer_prompt(
            original_cv="CV",
            vacancy="Job",
            company_research="Research",
            background="Extra info",
        )
        assert "ADDITIONAL BACKGROUND" in prompt
        assert "Extra info" in prompt

    def test_with_validation_issues(self):
        prompt = build_cv_writer_prompt(
            original_cv="CV",
            vacancy="Job",
            company_research="Research",
            validation_issues="Issue 1\nIssue 2",
        )
        assert "VALIDATION ISSUES TO FIX" in prompt
        assert "Issue 1" in prompt

    def test_with_both(self):
        prompt = build_cv_writer_prompt(
            original_cv="CV",
            vacancy="Job",
            company_research="Research",
            background="Background",
            validation_issues="Fix this",
        )
        assert "ADDITIONAL BACKGROUND" in prompt
        assert "VALIDATION ISSUES TO FIX" in prompt


class TestIsValidationSuccess:
    def test_valid(self):
        assert is_validation_success(ValidationStepResult(valid=True, issues=[], retry_count=0))

    def test_invalid(self):
        assert not is_validation_success(ValidationStepResult(valid=False, issues=["x"], retry_count=0))

    def test_wrong_type(self):
        assert not is_validation_success("not a result")
        assert not is_validation_success(None)


class TestIsValidationRetry:
    def test_can_retry(self):
        result = ValidationStepResult(valid=False, issues=["x"], retry_count=0)
        assert is_validation_retry(result)

    def test_max_retries_reached(self):
        result = ValidationStepResult(valid=False, issues=["x"], retry_count=MAX_VALIDATION_RETRIES)
        assert not is_validation_retry(result)

    def test_valid_result(self):
        result = ValidationStepResult(valid=True, issues=[], retry_count=0)
        assert not is_validation_retry(result)


class TestIsValidationFailed:
    def test_max_retries(self):
        result = ValidationStepResult(valid=False, issues=["x"], retry_count=MAX_VALIDATION_RETRIES)
        assert is_validation_failed(result)

    def test_retries_remaining(self):
        result = ValidationStepResult(valid=False, issues=["x"], retry_count=MAX_VALIDATION_RETRIES - 1)
        assert not is_validation_failed(result)


# ============================================================================
# 2. Executor Functions
# ============================================================================


class TestStartWorkflow:
    @pytest.mark.asyncio
    async def test_sets_state_and_triggers(self):
        ctx = make_ctx()
        input_data = WorkflowInput(
            vacancy_description="Job desc",
            cv_pdf_path="/path/cv.pdf",
            output_path="/path/out.pdf",
            background="bg info",
        )

        await start_workflow(input_data, ctx)

        assert ctx._state[STATE_VACANCY] == "Job desc"
        assert ctx._state[STATE_CV_PDF_PATH] == "/path/cv.pdf"
        assert ctx._state[STATE_OUTPUT_PATH] == "/path/out.pdf"
        assert ctx._state[STATE_BACKGROUND] == "bg info"
        assert ctx._state[STATE_VALIDATION_RETRIES] == 0
        assert ctx._state[STATE_VALIDATION_ISSUES] == ""
        assert ctx._state[STATE_RESEARCH_READY] is False
        assert ctx._state[STATE_CV_READY] is False
        ctx.send_message.assert_awaited_once()
        msg = ctx.send_message.call_args[0][0]
        assert isinstance(msg, BranchTrigger)

    @pytest.mark.asyncio
    async def test_no_background_stores_empty_string(self):
        ctx = make_ctx()
        input_data = WorkflowInput(
            vacancy_description="Job",
            cv_pdf_path="/cv.pdf",
            output_path="/out.pdf",
            background=None,
        )
        await start_workflow(input_data, ctx)
        assert ctx._state[STATE_BACKGROUND] == ""


class TestStartCompanyBranch:
    @pytest.mark.asyncio
    async def test_sends_agent_request(self):
        ctx = make_ctx(**{STATE_VACANCY: "Senior Engineer at ACME"})
        await start_company_branch(BranchTrigger(), ctx)

        ctx.send_message.assert_awaited_once()
        msg = ctx.send_message.call_args[0][0]
        assert "Senior Engineer at ACME" in msg.messages[0].text


class TestStartCvBranch:
    @pytest.mark.asyncio
    async def test_sends_agent_request(self):
        ctx = make_ctx(**{STATE_CV_PDF_PATH: "/path/to/cv.pdf"})
        await start_cv_branch(BranchTrigger(), ctx)

        ctx.send_message.assert_awaited_once()
        msg = ctx.send_message.call_args[0][0]
        assert "/path/to/cv.pdf" in msg.messages[0].text


class TestProcessCompanyName:
    @pytest.mark.asyncio
    async def test_stores_name_and_sends_research(self):
        ctx = make_ctx(**{STATE_VACANCY: "Job at ACME Corp"})
        response = make_agent_response("  ACME Corp  ")

        await process_company_name(response, ctx)

        assert ctx._state[STATE_COMPANY_NAME] == "ACME Corp"
        ctx.send_message.assert_awaited_once()
        msg = ctx.send_message.call_args[0][0]
        assert "ACME Corp" in msg.messages[0].text


class TestProcessResearch:
    @pytest.mark.asyncio
    async def test_stores_research_and_signals_complete(self):
        ctx = make_ctx()
        response = make_agent_response("Company research data")

        await process_research(response, ctx)

        assert ctx._state[STATE_COMPANY_RESEARCH] == "Company research data"
        assert ctx._state[STATE_RESEARCH_READY] is True
        msg = ctx.send_message.call_args[0][0]
        assert isinstance(msg, BranchComplete)
        assert msg.branch == "company"


class TestProcessCvContent:
    @pytest.mark.asyncio
    async def test_stores_cv_and_signals_complete(self):
        ctx = make_ctx()
        response = make_agent_response("Original CV content")

        await process_cv_content(response, ctx)

        assert ctx._state[STATE_ORIGINAL_CV] == "Original CV content"
        assert ctx._state[STATE_CV_READY] is True
        msg = ctx.send_message.call_args[0][0]
        assert isinstance(msg, BranchComplete)
        assert msg.branch == "cv"


class TestMergeBranches:
    @pytest.mark.asyncio
    async def test_builds_prompt_and_sends(self):
        ctx = make_ctx(**{
            STATE_ORIGINAL_CV: "My CV",
            STATE_VACANCY: "Job posting",
            STATE_COMPANY_RESEARCH: "Research",
            STATE_BACKGROUND: "",
            STATE_VALIDATION_ISSUES: "",
        })
        branches = [BranchComplete("company"), BranchComplete("cv")]

        await merge_branches(branches, ctx)

        ctx.send_message.assert_awaited_once()
        msg = ctx.send_message.call_args[0][0]
        assert "My CV" in msg.messages[0].text
        assert "Job posting" in msg.messages[0].text


class TestProcessOptimizedCv:
    @pytest.mark.asyncio
    async def test_stores_cv_and_sends_validation(self):
        ctx = make_ctx(**{
            STATE_ORIGINAL_CV: "Original",
            STATE_BACKGROUND: "",
        })
        response = make_agent_response("Optimized CV")

        await process_optimized_cv(response, ctx)

        assert ctx._state[STATE_OPTIMIZED_CV] == "Optimized CV"
        ctx.send_message.assert_awaited_once()
        msg = ctx.send_message.call_args[0][0]
        assert "ORIGINAL CV:" in msg.messages[0].text
        assert "OPTIMIZED CV:" in msg.messages[0].text

    @pytest.mark.asyncio
    async def test_includes_background_in_validation(self):
        ctx = make_ctx(**{
            STATE_ORIGINAL_CV: "Original",
            STATE_BACKGROUND: "Background info",
        })
        response = make_agent_response("Optimized CV")

        await process_optimized_cv(response, ctx)

        msg = ctx.send_message.call_args[0][0]
        assert "ADDITIONAL BACKGROUND" in msg.messages[0].text
        assert "Background info" in msg.messages[0].text


class TestProcessValidation:
    @pytest.mark.asyncio
    async def test_sends_validation_step_result(self):
        ctx = make_ctx(**{STATE_VALIDATION_RETRIES: 1})
        response = make_agent_response('{"valid": false, "issues": ["Bad skill"]}')

        await process_validation(response, ctx)

        ctx.send_message.assert_awaited_once()
        msg = ctx.send_message.call_args[0][0]
        assert isinstance(msg, ValidationStepResult)
        assert msg.valid is False
        assert msg.issues == ["Bad skill"]
        assert msg.retry_count == 1


class TestHandleValidationSuccess:
    @pytest.mark.asyncio
    async def test_writes_content_and_sends_pdf_request(self, tmp_path):
        output_path = str(tmp_path / "cv.pdf")
        ctx = make_ctx(**{
            STATE_OPTIMIZED_CV: "Final CV content",
            STATE_OUTPUT_PATH: output_path,
        })
        result = ValidationStepResult(valid=True, issues=[], retry_count=0)

        await handle_validation_success(result, ctx)

        assert Path(output_path + ".content").read_text() == "Final CV content"
        ctx.send_message.assert_awaited_once()
        msg = ctx.send_message.call_args[0][0]
        assert output_path in msg.messages[0].text


class TestHandleValidationRetry:
    @pytest.mark.asyncio
    async def test_increments_retry_and_sends_rewrite(self):
        ctx = make_ctx(**{
            STATE_ORIGINAL_CV: "CV",
            STATE_VACANCY: "Job",
            STATE_COMPANY_RESEARCH: "Research",
            STATE_BACKGROUND: "",
        })
        result = ValidationStepResult(valid=False, issues=["Bad skill", "Wrong date"], retry_count=1)

        await handle_validation_retry(result, ctx)

        assert ctx._state[STATE_VALIDATION_RETRIES] == 2
        assert "Bad skill" in ctx._state[STATE_VALIDATION_ISSUES]
        ctx.send_message.assert_awaited_once()
        msg = ctx.send_message.call_args[0][0]
        assert "VALIDATION ISSUES TO FIX" in msg.messages[0].text


class TestHandleValidationFailed:
    @pytest.mark.asyncio
    async def test_writes_content_warns_and_sends_pdf(self, tmp_path):
        output_path = str(tmp_path / "cv.pdf")
        ctx = make_ctx(**{
            STATE_OPTIMIZED_CV: "Imperfect CV",
            STATE_OUTPUT_PATH: output_path,
        })
        result = ValidationStepResult(
            valid=False,
            issues=["Unresolvable issue"],
            retry_count=MAX_VALIDATION_RETRIES,
        )

        await handle_validation_failed(result, ctx)

        assert Path(output_path + ".content").read_text() == "Imperfect CV"
        ctx.add_event.assert_awaited_once()
        event = ctx.add_event.call_args[0][0]
        assert "WARNING" in str(event.data)
        assert "Unresolvable issue" in str(event.data)
        ctx.send_message.assert_awaited_once()


class TestProcessPdfGenerated:
    @pytest.mark.asyncio
    async def test_sends_summarization_request(self):
        ctx = make_ctx(**{
            STATE_ORIGINAL_CV: "Original CV",
            STATE_OPTIMIZED_CV: "Optimized CV",
            STATE_VACANCY: "Job posting here",
        })
        response = make_agent_response("PDF generated")

        await process_pdf_generated(response, ctx)

        ctx.send_message.assert_awaited_once()
        msg = ctx.send_message.call_args[0][0]
        assert "ORIGINAL CV:" in msg.messages[0].text
        assert "OPTIMIZED CV:" in msg.messages[0].text


class TestFinalizeWorkflow:
    @pytest.mark.asyncio
    async def test_writes_summary_and_yields_output(self, tmp_path):
        output_path = str(tmp_path / "cv.pdf")
        ctx = make_ctx(**{STATE_OUTPUT_PATH: output_path})
        response = make_agent_response("Summary of changes")

        await finalize_workflow(response, ctx)

        summary_path = Path(output_path + ".summary.md")
        assert summary_path.read_text() == "Summary of changes"
        ctx.yield_output.assert_awaited_once()
        output_str = ctx.yield_output.call_args[0][0]
        assert output_path in output_str
        assert str(summary_path) in output_str


# ============================================================================
# 3. Entry-point Functions
# ============================================================================


class TestRunFromContent:
    @pytest.mark.asyncio
    async def test_happy_path_content_only(self, tmp_path):
        content_file = tmp_path / "cv.pdf.content"
        content_file.write_text("CV text content")
        output_path = str(tmp_path / "cv.pdf")

        mock_pdf_agent = AsyncMock()
        mock_pdf_agent.run = AsyncMock()

        with (
            patch("cv_creator.agents.orchestrator.initialize"),
            patch("cv_creator.agents.orchestrator.get_pdf_generator_agent", return_value=mock_pdf_agent),
        ):
            from cv_creator.agents.orchestrator import run_from_content
            result = await run_from_content(str(content_file), output_path)

        assert result == output_path
        mock_pdf_agent.run.assert_awaited_once()
        assert "CV text content" in mock_pdf_agent.run.call_args[0][0]

    @pytest.mark.asyncio
    async def test_with_original_cv_and_vacancy(self, tmp_path):
        content_file = tmp_path / "cv.pdf.content"
        content_file.write_text("CV text content")
        output_path = str(tmp_path / "cv.pdf")

        mock_pdf_agent = AsyncMock()
        mock_pdf_agent.run = AsyncMock()
        mock_summarizer = AsyncMock()
        mock_summary_result = MagicMock()
        mock_summary_result.text = "Summary text"
        mock_summarizer.run = AsyncMock(return_value=mock_summary_result)

        with (
            patch("cv_creator.agents.orchestrator.initialize"),
            patch("cv_creator.agents.orchestrator.get_pdf_generator_agent", return_value=mock_pdf_agent),
            patch("cv_creator.agents.orchestrator.get_summarizer_agent", return_value=mock_summarizer),
            patch("cv_creator.tools.read_pdf", return_value="Original CV text"),
        ):
            from cv_creator.agents.orchestrator import run_from_content
            result = await run_from_content(
                str(content_file),
                output_path,
                original_cv_path="/path/to/original.pdf",
                vacancy_description="Job posting",
            )

        assert result == output_path
        mock_summarizer.run.assert_awaited_once()
        summary_path = Path(output_path + ".summary.md")
        assert summary_path.read_text() == "Summary text"

    @pytest.mark.asyncio
    async def test_empty_content_raises(self, tmp_path):
        content_file = tmp_path / "cv.pdf.content"
        content_file.write_text("   ")
        output_path = str(tmp_path / "cv.pdf")

        with (
            patch("cv_creator.agents.orchestrator.initialize"),
            pytest.raises(RuntimeError, match="Content file is empty"),
        ):
            from cv_creator.agents.orchestrator import run_from_content
            await run_from_content(str(content_file), output_path)


class TestRunCvOptimization:
    @pytest.mark.asyncio
    async def test_happy_path(self, tmp_path):
        output_path = str(tmp_path / "cv.pdf")

        # Mock the workflow to yield an output event
        mock_workflow = MagicMock()

        async def fake_stream(input_data):
            event = MagicMock()
            event.executor_id = "finalize_workflow"
            event.type = "output"
            event.data = f"CV optimization complete!\nPDF: {output_path}"
            yield event

        mock_workflow.run_stream = fake_stream

        with (
            patch("cv_creator.agents.orchestrator.initialize"),
            patch("cv_creator.agents.orchestrator.create_cv_optimization_workflow", return_value=mock_workflow),
        ):
            from cv_creator.agents.orchestrator import run_cv_optimization
            result = await run_cv_optimization(
                vacancy_description="Job desc",
                cv_pdf_path="/path/cv.pdf",
                output_path=output_path,
            )

        assert result == output_path

    @pytest.mark.asyncio
    async def test_workflow_error_wraps_in_runtime_error(self, tmp_path):
        output_path = str(tmp_path / "cv.pdf")

        mock_workflow = MagicMock()

        async def failing_stream(input_data):
            raise ValueError("Something went wrong")
            yield  # noqa: unreachable — makes this an async generator

        mock_workflow.run_stream = failing_stream

        with (
            patch("cv_creator.agents.orchestrator.initialize"),
            patch("cv_creator.agents.orchestrator.create_cv_optimization_workflow", return_value=mock_workflow),
            pytest.raises(RuntimeError, match="Something went wrong"),
        ):
            from cv_creator.agents.orchestrator import run_cv_optimization
            await run_cv_optimization(
                vacancy_description="Job desc",
                cv_pdf_path="/path/cv.pdf",
                output_path=output_path,
            )
