"""Tests for the validation result parser."""


from cv_creator.agents.validator import ValidationResult, parse_validation_result


class TestParseValidationResult:
    """Tests for parse_validation_result()."""

    # --- Passthrough ---

    def test_passthrough_existing_validation_result(self):
        original = ValidationResult(valid=True, issues=[])
        result = parse_validation_result(original)
        assert result is original

    def test_passthrough_with_issues(self):
        original = ValidationResult(valid=False, issues=["bad title"])
        result = parse_validation_result(original)
        assert result is original

    # --- Valid JSON strings ---

    def test_valid_json_no_issues(self):
        result = parse_validation_result('{"valid": true, "issues": []}')
        assert result.valid is True
        assert result.issues == []

    def test_valid_json_with_issues(self):
        raw = '{"valid": false, "issues": ["Added Kubernetes skill not in source", "Changed job title"]}'
        result = parse_validation_result(raw)
        assert result.valid is False
        assert len(result.issues) == 2
        assert "Kubernetes" in result.issues[0]

    def test_valid_json_with_surrounding_whitespace(self):
        result = parse_validation_result('  \n {"valid": true, "issues": []} \n ')
        assert result.valid is True

    # --- Markdown code block wrapping ---

    def test_json_in_markdown_code_block(self):
        raw = '```json\n{"valid": true, "issues": []}\n```'
        result = parse_validation_result(raw)
        assert result.valid is True
        assert result.issues == []

    def test_json_in_plain_code_block(self):
        raw = '```\n{"valid": false, "issues": ["fabricated degree"]}\n```'
        result = parse_validation_result(raw)
        assert result.valid is False
        assert result.issues == ["fabricated degree"]

    def test_code_block_with_multiple_json_lines(self):
        raw = (
            "```json\n"
            "{\n"
            '  "valid": false,\n'
            '  "issues": ["issue one", "issue two"]\n'
            "}\n"
            "```"
        )
        result = parse_validation_result(raw)
        assert result.valid is False
        assert len(result.issues) == 2

    def test_code_block_without_closing_fence(self):
        raw = '```json\n{"valid": true, "issues": []}'
        result = parse_validation_result(raw)
        assert result.valid is True

    # --- Malformed / unparseable input ---

    def test_plain_text_returns_invalid_with_message(self):
        result = parse_validation_result("Looks good to me!")
        assert result.valid is False
        assert len(result.issues) == 1
        assert "Failed to parse" in result.issues[0]

    def test_empty_string_returns_invalid(self):
        result = parse_validation_result("")
        assert result.valid is False
        assert "Failed to parse" in result.issues[0]

    def test_partial_json_returns_invalid(self):
        result = parse_validation_result('{"valid": true, "issues": [')
        assert result.valid is False
        assert "Failed to parse" in result.issues[0]

    def test_json_missing_required_field(self):
        """JSON is valid but doesn't match ValidationResult schema."""
        result = parse_validation_result('{"valid": true}')
        # Pydantic will raise a ValidationError, caught by the except branch
        assert result.valid is False
        assert "Failed to parse" in result.issues[0]

    def test_json_wrong_types(self):
        result = parse_validation_result('{"valid": "yes", "issues": "none"}')
        # Pydantic may coerce or reject — either way should not raise
        # If pydantic coerces "yes" to truthy, that's acceptable; if it rejects, we get Failed to parse
        assert isinstance(result, ValidationResult)
