"""Unit tests for the CLI module.

Tests argument parsing, validation, and error handling.
Uses Click's CliRunner for isolated CLI testing.
"""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from guardian_stream.models import Article


class TestCLI:
    """Tests for the CLI interface."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a Click test runner.

        CliRunner provides isolated CLI testing:
        - Captures stdout/stderr
        - Simulates command-line invocation
        - Provides exit codes
        """
        return CliRunner()

    @pytest.fixture
    def mock_orchestrator_run(self) -> MagicMock:
        """Create a mock for orchestrator.run()."""
        mock = MagicMock()
        mock.return_value = {
            "articles_found": 5,
            "articles_published": 5,
        }
        return mock

    @pytest.fixture
    def env_vars(self) -> dict[str, str]:
        """Environment variables for testing."""
        return {
            "GUARDIAN_API_KEY": "test-api-key",
            "KINESIS_STREAM_NAME": "test-stream",
        }

    # =========================================================================
    # Argument Parsing Tests
    # =========================================================================

    def test_cli_requires_search_term(self, runner: CliRunner, env_vars: dict):
        """Missing search term should exit with error."""
        from guardian_stream.cli import main

        result = runner.invoke(main, [], env=env_vars)

        assert result.exit_code != 0
        assert "search_term" in result.output.lower() or "missing" in result.output.lower()

    def test_cli_accepts_search_term(
        self,
        runner: CliRunner,
        env_vars: dict,
        mock_orchestrator_run: MagicMock,
    ):
        """Search term should be passed to orchestrator."""
        from guardian_stream.cli import main

        with patch("guardian_stream.cli.run", mock_orchestrator_run):
            with patch("guardian_stream.cli.GuardianClient"):
                with patch("guardian_stream.cli.KinesisPublisher"):
                    result = runner.invoke(main, ["climate change"], env=env_vars)

        assert result.exit_code == 0

    def test_cli_accepts_optional_date(
        self,
        runner: CliRunner,
        env_vars: dict,
        mock_orchestrator_run: MagicMock,
    ):
        """--date-from should be optional and parsed correctly."""
        from guardian_stream.cli import main

        with patch("guardian_stream.cli.run", mock_orchestrator_run):
            with patch("guardian_stream.cli.GuardianClient"):
                with patch("guardian_stream.cli.KinesisPublisher"):
                    result = runner.invoke(
                        main,
                        ["climate", "--date-from", "2024-01-01"],
                        env=env_vars,
                    )

        assert result.exit_code == 0
        # Verify date was passed to orchestrator
        call_kwargs = mock_orchestrator_run.call_args.kwargs
        assert call_kwargs.get("date_from") == date(2024, 1, 1)

    def test_cli_validates_date_format(self, runner: CliRunner, env_vars: dict):
        """Invalid date should exit with helpful error."""
        from guardian_stream.cli import main

        result = runner.invoke(
            main,
            ["climate", "--date-from", "not-a-date"],
            env=env_vars,
        )

        assert result.exit_code != 0
        assert "date" in result.output.lower() or "invalid" in result.output.lower()

    # =========================================================================
    # Environment Variable Tests
    # =========================================================================

    def test_cli_requires_api_key_env_var(self, runner: CliRunner):
        """Missing GUARDIAN_API_KEY should exit with error."""
        from guardian_stream.cli import main

        env_without_key = {"KINESIS_STREAM_NAME": "test-stream"}
        result = runner.invoke(main, ["climate"], env=env_without_key)

        assert result.exit_code != 0

    def test_cli_requires_stream_name_env_var(self, runner: CliRunner):
        """Missing KINESIS_STREAM_NAME should exit with error."""
        from guardian_stream.cli import main

        env_without_stream = {"GUARDIAN_API_KEY": "test-key"}
        result = runner.invoke(main, ["climate"], env=env_without_stream)

        assert result.exit_code != 0

    # =========================================================================
    # Output Tests
    # =========================================================================

    def test_cli_displays_results(
        self,
        runner: CliRunner,
        env_vars: dict,
        mock_orchestrator_run: MagicMock,
    ):
        """CLI should display found and published counts."""
        from guardian_stream.cli import main

        mock_orchestrator_run.return_value = {
            "articles_found": 10,
            "articles_published": 10,
        }

        with patch("guardian_stream.cli.run", mock_orchestrator_run):
            with patch("guardian_stream.cli.GuardianClient"):
                with patch("guardian_stream.cli.KinesisPublisher"):
                    result = runner.invoke(main, ["technology"], env=env_vars)

        assert "10" in result.output
        assert result.exit_code == 0

    def test_cli_handles_no_results(
        self,
        runner: CliRunner,
        env_vars: dict,
        mock_orchestrator_run: MagicMock,
    ):
        """Zero articles should be reported, not error."""
        from guardian_stream.cli import main

        mock_orchestrator_run.return_value = {
            "articles_found": 0,
            "articles_published": 0,
        }

        with patch("guardian_stream.cli.run", mock_orchestrator_run):
            with patch("guardian_stream.cli.GuardianClient"):
                with patch("guardian_stream.cli.KinesisPublisher"):
                    result = runner.invoke(main, ["xyznonexistent"], env=env_vars)

        assert result.exit_code == 0
        assert "0" in result.output

    # =========================================================================
    # Error Handling Tests
    # =========================================================================

    def test_cli_handles_api_error_gracefully(
        self,
        runner: CliRunner,
        env_vars: dict,
    ):
        """Guardian API errors should show user-friendly message."""
        from guardian_stream.cli import main
        from guardian_stream.exceptions import GuardianAPIError

        mock_run = MagicMock()
        mock_run.side_effect = GuardianAPIError("API unavailable", status_code=503)

        with patch("guardian_stream.cli.run", mock_run):
            with patch("guardian_stream.cli.GuardianClient"):
                with patch("guardian_stream.cli.KinesisPublisher"):
                    result = runner.invoke(main, ["test"], env=env_vars)

        assert result.exit_code != 0
        # Should show error but not full traceback
        assert "error" in result.output.lower() or "failed" in result.output.lower()

    def test_cli_handles_publisher_error_gracefully(
        self,
        runner: CliRunner,
        env_vars: dict,
    ):
        """Kinesis errors should show user-friendly message."""
        from guardian_stream.cli import main
        from guardian_stream.exceptions import PublisherError

        mock_run = MagicMock()
        mock_run.side_effect = PublisherError("Stream unavailable")

        with patch("guardian_stream.cli.run", mock_run):
            with patch("guardian_stream.cli.GuardianClient"):
                with patch("guardian_stream.cli.KinesisPublisher"):
                    result = runner.invoke(main, ["test"], env=env_vars)

        assert result.exit_code != 0
