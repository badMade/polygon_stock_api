"""
Error Detector Module for Self-Healing Code System
===================================================

This module provides error detection mechanisms for various environments.
It monitors execution, catches errors, and triggers the self-healing process.

Detection Methods:
------------------
- Exception hooks for Python runtime errors
- Output parsing for Terraform/Ansible/Bash
- Syntax validation before execution
- Runtime assertions and validators
- Health checks and proactive monitoring

Supported Error Types:
---------------------
- Syntax errors (malformed code/config)
- Logic bugs (incorrect behavior, infinite loops)
- Dependency issues (missing packages, version conflicts)
- Runtime exceptions (general execution failures)
- Configuration errors (environment mismatches)
- Network errors (connection failures, timeouts)
- Permission errors (access denied, insufficient privileges)
- Resource errors (memory, disk, CPU exhaustion)
"""

import ast
import re
import sys
import subprocess
import traceback
from dataclasses import dataclass, field
from typing import Optional, Callable, Dict, Any, List, Tuple, Type
from pathlib import Path

from .config import ErrorType, EnvironmentType, get_config
from .logger import HealingLogger


@dataclass
class DetectedError:
    """
    Represents a detected error with all relevant context.

    This class captures comprehensive information about an error
    to enable accurate analysis and fix generation.
    """
    error_type: ErrorType              # Classification of the error
    environment: EnvironmentType       # Where the error occurred
    message: str                       # Error message
    file_path: Optional[str] = None    # Source file
    line_number: Optional[int] = None  # Line number in source
    column: Optional[int] = None       # Column number
    stack_trace: Optional[str] = None  # Full stack trace
    source_code: Optional[str] = None  # Relevant source code snippet
    exception_type: Optional[str] = None  # Python exception class name
    original_exception: Optional[Exception] = None  # The actual exception
    exit_code: Optional[int] = None    # Exit code for external processes
    stdout: Optional[str] = None       # Standard output
    stderr: Optional[str] = None       # Standard error
    context: Dict[str, Any] = field(default_factory=dict)  # Additional context


class ErrorPatterns:
    """
    Collection of regex patterns for identifying error types.

    These patterns are used to classify errors based on their messages
    and determine the appropriate handling strategy.
    """

    # Python error patterns
    PYTHON_SYNTAX = [
        r"SyntaxError: (.+)",
        r"IndentationError: (.+)",
        r"TabError: (.+)",
    ]

    PYTHON_IMPORT = [
        r"ModuleNotFoundError: No module named '([^']+)'",
        r"ImportError: cannot import name '([^']+)'",
        r"ImportError: (.+)",
    ]

    PYTHON_TYPE = [
        r"TypeError: (.+)",
        r"AttributeError: (.+)",
    ]

    PYTHON_VALUE = [
        r"ValueError: (.+)",
        r"KeyError: (.+)",
        r"IndexError: (.+)",
    ]

    PYTHON_RUNTIME = [
        r"RuntimeError: (.+)",
        r"RecursionError: (.+)",
        r"StopIteration",
    ]

    PYTHON_RESOURCE = [
        r"MemoryError",
        r"OSError: \[Errno 28\]",  # No space left on device
        r"ResourceWarning: (.+)",
    ]

    PYTHON_PERMISSION = [
        r"PermissionError: (.+)",
        r"OSError: \[Errno 13\]",  # Permission denied
    ]

    PYTHON_NETWORK = [
        r"ConnectionError: (.+)",
        r"TimeoutError: (.+)",
        r"socket\.error: (.+)",
        r"urllib\.error\.URLError: (.+)",
        r"requests\.exceptions\.(.+)",
    ]

    # Terraform error patterns
    TERRAFORM_SYNTAX = [
        r"Error: (.+) on (.+) line (\d+)",
        r"Error: Invalid (.+)",
        r"Error: Unsupported (.+)",
    ]

    TERRAFORM_PROVIDER = [
        r"Error: Failed to install provider",
        r"Error: Provider (.+) not found",
    ]

    TERRAFORM_RESOURCE = [
        r"Error: Error creating (.+)",
        r"Error: Error applying (.+)",
    ]

    # Ansible error patterns
    ANSIBLE_SYNTAX = [
        r"ERROR! Syntax Error",
        r"ERROR! (.+) is not a valid attribute",
    ]

    ANSIBLE_MODULE = [
        r"ERROR! couldn't resolve module/action '([^']+)'",
        r"ERROR! the role '([^']+)' was not found",
    ]

    ANSIBLE_CONNECTION = [
        r"UNREACHABLE!",
        r"SSH Error",
    ]

    # Bash error patterns
    BASH_SYNTAX = [
        r"syntax error",
        r"unexpected token",
    ]

    BASH_COMMAND = [
        r"command not found",
        r"No such file or directory",
    ]

    BASH_PERMISSION = [
        r"Permission denied",
        r"Operation not permitted",
    ]


class ErrorDetector:
    """
    Main error detection class for the self-healing system.

    This class provides methods to detect errors in various environments,
    classify them, and extract context for the repair module.

    Usage:
        detector = ErrorDetector()

        # Detect Python errors
        @detector.catch_python_errors
        def my_function():
            pass

        # Detect errors in external process output
        error = detector.detect_from_output(stderr, EnvironmentType.TERRAFORM)
    """

    def __init__(self, logger: Optional[HealingLogger] = None):
        """
        Initialize the error detector.

        Args:
            logger: HealingLogger instance for logging detected errors
        """
        self.logger = logger or HealingLogger()
        self.config = get_config()

        # Compile regex patterns for performance
        self._compiled_patterns: Dict[str, List[re.Pattern]] = {}
        self._compile_patterns()

        # Custom validators registered by the application
        self._validators: List[Callable[[], Optional[DetectedError]]] = []

        # Error hooks for custom error handling
        self._error_hooks: List[Callable[[DetectedError], None]] = []

    def _compile_patterns(self) -> None:
        """Compile all regex patterns for efficient matching."""
        pattern_groups = {
            "python_syntax": ErrorPatterns.PYTHON_SYNTAX,
            "python_import": ErrorPatterns.PYTHON_IMPORT,
            "python_type": ErrorPatterns.PYTHON_TYPE,
            "python_value": ErrorPatterns.PYTHON_VALUE,
            "python_runtime": ErrorPatterns.PYTHON_RUNTIME,
            "python_resource": ErrorPatterns.PYTHON_RESOURCE,
            "python_permission": ErrorPatterns.PYTHON_PERMISSION,
            "python_network": ErrorPatterns.PYTHON_NETWORK,
            "terraform_syntax": ErrorPatterns.TERRAFORM_SYNTAX,
            "terraform_provider": ErrorPatterns.TERRAFORM_PROVIDER,
            "terraform_resource": ErrorPatterns.TERRAFORM_RESOURCE,
            "ansible_syntax": ErrorPatterns.ANSIBLE_SYNTAX,
            "ansible_module": ErrorPatterns.ANSIBLE_MODULE,
            "ansible_connection": ErrorPatterns.ANSIBLE_CONNECTION,
            "bash_syntax": ErrorPatterns.BASH_SYNTAX,
            "bash_command": ErrorPatterns.BASH_COMMAND,
            "bash_permission": ErrorPatterns.BASH_PERMISSION,
        }

        for group_name, patterns in pattern_groups.items():
            self._compiled_patterns[group_name] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]

    def classify_error(
        self,
        message: str,
        environment: EnvironmentType
    ) -> ErrorType:
        """
        Classify an error message into an ErrorType.

        Args:
            message: The error message to classify
            environment: The environment the error occurred in

        Returns:
            The classified ErrorType
        """
        if environment == EnvironmentType.PYTHON:
            return self._classify_python_error(message)
        elif environment == EnvironmentType.TERRAFORM:
            return self._classify_terraform_error(message)
        elif environment == EnvironmentType.ANSIBLE:
            return self._classify_ansible_error(message)
        elif environment == EnvironmentType.BASH:
            return self._classify_bash_error(message)

        return ErrorType.UNKNOWN

    def _classify_python_error(self, message: str) -> ErrorType:
        """Classify a Python error message."""
        # Check syntax errors
        for pattern in self._compiled_patterns["python_syntax"]:
            if pattern.search(message):
                return ErrorType.SYNTAX

        # Check import/dependency errors
        for pattern in self._compiled_patterns["python_import"]:
            if pattern.search(message):
                return ErrorType.DEPENDENCY

        # Check type errors (often indicate logic issues)
        for pattern in self._compiled_patterns["python_type"]:
            if pattern.search(message):
                return ErrorType.LOGIC

        # Check value errors
        for pattern in self._compiled_patterns["python_value"]:
            if pattern.search(message):
                return ErrorType.RUNTIME

        # Check resource errors
        for pattern in self._compiled_patterns["python_resource"]:
            if pattern.search(message):
                return ErrorType.RESOURCE

        # Check permission errors
        for pattern in self._compiled_patterns["python_permission"]:
            if pattern.search(message):
                return ErrorType.PERMISSION

        # Check network errors
        for pattern in self._compiled_patterns["python_network"]:
            if pattern.search(message):
                return ErrorType.NETWORK

        # Check runtime errors
        for pattern in self._compiled_patterns["python_runtime"]:
            if pattern.search(message):
                return ErrorType.RUNTIME

        return ErrorType.UNKNOWN

    def _classify_terraform_error(self, message: str) -> ErrorType:
        """Classify a Terraform error message."""
        for pattern in self._compiled_patterns["terraform_syntax"]:
            if pattern.search(message):
                return ErrorType.SYNTAX

        for pattern in self._compiled_patterns["terraform_provider"]:
            if pattern.search(message):
                return ErrorType.DEPENDENCY

        for pattern in self._compiled_patterns["terraform_resource"]:
            if pattern.search(message):
                return ErrorType.CONFIGURATION

        return ErrorType.UNKNOWN

    def _classify_ansible_error(self, message: str) -> ErrorType:
        """Classify an Ansible error message."""
        for pattern in self._compiled_patterns["ansible_syntax"]:
            if pattern.search(message):
                return ErrorType.SYNTAX

        for pattern in self._compiled_patterns["ansible_module"]:
            if pattern.search(message):
                return ErrorType.DEPENDENCY

        for pattern in self._compiled_patterns["ansible_connection"]:
            if pattern.search(message):
                return ErrorType.NETWORK

        return ErrorType.UNKNOWN

    def _classify_bash_error(self, message: str) -> ErrorType:
        """Classify a Bash error message."""
        for pattern in self._compiled_patterns["bash_syntax"]:
            if pattern.search(message):
                return ErrorType.SYNTAX

        for pattern in self._compiled_patterns["bash_command"]:
            if pattern.search(message):
                return ErrorType.DEPENDENCY

        for pattern in self._compiled_patterns["bash_permission"]:
            if pattern.search(message):
                return ErrorType.PERMISSION

        return ErrorType.UNKNOWN

    def detect_from_exception(
        self,
        exception: Exception,
        file_path: Optional[str] = None
    ) -> DetectedError:
        """
        Create a DetectedError from a Python exception.

        Args:
            exception: The exception that was raised
            file_path: Optional source file path

        Returns:
            A DetectedError with full context
        """
        # Get the full stack trace
        stack_trace = traceback.format_exc()

        # Extract file and line information from the traceback
        tb = exception.__traceback__
        detected_file = file_path
        detected_line = None
        source_code = None

        if tb:
            # Walk to the last frame to get the actual error location
            while tb.tb_next:
                tb = tb.tb_next

            frame = tb.tb_frame
            detected_line = tb.tb_lineno
            if not detected_file:
                detected_file = frame.f_code.co_filename

            # Try to get the source code line
            try:
                if detected_file and Path(detected_file).exists():
                    with open(detected_file, 'r') as f:
                        lines = f.readlines()
                        if detected_line and 0 < detected_line <= len(lines):
                            # Get a few lines of context
                            start = max(0, detected_line - 3)
                            end = min(len(lines), detected_line + 2)
                            source_code = ''.join(lines[start:end])
            except Exception:
                pass

        error_message = str(exception)
        error_type = self.classify_error(
            f"{type(exception).__name__}: {error_message}",
            EnvironmentType.PYTHON
        )

        return DetectedError(
            error_type=error_type,
            environment=EnvironmentType.PYTHON,
            message=error_message,
            file_path=detected_file,
            line_number=detected_line,
            stack_trace=stack_trace,
            source_code=source_code,
            exception_type=type(exception).__name__,
            original_exception=exception,
        )

    def detect_from_output(
        self,
        output: str,
        environment: EnvironmentType,
        exit_code: Optional[int] = None,
        file_path: Optional[str] = None
    ) -> Optional[DetectedError]:
        """
        Detect errors from process output (stdout/stderr).

        Args:
            output: The output to analyze
            environment: The environment type
            exit_code: Exit code of the process
            file_path: Related file path

        Returns:
            DetectedError if an error is detected, None otherwise
        """
        if not output and (exit_code is None or exit_code == 0):
            return None

        # If exit code indicates failure, treat as error
        if exit_code is not None and exit_code != 0:
            error_type = self.classify_error(output, environment)

            # Extract line number if present in output
            line_number = None
            line_match = re.search(r'line (\d+)', output, re.IGNORECASE)
            if line_match:
                line_number = int(line_match.group(1))

            return DetectedError(
                error_type=error_type,
                environment=environment,
                message=output[:500],  # Truncate long messages
                file_path=file_path,
                line_number=line_number,
                exit_code=exit_code,
                stderr=output,
            )

        # Look for error patterns in output even if exit code is 0
        if environment == EnvironmentType.TERRAFORM:
            if "Error:" in output or "error:" in output:
                error_type = self.classify_error(output, environment)
                return DetectedError(
                    error_type=error_type,
                    environment=environment,
                    message=self._extract_error_message(output),
                    file_path=file_path,
                    stderr=output,
                )
        elif environment == EnvironmentType.ANSIBLE:
            if "fatal:" in output.lower() or "error!" in output.lower():
                error_type = self.classify_error(output, environment)
                return DetectedError(
                    error_type=error_type,
                    environment=environment,
                    message=self._extract_error_message(output),
                    file_path=file_path,
                    stderr=output,
                )

        return None

    def _extract_error_message(self, output: str) -> str:
        """Extract the main error message from output."""
        # Try to find the most relevant error line
        for line in output.split('\n'):
            if 'error' in line.lower():
                return line.strip()[:200]
        return output[:200]

    def validate_python_syntax(self, code: str, file_path: Optional[str] = None) -> Optional[DetectedError]:
        """
        Validate Python code syntax without executing it.

        Args:
            code: Python source code to validate
            file_path: Optional file path for context

        Returns:
            DetectedError if syntax is invalid, None if valid
        """
        try:
            ast.parse(code)
            return None
        except SyntaxError as e:
            return DetectedError(
                error_type=ErrorType.SYNTAX,
                environment=EnvironmentType.PYTHON,
                message=str(e.msg),
                file_path=file_path or e.filename,
                line_number=e.lineno,
                column=e.offset,
                source_code=e.text,
                exception_type="SyntaxError",
                original_exception=e,
            )

    def validate_file_syntax(
        self,
        file_path: str,
        environment: Optional[EnvironmentType] = None
    ) -> Optional[DetectedError]:
        """
        Validate syntax of a file before execution.

        Args:
            file_path: Path to the file to validate
            environment: Environment type (auto-detected if not provided)

        Returns:
            DetectedError if syntax is invalid, None if valid
        """
        path = Path(file_path)
        if not path.exists():
            return DetectedError(
                error_type=ErrorType.CONFIGURATION,
                environment=environment or EnvironmentType.PYTHON,
                message=f"File not found: {file_path}",
                file_path=file_path,
            )

        # Auto-detect environment from file extension
        if environment is None:
            ext = path.suffix.lower()
            if ext == '.py':
                environment = EnvironmentType.PYTHON
            elif ext == '.tf':
                environment = EnvironmentType.TERRAFORM
            elif ext in ['.yml', '.yaml']:
                environment = EnvironmentType.ANSIBLE
            elif ext == '.sh':
                environment = EnvironmentType.BASH
            else:
                environment = EnvironmentType.PYTHON

        # Python syntax validation
        if environment == EnvironmentType.PYTHON:
            with open(file_path, 'r') as f:
                code = f.read()
            return self.validate_python_syntax(code, file_path)

        # Terraform validation
        elif environment == EnvironmentType.TERRAFORM:
            result = subprocess.run(
                ['terraform', 'validate'],
                cwd=path.parent,
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                return DetectedError(
                    error_type=ErrorType.SYNTAX,
                    environment=environment,
                    message=result.stderr or result.stdout,
                    file_path=file_path,
                    exit_code=result.returncode,
                    stderr=result.stderr,
                    stdout=result.stdout,
                )

        # Ansible syntax check
        elif environment == EnvironmentType.ANSIBLE:
            result = subprocess.run(
                ['ansible-playbook', '--syntax-check', file_path],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                return DetectedError(
                    error_type=ErrorType.SYNTAX,
                    environment=environment,
                    message=result.stderr or result.stdout,
                    file_path=file_path,
                    exit_code=result.returncode,
                    stderr=result.stderr,
                    stdout=result.stdout,
                )

        # Bash syntax check
        elif environment == EnvironmentType.BASH:
            result = subprocess.run(
                ['bash', '-n', file_path],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                return DetectedError(
                    error_type=ErrorType.SYNTAX,
                    environment=environment,
                    message=result.stderr,
                    file_path=file_path,
                    exit_code=result.returncode,
                    stderr=result.stderr,
                )

        return None

    def register_validator(
        self,
        validator: Callable[[], Optional[DetectedError]]
    ) -> None:
        """
        Register a custom validator function.

        Validators are called periodically to check for issues.
        They should return a DetectedError if an issue is found,
        or None if everything is healthy.

        Args:
            validator: A callable that returns DetectedError or None
        """
        self._validators.append(validator)

    def run_validators(self) -> List[DetectedError]:
        """
        Run all registered validators.

        Returns:
            List of detected errors from validators
        """
        errors = []
        for validator in self._validators:
            try:
                result = validator()
                if result is not None:
                    errors.append(result)
            except Exception as e:
                # Validator itself failed - log but continue
                errors.append(DetectedError(
                    error_type=ErrorType.RUNTIME,
                    environment=EnvironmentType.PYTHON,
                    message=f"Validator failed: {e}",
                    exception_type=type(e).__name__,
                    original_exception=e,
                ))
        return errors

    def register_error_hook(
        self,
        hook: Callable[[DetectedError], None]
    ) -> None:
        """
        Register a hook to be called when an error is detected.

        Args:
            hook: Callable that receives the DetectedError
        """
        self._error_hooks.append(hook)

    def _notify_hooks(self, error: DetectedError) -> None:
        """Notify all registered hooks about a detected error."""
        for hook in self._error_hooks:
            try:
                hook(error)
            except Exception:
                pass  # Don't let hook failures break detection

    def catch_python_errors(self, func: Callable) -> Callable:
        """
        Decorator to catch and detect Python errors in a function.

        Usage:
            @detector.catch_python_errors
            def my_function():
                # This function's errors will be caught and analyzed
                pass

        Args:
            func: The function to wrap

        Returns:
            Wrapped function that catches errors
        """
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Detect and analyze the error
                error = self.detect_from_exception(e)

                # Notify hooks
                self._notify_hooks(error)

                # Re-raise so the orchestrator can handle it
                raise

        return wrapper

    def create_global_exception_hook(
        self,
        callback: Callable[[DetectedError], None]
    ) -> None:
        """
        Install a global exception hook for uncaught exceptions.

        This modifies sys.excepthook to catch any unhandled exceptions
        and analyze them before the program exits.

        Args:
            callback: Function to call with the DetectedError
        """
        original_hook = sys.excepthook

        def custom_hook(exc_type: Type[BaseException], exc_value: BaseException, exc_tb):
            # Analyze the exception
            if isinstance(exc_value, Exception):
                error = self.detect_from_exception(exc_value)
                callback(error)

            # Call the original hook
            original_hook(exc_type, exc_value, exc_tb)

        sys.excepthook = custom_hook

    def detect_logic_issues(
        self,
        expected: Any,
        actual: Any,
        description: str,
        file_path: Optional[str] = None,
        line_number: Optional[int] = None
    ) -> Optional[DetectedError]:
        """
        Detect logic issues by comparing expected vs actual values.

        This is useful for runtime assertions and sanity checks.

        Args:
            expected: The expected value
            actual: The actual value
            description: Description of what was being checked
            file_path: Related file path
            line_number: Line number of the check

        Returns:
            DetectedError if values don't match, None if they match
        """
        if expected != actual:
            return DetectedError(
                error_type=ErrorType.LOGIC,
                environment=EnvironmentType.PYTHON,
                message=f"Logic error: {description}. Expected {expected}, got {actual}",
                file_path=file_path,
                line_number=line_number,
                context={
                    "expected": str(expected),
                    "actual": str(actual),
                    "description": description,
                }
            )
        return None

    def detect_infinite_loop(
        self,
        iteration_count: int,
        max_iterations: int,
        loop_description: str,
        file_path: Optional[str] = None,
        line_number: Optional[int] = None
    ) -> Optional[DetectedError]:
        """
        Detect potential infinite loops based on iteration count.

        Args:
            iteration_count: Current iteration count
            max_iterations: Maximum allowed iterations
            loop_description: Description of the loop
            file_path: Related file path
            line_number: Line number of the loop

        Returns:
            DetectedError if loop appears infinite, None otherwise
        """
        if iteration_count > max_iterations:
            return DetectedError(
                error_type=ErrorType.LOGIC,
                environment=EnvironmentType.PYTHON,
                message=f"Potential infinite loop detected: {loop_description}. "
                        f"Iteration count ({iteration_count}) exceeds maximum ({max_iterations})",
                file_path=file_path,
                line_number=line_number,
                context={
                    "iteration_count": iteration_count,
                    "max_iterations": max_iterations,
                }
            )
        return None
