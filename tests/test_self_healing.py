"""
Tests for the Self-Healing Code System.

These tests verify the core functionality of the self-healing framework,
including error detection, analysis, fixing, and validation.
"""

import pytest
import tempfile
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from self_healing.config import (
    SelfHealingConfig, ErrorType, EnvironmentType, FixStrategy,
    RetryConfig, LoggingConfig, SafetyConfig
)
from self_healing.detector import ErrorDetector, DetectedError, ErrorPatterns
from self_healing.analyzer import ErrorAnalyzer, FixSuggestion, FixConfidence
from self_healing.fixer import ErrorFixer, CodeTransformer
from self_healing.validator import FixValidator, ValidationLevel
from self_healing.logger import HealingLogger, HealingEvent, HealingEventType
from self_healing.orchestrator import SelfHealingOrchestrator


class TestSelfHealingConfig:
    """Tests for configuration management."""

    def test_default_config(self):
        """Test default configuration values."""
        config = SelfHealingConfig()

        assert config.enabled is True
        assert config.retry.max_attempts == 3
        assert config.safety.dry_run is False
        assert config.safety.backup_before_fix is True

    def test_config_to_dict_and_back(self):
        """Test config serialization."""
        config = SelfHealingConfig()
        config.retry.max_attempts = 5
        config.safety.dry_run = True

        data = config.to_dict()
        assert data["retry"]["max_attempts"] == 5
        assert data["safety"]["dry_run"] is True

    def test_protected_path_check(self):
        """Test protected path checking."""
        config = SelfHealingConfig()
        config.safety.protected_paths = ["/etc", "/usr"]

        assert config.is_path_protected("/etc/passwd") is True
        assert config.is_path_protected("/home/user/file.py") is False

    def test_allowed_command_check(self):
        """Test allowed command checking."""
        config = SelfHealingConfig()
        config.safety.allowed_external_commands = ["pip", "npm"]

        assert config.is_command_allowed("pip install requests") is True
        assert config.is_command_allowed("rm -rf /") is False


class TestErrorDetector:
    """Tests for error detection."""

    def test_detect_python_syntax_error(self):
        """Test Python syntax error detection."""
        detector = ErrorDetector()

        code = "def foo(\n    print('hello')"  # Missing colon and closing paren
        error = detector.validate_python_syntax(code)

        assert error is not None
        assert error.error_type == ErrorType.SYNTAX
        assert error.environment == EnvironmentType.PYTHON

    def test_detect_from_exception(self):
        """Test detection from Python exception."""
        detector = ErrorDetector()

        try:
            raise ValueError("Test error message")
        except Exception as e:
            error = detector.detect_from_exception(e)

        assert error.error_type == ErrorType.RUNTIME
        assert error.exception_type == "ValueError"
        assert "Test error message" in error.message

    def test_classify_import_error(self):
        """Test classification of import errors."""
        detector = ErrorDetector()

        error_type = detector.classify_error(
            "ModuleNotFoundError: No module named 'nonexistent'",
            EnvironmentType.PYTHON
        )

        assert error_type == ErrorType.DEPENDENCY

    def test_classify_network_error(self):
        """Test classification of network errors."""
        detector = ErrorDetector()

        error_type = detector.classify_error(
            "ConnectionError: Connection refused",
            EnvironmentType.PYTHON
        )

        assert error_type == ErrorType.NETWORK

    def test_detect_logic_issue(self):
        """Test detection of logic issues."""
        detector = ErrorDetector()

        error = detector.detect_logic_issues(
            expected=10,
            actual=5,
            description="Sum calculation"
        )

        assert error is not None
        assert error.error_type == ErrorType.LOGIC
        assert "expected 10" in error.message.lower()

    def test_detect_infinite_loop(self):
        """Test detection of potential infinite loops."""
        detector = ErrorDetector()

        error = detector.detect_infinite_loop(
            iteration_count=10001,
            max_iterations=10000,
            loop_description="Main processing loop"
        )

        assert error is not None
        assert error.error_type == ErrorType.LOGIC


class TestErrorAnalyzer:
    """Tests for error analysis."""

    def test_analyze_import_error(self):
        """Test analysis of import errors."""
        analyzer = ErrorAnalyzer()

        error = DetectedError(
            error_type=ErrorType.DEPENDENCY,
            environment=EnvironmentType.PYTHON,
            message="ModuleNotFoundError: No module named 'requests'",
            exception_type="ModuleNotFoundError"
        )

        result = analyzer.analyze(error)

        assert result.root_cause is not None
        assert len(result.suggestions) > 0
        assert any("install" in s.description.lower() for s in result.suggestions)

    def test_analyze_syntax_error(self):
        """Test analysis of syntax errors."""
        analyzer = ErrorAnalyzer()

        error = DetectedError(
            error_type=ErrorType.SYNTAX,
            environment=EnvironmentType.PYTHON,
            message="SyntaxError: expected ':'",
            exception_type="SyntaxError",
            line_number=10
        )

        result = analyzer.analyze(error)

        assert result.root_cause is not None
        assert len(result.suggestions) > 0

    def test_analyze_with_confidence(self):
        """Test that analysis includes confidence levels."""
        analyzer = ErrorAnalyzer()

        error = DetectedError(
            error_type=ErrorType.DEPENDENCY,
            environment=EnvironmentType.PYTHON,
            message="ModuleNotFoundError: No module named 'requests'"
        )

        result = analyzer.analyze(error)

        for suggestion in result.suggestions:
            assert suggestion.confidence in [
                FixConfidence.HIGH,
                FixConfidence.MEDIUM,
                FixConfidence.LOW,
                FixConfidence.EXPERIMENTAL
            ]


class TestCodeTransformer:
    """Tests for code transformation utilities."""

    def test_add_null_check(self):
        """Test adding null checks."""
        code = "result = data.process()"
        transformer = CodeTransformer()

        # The method expects line_number and variable
        fixed = transformer.add_null_check(code, "data", 1)

        assert "if data is not None:" in fixed

    def test_fix_indentation(self):
        """Test fixing indentation."""
        code = "\tdef foo():\n\t\tpass"
        transformer = CodeTransformer()

        fixed = transformer.fix_indentation(code, use_spaces=True, indent_size=4)

        assert "\t" not in fixed or "    " in fixed

    def test_add_import(self):
        """Test adding imports."""
        code = "def foo():\n    pass"
        transformer = CodeTransformer()

        fixed = transformer.add_import(code, "import os")

        assert "import os" in fixed

    def test_use_dict_get(self):
        """Test converting dict access to .get()."""
        code = "value = data['key']"
        transformer = CodeTransformer()

        fixed = transformer.use_dict_get(code, 1)

        assert ".get(" in fixed


class TestErrorFixer:
    """Tests for fix application."""

    def test_dry_run_command_fix(self):
        """Test dry run for command fixes."""
        config = SelfHealingConfig()
        config.safety.dry_run = True

        fixer = ErrorFixer(config=config)

        suggestion = FixSuggestion(
            description="Install requests",
            reasoning="Missing package",
            confidence=FixConfidence.HIGH,
            fix_type="command",
            command="pip install requests"
        )

        analysis_result = type('obj', (object,), {
            'error': DetectedError(
                error_type=ErrorType.DEPENDENCY,
                environment=EnvironmentType.PYTHON,
                message="No module named 'requests'"
            )
        })()

        result = fixer.apply_fix(suggestion, analysis_result)

        assert result.success is True
        assert "[DRY RUN]" in result.description

    def test_protected_path_rejection(self):
        """Test that protected paths are rejected."""
        config = SelfHealingConfig()
        config.safety.protected_paths = ["/etc"]

        fixer = ErrorFixer(config=config)

        suggestion = FixSuggestion(
            description="Modify file",
            reasoning="Test",
            confidence=FixConfidence.HIGH,
            fix_type="code_change",
            file_path="/etc/passwd"
        )

        analysis_result = type('obj', (object,), {
            'error': DetectedError(
                error_type=ErrorType.SYNTAX,
                environment=EnvironmentType.PYTHON,
                message="Test"
            )
        })()

        result = fixer.apply_fix(suggestion, analysis_result)

        assert result.success is False
        assert "protected" in result.description.lower()


class TestFixValidator:
    """Tests for fix validation."""

    def test_validate_python_syntax(self):
        """Test Python syntax validation."""
        validator = FixValidator()

        valid, error = validator.validate_code_string(
            "def foo():\n    pass",
            EnvironmentType.PYTHON
        )

        assert valid is True

    def test_validate_invalid_syntax(self):
        """Test validation of invalid syntax."""
        validator = FixValidator()

        valid, error = validator.validate_code_string(
            "def foo(\n    pass",
            EnvironmentType.PYTHON
        )

        assert valid is False


class TestHealingLogger:
    """Tests for logging and audit trail."""

    def test_logger_creates_directory(self):
        """Test that logger creates log directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = os.path.join(tmpdir, "logs")
            logger = HealingLogger(log_directory=log_dir)

            assert os.path.exists(log_dir)

    def test_new_incident_id(self):
        """Test incident ID generation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = HealingLogger(log_directory=tmpdir)
            incident_id = logger.new_incident()

            assert incident_id is not None
            assert len(incident_id) > 0

    def test_log_error_detected(self):
        """Test logging error detection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = HealingLogger(log_directory=tmpdir)
            incident_id = logger.new_incident()

            logger.log_error_detected(
                incident_id=incident_id,
                environment="python",
                error_type="syntax",
                error_message="Test error"
            )

            changelog = logger.get_changelog()
            assert len(changelog["incidents"]) > 0

    def test_get_statistics(self):
        """Test statistics calculation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = HealingLogger(log_directory=tmpdir)

            stats = logger.get_statistics()

            assert "total_incidents" in stats
            assert "successful_fixes" in stats
            assert "success_rate" in stats


class TestSelfHealingOrchestrator:
    """Tests for the main orchestrator."""

    def test_orchestrator_initialization(self):
        """Test orchestrator initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            orchestrator = SelfHealingOrchestrator(log_directory=tmpdir)

            assert orchestrator.config is not None
            assert orchestrator.detector is not None
            assert orchestrator.analyzer is not None

    def test_protect_decorator_normal_execution(self):
        """Test that protected functions work normally without errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            orchestrator = SelfHealingOrchestrator(log_directory=tmpdir)

            @orchestrator.protect
            def add(a, b):
                return a + b

            result = add(2, 3)
            assert result == 5

    def test_preview_fix(self):
        """Test fix preview generation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            orchestrator = SelfHealingOrchestrator(log_directory=tmpdir)

            error = DetectedError(
                error_type=ErrorType.DEPENDENCY,
                environment=EnvironmentType.PYTHON,
                message="ModuleNotFoundError: No module named 'requests'"
            )

            previews = orchestrator.preview_fix(error)

            assert len(previews) > 0
            assert "description" in previews[0]

    def test_disabled_orchestrator(self):
        """Test that disabled orchestrator doesn't heal."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = SelfHealingConfig()
            config.enabled = False

            orchestrator = SelfHealingOrchestrator(
                config=config,
                log_directory=tmpdir
            )

            error = DetectedError(
                error_type=ErrorType.SYNTAX,
                environment=EnvironmentType.PYTHON,
                message="Test error"
            )

            session = orchestrator.heal(error)
            assert session.final_result == "disabled"


class TestEnvironmentHandlers:
    """Tests for environment-specific handlers."""

    def test_python_environment_syntax_check(self):
        """Test Python environment syntax checking."""
        from self_healing.environments import PythonEnvironment

        env = PythonEnvironment()
        valid, error = env.validate_syntax("def foo():\n    pass")

        assert valid is True

    def test_python_environment_invalid_syntax(self):
        """Test Python environment with invalid syntax."""
        from self_healing.environments import PythonEnvironment

        env = PythonEnvironment()
        valid, error = env.validate_syntax("def foo(\n    pass")

        assert valid is False
        assert error is not None

    def test_bash_environment_command_check(self):
        """Test Bash environment command checking."""
        from self_healing.environments import BashEnvironment

        env = BashEnvironment()

        # 'ls' should exist on most systems
        assert env.check_command_exists("ls") is True
        # This shouldn't exist
        assert env.check_command_exists("nonexistent_command_xyz") is False


class TestIntegration:
    """Integration tests for the complete healing workflow."""

    def test_full_healing_workflow_dry_run(self):
        """Test complete healing workflow in dry-run mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = SelfHealingConfig()
            config.safety.dry_run = True
            config.logging.log_directory = tmpdir

            orchestrator = SelfHealingOrchestrator(config=config)

            error = DetectedError(
                error_type=ErrorType.DEPENDENCY,
                environment=EnvironmentType.PYTHON,
                message="ModuleNotFoundError: No module named 'requests'"
            )

            session = orchestrator.heal(error)

            assert session.incident_id is not None
            assert session.analysis is not None
            assert len(session.fix_attempts) > 0

    def test_error_detection_to_analysis_flow(self):
        """Test flow from detection to analysis."""
        with tempfile.TemporaryDirectory() as tmpdir:
            orchestrator = SelfHealingOrchestrator(log_directory=tmpdir)

            try:
                raise ValueError("Test value error")
            except Exception as e:
                error = orchestrator.detector.detect_from_exception(e)

            analysis = orchestrator.analyzer.analyze(error)

            assert error.exception_type == "ValueError"
            assert analysis.root_cause is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
