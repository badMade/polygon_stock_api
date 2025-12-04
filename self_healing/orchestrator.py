"""
Self-Healing Orchestrator Module
================================

This module provides the main orchestrator that coordinates all components
of the self-healing system. It manages the complete workflow from error
detection through fix application and validation.

Workflow:
---------
1. Error Detection -> Captured by detector or exception hooks
2. Error Analysis -> Determine root cause and generate fix suggestions
3. Fix Selection -> Choose the best fix based on confidence
4. Fix Application -> Apply the fix (with backup)
5. Validation -> Verify the fix works
6. Retry Loop -> If validation fails, try next suggestion
7. Logging -> Record all actions in the changelog

Features:
---------
- Decorator for protecting functions
- Context manager for protected code blocks
- Global exception hook installation
- CLI integration
- Configurable retry behavior
"""

import sys
import time
import functools
import traceback
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Optional, Callable, Any, List, Dict
from pathlib import Path

from .config import (
    SelfHealingConfig, get_config, set_config,
    ErrorType, EnvironmentType
)
from .logger import HealingLogger
from .detector import ErrorDetector, DetectedError
from .analyzer import ErrorAnalyzer, AnalysisResult, FixSuggestion
from .fixer import ErrorFixer, FixResult
from .validator import FixValidator, ValidationResult, ValidationLevel


@dataclass
class HealingSession:
    """
    Represents a single healing session for an error.

    Tracks all attempts and results for a specific error incident.
    """
    incident_id: str
    original_error: DetectedError
    analysis: Optional[AnalysisResult] = None
    fix_attempts: List[Dict[str, Any]] = field(default_factory=list)
    final_result: Optional[str] = None  # "success", "failed", "manual_required"
    total_attempts: int = 0


class SelfHealingOrchestrator:
    """
    Main orchestrator for the self-healing code system.

    This class coordinates all components and provides the main interface
    for enabling self-healing capabilities in your code.

    Usage:
        # Option 1: Decorator
        healer = SelfHealingOrchestrator()

        @healer.protect
        def my_function():
            pass

        # Option 2: Context manager
        with healer.healing_context():
            risky_code()

        # Option 3: Run a script with healing
        healer.run_script("my_script.py")

        # Option 4: Install global exception hook
        healer.install_global_hook()
    """

    def __init__(
        self,
        config: Optional[SelfHealingConfig] = None,
        log_directory: Optional[str] = None
    ):
        """
        Initialize the self-healing orchestrator.

        Args:
            config: Configuration settings (uses default if None)
            log_directory: Override log directory location
        """
        self.config = config or get_config()
        set_config(self.config)  # Make it globally available

        # Override log directory if specified
        if log_directory:
            self.config.logging.log_directory = log_directory

        # Initialize components
        self.logger = HealingLogger(
            log_directory=self.config.logging.log_directory,
            verbose=self.config.logging.verbose,
            log_to_console=self.config.logging.log_to_console,
            log_to_file=self.config.logging.log_to_file
        )
        self.detector = ErrorDetector(self.logger)
        self.analyzer = ErrorAnalyzer()
        self.fixer = ErrorFixer(self.config, self.logger)
        self.validator = FixValidator(self.config, self.logger, self.detector)

        # Track active sessions
        self._active_sessions: Dict[str, HealingSession] = {}

        # Callbacks for hooks
        self._on_error_callbacks: List[Callable[[DetectedError], None]] = []
        self._on_fix_callbacks: List[Callable[[FixResult], None]] = []
        self._on_complete_callbacks: List[Callable[[HealingSession], None]] = []

    def heal(
        self,
        error: DetectedError,
        rerun_function: Optional[Callable] = None
    ) -> HealingSession:
        """
        Perform the complete healing process for an error.

        This is the main entry point for self-healing. It:
        1. Analyzes the error
        2. Generates and applies fixes
        3. Validates the fixes
        4. Retries if needed
        5. Logs everything

        Args:
            error: The detected error to heal
            rerun_function: Optional function to re-run for validation

        Returns:
            HealingSession with complete healing history
        """
        # Check if healing is enabled
        if not self.config.enabled:
            session = HealingSession(
                incident_id="disabled",
                original_error=error,
                final_result="disabled"
            )
            return session

        # Start a new incident
        incident_id = self.logger.new_incident()
        session = HealingSession(
            incident_id=incident_id,
            original_error=error
        )
        self._active_sessions[incident_id] = session

        # Log error detection
        self.logger.log_error_detected(
            incident_id=incident_id,
            environment=error.environment.value,
            error_type=error.error_type.value,
            error_message=error.message,
            file_path=error.file_path,
            line_number=error.line_number,
            stack_trace=error.stack_trace
        )

        # Notify callbacks
        for callback in self._on_error_callbacks:
            try:
                callback(error)
            except Exception:
                pass

        # Step 1: Analyze the error
        analysis = self.analyzer.analyze(error)
        session.analysis = analysis

        self.logger.log_analysis_complete(
            incident_id=incident_id,
            environment=error.environment.value,
            analysis_summary=analysis.root_cause,
            root_cause=analysis.root_cause,
            suggested_fixes=[s.description for s in analysis.suggestions]
        )

        # If manual intervention is required immediately, stop here
        if analysis.requires_human_review and not analysis.suggestions:
            self.logger.log_manual_intervention_required(
                incident_id=incident_id,
                environment=error.environment.value,
                reason=analysis.analysis_notes,
                suggested_action="Review the error manually and apply appropriate fix"
            )
            session.final_result = "manual_required"
            self._complete_session(session)
            return session

        # Step 2: Try each fix suggestion
        max_attempts = self.config.retry.max_attempts
        delay = self.config.retry.initial_delay_seconds

        for attempt, suggestion in enumerate(analysis.suggestions[:max_attempts], 1):
            session.total_attempts = attempt

            # Log fix generation
            self.logger.log_fix_generated(
                incident_id=incident_id,
                environment=error.environment.value,
                fix_description=suggestion.description,
                fix_reasoning=suggestion.reasoning
            )

            # Apply the fix
            fix_result = self.fixer.apply_fix(suggestion, analysis)

            # Record the attempt
            session.fix_attempts.append({
                "attempt": attempt,
                "suggestion": suggestion.description,
                "fix_result": fix_result.success,
                "diff": fix_result.diff
            })

            if fix_result.success:
                # Log fix applied
                self.logger.log_fix_applied(
                    incident_id=incident_id,
                    environment=error.environment.value,
                    file_path=suggestion.file_path or error.file_path or "N/A",
                    fix_description=suggestion.description,
                    fix_reasoning=suggestion.reasoning,
                    fix_diff=fix_result.diff,
                    attempt_number=attempt
                )

                # Notify callbacks
                for callback in self._on_fix_callbacks:
                    try:
                        callback(fix_result)
                    except Exception:
                        pass

                # Validate the fix
                validation = self.validator.validate(
                    fix_result,
                    error,
                    level=ValidationLevel.STANDARD,
                    rerun_function=rerun_function
                )

                if validation.success:
                    # Fix worked!
                    self.logger.log_fix_validated(
                        incident_id=incident_id,
                        environment=error.environment.value,
                        validation_result="SUCCESS",
                        tests_run=validation.messages
                    )

                    self.logger.log_healing_complete(
                        incident_id=incident_id,
                        environment=error.environment.value,
                        success=True,
                        total_attempts=attempt,
                        summary=f"Fixed: {suggestion.description}"
                    )

                    session.final_result = "success"
                    self._complete_session(session)
                    return session

                else:
                    # Validation failed
                    self.logger.log_fix_failed(
                        incident_id=incident_id,
                        environment=error.environment.value,
                        failure_reason="; ".join(validation.messages),
                        attempt_number=attempt,
                        will_retry=attempt < min(len(analysis.suggestions), max_attempts)
                    )

                    # Rollback the fix
                    if self.config.validation.rollback_on_failure:
                        if self.fixer.rollback(fix_result):
                            self.logger.log_rollback(
                                incident_id=incident_id,
                                environment=error.environment.value,
                                file_path=suggestion.file_path or error.file_path or "N/A",
                                rollback_reason="Validation failed"
                            )

            else:
                # Fix application failed
                self.logger.log_fix_failed(
                    incident_id=incident_id,
                    environment=error.environment.value,
                    failure_reason=fix_result.error_message or "Unknown error",
                    attempt_number=attempt,
                    will_retry=attempt < min(len(analysis.suggestions), max_attempts)
                )

            # Wait before next attempt (exponential backoff)
            if attempt < min(len(analysis.suggestions), max_attempts):
                time.sleep(delay)
                delay = min(
                    delay * self.config.retry.backoff_multiplier,
                    self.config.retry.max_delay_seconds
                )

        # All attempts exhausted
        self.logger.log_manual_intervention_required(
            incident_id=incident_id,
            environment=error.environment.value,
            reason=f"All {session.total_attempts} fix attempts failed",
            suggested_action="Manual investigation and fix required"
        )

        self.logger.log_healing_complete(
            incident_id=incident_id,
            environment=error.environment.value,
            success=False,
            total_attempts=session.total_attempts,
            summary="Automatic healing failed, manual intervention required"
        )

        session.final_result = "failed"
        self._complete_session(session)
        return session

    def _complete_session(self, session: HealingSession) -> None:
        """Complete a healing session and notify callbacks."""
        for callback in self._on_complete_callbacks:
            try:
                callback(session)
            except Exception:
                pass

        # Remove from active sessions
        if session.incident_id in self._active_sessions:
            del self._active_sessions[session.incident_id]

    def protect(self, func: Callable) -> Callable:
        """
        Decorator to protect a function with self-healing.

        The decorated function will have its exceptions caught,
        analyzed, and potentially fixed automatically.

        Usage:
            @healer.protect
            def my_function():
                # Errors here will be caught and healed
                pass

        Args:
            func: The function to protect

        Returns:
            Wrapped function with self-healing
        """
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Detect the error
                error = self.detector.detect_from_exception(e)

                # Attempt to heal
                session = self.heal(error, rerun_function=lambda: func(*args, **kwargs))

                # If healing succeeded, try again
                if session.final_result == "success":
                    return func(*args, **kwargs)
                else:
                    # Re-raise the original exception
                    raise

        return wrapper

    @contextmanager
    def healing_context(self, file_path: Optional[str] = None):
        """
        Context manager for protected code blocks.

        Usage:
            with healer.healing_context():
                risky_code()

        Args:
            file_path: Optional file path for context

        Yields:
            The healing context
        """
        try:
            yield
        except Exception as e:
            error = self.detector.detect_from_exception(e, file_path)
            session = self.heal(error)

            if session.final_result != "success":
                raise

    def run_script(
        self,
        script_path: str,
        globals_dict: Optional[Dict[str, Any]] = None,
        locals_dict: Optional[Dict[str, Any]] = None
    ) -> HealingSession:
        """
        Run a Python script with self-healing enabled.

        Args:
            script_path: Path to the Python script
            globals_dict: Global namespace for execution
            locals_dict: Local namespace for execution

        Returns:
            HealingSession (if error occurred) or None (if successful)
        """
        path = Path(script_path)
        if not path.exists():
            raise FileNotFoundError(f"Script not found: {script_path}")

        # Validate syntax first
        syntax_error = self.detector.validate_file_syntax(script_path)
        if syntax_error:
            return self.heal(syntax_error)

        # Read and execute the script
        with open(script_path, 'r') as f:
            code = f.read()

        globals_dict = globals_dict or {"__name__": "__main__", "__file__": script_path}
        locals_dict = locals_dict or {}

        try:
            exec(compile(code, script_path, 'exec'), globals_dict, locals_dict)
            return None  # No errors
        except Exception as e:
            error = self.detector.detect_from_exception(e, script_path)
            return self.heal(
                error,
                rerun_function=lambda: exec(
                    compile(open(script_path).read(), script_path, 'exec'),
                    globals_dict,
                    locals_dict
                )
            )

    def install_global_hook(self) -> None:
        """
        Install a global exception hook to catch all uncaught exceptions.

        This modifies sys.excepthook to intercept exceptions and
        attempt automatic healing.

        Note: This should be used carefully as it affects the entire
        Python process.
        """
        original_hook = sys.excepthook

        def healing_hook(exc_type, exc_value, exc_tb):
            # Don't handle KeyboardInterrupt or SystemExit
            if issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
                original_hook(exc_type, exc_value, exc_tb)
                return

            if isinstance(exc_value, Exception):
                error = self.detector.detect_from_exception(exc_value)
                session = self.heal(error)

                if session.final_result == "success":
                    print("Error was automatically healed. Please re-run the program.")
                else:
                    print("Automatic healing failed. See logs for details.")
                    original_hook(exc_type, exc_value, exc_tb)
            else:
                original_hook(exc_type, exc_value, exc_tb)

        sys.excepthook = healing_hook

    def on_error(self, callback: Callable[[DetectedError], None]) -> None:
        """
        Register a callback for when errors are detected.

        Args:
            callback: Function to call with the DetectedError
        """
        self._on_error_callbacks.append(callback)

    def on_fix(self, callback: Callable[[FixResult], None]) -> None:
        """
        Register a callback for when fixes are applied.

        Args:
            callback: Function to call with the FixResult
        """
        self._on_fix_callbacks.append(callback)

    def on_complete(self, callback: Callable[[HealingSession], None]) -> None:
        """
        Register a callback for when healing sessions complete.

        Args:
            callback: Function to call with the HealingSession
        """
        self._on_complete_callbacks.append(callback)

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics from the healing system.

        Returns:
            Dictionary with healing statistics
        """
        return self.logger.get_statistics()

    def get_changelog(self) -> Dict[str, Any]:
        """
        Get the complete changelog.

        Returns:
            Dictionary with all logged incidents
        """
        return self.logger.get_changelog()

    def preview_fix(
        self,
        error: DetectedError
    ) -> List[Dict[str, Any]]:
        """
        Preview what fixes would be applied without applying them.

        Useful for dry-run mode or getting user approval.

        Args:
            error: The error to analyze

        Returns:
            List of fix previews
        """
        analysis = self.analyzer.analyze(error)
        previews = []

        for suggestion in analysis.suggestions:
            preview = {
                "description": suggestion.description,
                "reasoning": suggestion.reasoning,
                "confidence": suggestion.confidence.value,
                "type": suggestion.fix_type,
                "preview": self.fixer.generate_fix_preview(suggestion, analysis)
            }
            previews.append(preview)

        return previews

    def heal_from_output(
        self,
        output: str,
        environment: EnvironmentType,
        exit_code: int = 1,
        file_path: Optional[str] = None
    ) -> Optional[HealingSession]:
        """
        Heal based on command/process output.

        Useful for infrastructure-as-code tools like Terraform and Ansible.

        Args:
            output: The error output (stderr)
            environment: The environment type
            exit_code: Process exit code
            file_path: Related file path

        Returns:
            HealingSession if error was detected, None otherwise
        """
        error = self.detector.detect_from_output(
            output, environment, exit_code, file_path
        )

        if error:
            return self.heal(error)

        return None


def create_healer(**kwargs) -> SelfHealingOrchestrator:
    """
    Factory function to create a configured self-healing orchestrator.

    Args:
        **kwargs: Configuration overrides

    Returns:
        Configured SelfHealingOrchestrator
    """
    config = SelfHealingConfig.from_env()

    # Apply overrides
    if "dry_run" in kwargs:
        config.safety.dry_run = kwargs["dry_run"]
    if "max_attempts" in kwargs:
        config.retry.max_attempts = kwargs["max_attempts"]
    if "log_directory" in kwargs:
        config.logging.log_directory = kwargs["log_directory"]
    if "verbose" in kwargs:
        config.logging.verbose = kwargs["verbose"]

    return SelfHealingOrchestrator(config=config)


# Convenience function for quick protection
def self_heal(func: Callable) -> Callable:
    """
    Quick decorator for self-healing protection.

    Usage:
        from self_healing import self_heal

        @self_heal
        def my_function():
            pass

    Args:
        func: Function to protect

    Returns:
        Protected function
    """
    healer = create_healer()
    return healer.protect(func)
