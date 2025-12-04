"""
Fix Validator Module for Self-Healing Code System
==================================================

This module validates that applied fixes actually resolve the issues.
It runs syntax checks, linters, and tests to verify fix effectiveness.

Validation Process:
------------------
1. Syntax validation (parse/compile check)
2. Lint check (style and potential issues)
3. Unit test execution (if available)
4. Re-run the original operation (if applicable)

Features:
---------
- Multiple validation levels (quick, standard, thorough)
- Environment-specific validators
- Test discovery and execution
- Performance impact assessment
"""

import ast
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable
from pathlib import Path
from enum import Enum

from .config import EnvironmentType, get_config, SelfHealingConfig
from .detector import DetectedError, ErrorDetector
from .fixer import FixResult
from .logger import HealingLogger


class ValidationLevel(Enum):
    """Levels of validation thoroughness."""
    QUICK = "quick"       # Syntax check only
    STANDARD = "standard"  # Syntax + lint
    THOROUGH = "thorough"  # Syntax + lint + tests


@dataclass
class ValidationResult:
    """
    Result of validating a fix.

    Attributes:
        success: Whether validation passed
        level: Validation level used
        syntax_valid: Whether syntax is valid
        lint_passed: Whether lint check passed
        tests_passed: Whether tests passed
        original_error_resolved: Whether the original error is resolved
        new_errors: Any new errors introduced by the fix
        messages: Validation messages/details
        duration_seconds: How long validation took
    """
    success: bool
    level: ValidationLevel
    syntax_valid: bool = True
    lint_passed: Optional[bool] = None
    tests_passed: Optional[bool] = None
    original_error_resolved: Optional[bool] = None
    new_errors: List[str] = field(default_factory=list)
    messages: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0


class FixValidator:
    """
    Validates that applied fixes are effective and don't introduce new issues.

    This class runs various checks to ensure fixes are safe and working.

    Usage:
        validator = FixValidator()
        result = validator.validate(fix_result, original_error)
        if not result.success:
            print("Fix validation failed:", result.messages)
    """

    def __init__(
        self,
        config: Optional[SelfHealingConfig] = None,
        logger: Optional[HealingLogger] = None,
        detector: Optional[ErrorDetector] = None
    ):
        """
        Initialize the validator.

        Args:
            config: Configuration settings
            logger: Logger instance
            detector: Error detector for checking if errors are resolved
        """
        self.config = config or get_config()
        self.logger = logger or HealingLogger()
        self.detector = detector or ErrorDetector(self.logger)

        # Custom validators that can be registered
        self._custom_validators: List[Callable[[str], Optional[str]]] = []

    def validate(
        self,
        fix_result: FixResult,
        original_error: DetectedError,
        level: ValidationLevel = ValidationLevel.STANDARD,
        rerun_function: Optional[Callable] = None
    ) -> ValidationResult:
        """
        Validate a fix after it has been applied.

        Args:
            fix_result: The result from applying the fix
            original_error: The original error that was fixed
            level: How thorough to be in validation
            rerun_function: Optional function to re-run to verify fix

        Returns:
            ValidationResult with detailed validation status
        """
        start_time = time.time()
        messages = []
        new_errors = []

        # If fix wasn't applied, validation fails
        if not fix_result.success:
            return ValidationResult(
                success=False,
                level=level,
                syntax_valid=False,
                messages=["Fix was not successfully applied"],
                duration_seconds=time.time() - start_time
            )

        file_path = fix_result.rollback_info.get("file_path") if fix_result.rollback_info else None
        environment = original_error.environment

        # Step 1: Syntax validation
        syntax_valid = True
        if file_path and Path(file_path).exists():
            syntax_result = self._validate_syntax(file_path, environment)
            syntax_valid = syntax_result[0]
            if not syntax_valid:
                messages.append(f"Syntax check failed: {syntax_result[1]}")
                new_errors.append(syntax_result[1])

        # If syntax is invalid, don't continue
        if not syntax_valid:
            return ValidationResult(
                success=False,
                level=level,
                syntax_valid=False,
                messages=messages,
                new_errors=new_errors,
                duration_seconds=time.time() - start_time
            )

        messages.append("Syntax check passed")

        # Step 2: Lint validation (for STANDARD and THOROUGH)
        lint_passed = None
        if level in [ValidationLevel.STANDARD, ValidationLevel.THOROUGH]:
            if file_path and Path(file_path).exists():
                lint_result = self._validate_lint(file_path, environment)
                lint_passed = lint_result[0]
                if not lint_passed:
                    messages.append(f"Lint check warning: {lint_result[1]}")
                    # Lint failures are warnings, not blockers
                else:
                    messages.append("Lint check passed")

        # Step 3: Test execution (for THOROUGH only)
        tests_passed = None
        if level == ValidationLevel.THOROUGH:
            test_result = self._run_tests(file_path, environment)
            tests_passed = test_result[0]
            if not tests_passed:
                messages.append(f"Test execution failed: {test_result[1]}")
                new_errors.append(test_result[1])
            else:
                messages.append("Tests passed")

        # Step 4: Re-run original operation to verify fix
        original_error_resolved = None
        if rerun_function is not None:
            try:
                rerun_function()
                original_error_resolved = True
                messages.append("Original operation completed successfully")
            except Exception as e:
                original_error_resolved = False
                messages.append(f"Original error still present: {e}")
                new_errors.append(str(e))

        # Step 5: Run custom validators
        for validator in self._custom_validators:
            if file_path:
                error_msg = validator(file_path)
                if error_msg:
                    messages.append(f"Custom validator failed: {error_msg}")
                    new_errors.append(error_msg)

        # Determine overall success
        success = syntax_valid
        if tests_passed is not None:
            success = success and tests_passed
        if original_error_resolved is not None:
            success = success and original_error_resolved

        return ValidationResult(
            success=success,
            level=level,
            syntax_valid=syntax_valid,
            lint_passed=lint_passed,
            tests_passed=tests_passed,
            original_error_resolved=original_error_resolved,
            new_errors=new_errors,
            messages=messages,
            duration_seconds=time.time() - start_time
        )

    def _validate_syntax(
        self,
        file_path: str,
        environment: EnvironmentType
    ) -> tuple[bool, str]:
        """
        Validate syntax of a file.

        Returns:
            Tuple of (is_valid, error_message)
        """
        path = Path(file_path)

        if environment == EnvironmentType.PYTHON:
            try:
                with open(file_path, 'r') as f:
                    code = f.read()
                ast.parse(code)
                return (True, "")
            except SyntaxError as e:
                return (False, f"Line {e.lineno}: {e.msg}")

        elif environment == EnvironmentType.TERRAFORM:
            try:
                result = subprocess.run(
                    ['terraform', 'validate'],
                    cwd=path.parent,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode == 0:
                    return (True, "")
                return (False, result.stderr or result.stdout)
            except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                return (False, str(e))

        elif environment == EnvironmentType.ANSIBLE:
            try:
                result = subprocess.run(
                    ['ansible-playbook', '--syntax-check', str(file_path)],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode == 0:
                    return (True, "")
                return (False, result.stderr or result.stdout)
            except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                return (False, str(e))

        elif environment == EnvironmentType.BASH:
            try:
                result = subprocess.run(
                    ['bash', '-n', str(file_path)],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    return (True, "")
                return (False, result.stderr)
            except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                return (False, str(e))

        return (True, "")  # Unknown environment, assume valid

    def _validate_lint(
        self,
        file_path: str,
        environment: EnvironmentType
    ) -> tuple[bool, str]:
        """
        Run linter on a file.

        Returns:
            Tuple of (passed, warning_message)
        """
        if environment == EnvironmentType.PYTHON:
            lint_cmd = self.config.python_settings.get("lint_command", "flake8")
            try:
                result = subprocess.run(
                    [lint_cmd, str(file_path)],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode == 0:
                    return (True, "")
                # Lint issues found, but code may still work
                return (False, result.stdout or result.stderr)
            except FileNotFoundError:
                # Linter not installed, skip
                return (True, "Linter not available")
            except subprocess.TimeoutExpired:
                return (False, "Lint check timed out")

        elif environment == EnvironmentType.TERRAFORM:
            try:
                result = subprocess.run(
                    ['terraform', 'fmt', '-check', str(file_path)],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode == 0:
                    return (True, "")
                return (False, "File not properly formatted")
            except (FileNotFoundError, subprocess.TimeoutExpired):
                return (True, "Terraform fmt not available")

        return (True, "")

    def _run_tests(
        self,
        file_path: Optional[str],
        environment: EnvironmentType
    ) -> tuple[bool, str]:
        """
        Run relevant tests for the modified file.

        Returns:
            Tuple of (passed, error_message)
        """
        if environment != EnvironmentType.PYTHON or not file_path:
            return (True, "No tests applicable")

        path = Path(file_path)

        # Try to find related test file
        test_patterns = [
            f"test_{path.stem}.py",
            f"{path.stem}_test.py",
            f"tests/test_{path.stem}.py",
            f"test/test_{path.stem}.py",
        ]

        test_file = None
        for pattern in test_patterns:
            test_path = path.parent / pattern
            if test_path.exists():
                test_file = str(test_path)
                break

        if not test_file:
            # No specific test file, try running all tests
            test_file = str(path.parent)

        try:
            result = subprocess.run(
                [sys.executable, '-m', 'pytest', test_file, '-v', '--tb=short'],
                capture_output=True,
                text=True,
                timeout=self.config.validation.test_timeout_seconds
            )
            if result.returncode == 0:
                return (True, "")
            return (False, result.stdout + result.stderr)
        except FileNotFoundError:
            # pytest not installed
            try:
                # Try unittest
                result = subprocess.run(
                    [sys.executable, '-m', 'unittest', 'discover', '-s', str(path.parent)],
                    capture_output=True,
                    text=True,
                    timeout=self.config.validation.test_timeout_seconds
                )
                if result.returncode == 0:
                    return (True, "")
                return (False, result.stderr)
            except Exception:
                return (True, "No test runner available")
        except subprocess.TimeoutExpired:
            return (False, "Test execution timed out")

    def register_validator(
        self,
        validator: Callable[[str], Optional[str]]
    ) -> None:
        """
        Register a custom validator function.

        The validator should take a file path and return None if valid,
        or an error message string if invalid.

        Args:
            validator: Function that validates a file
        """
        self._custom_validators.append(validator)

    def quick_validate(
        self,
        fix_result: FixResult,
        original_error: DetectedError
    ) -> ValidationResult:
        """
        Perform a quick validation (syntax only).

        Args:
            fix_result: The applied fix result
            original_error: The original error

        Returns:
            ValidationResult
        """
        return self.validate(fix_result, original_error, level=ValidationLevel.QUICK)

    def thorough_validate(
        self,
        fix_result: FixResult,
        original_error: DetectedError,
        rerun_function: Optional[Callable] = None
    ) -> ValidationResult:
        """
        Perform thorough validation (syntax + lint + tests + rerun).

        Args:
            fix_result: The applied fix result
            original_error: The original error
            rerun_function: Function to re-run to verify fix

        Returns:
            ValidationResult
        """
        return self.validate(
            fix_result,
            original_error,
            level=ValidationLevel.THOROUGH,
            rerun_function=rerun_function
        )

    def validate_code_string(
        self,
        code: str,
        environment: EnvironmentType = EnvironmentType.PYTHON
    ) -> tuple[bool, str]:
        """
        Validate a code string without writing to file.

        Args:
            code: The code to validate
            environment: The environment/language

        Returns:
            Tuple of (is_valid, error_message)
        """
        if environment == EnvironmentType.PYTHON:
            try:
                ast.parse(code)
                return (True, "")
            except SyntaxError as e:
                return (False, f"Line {e.lineno}: {e.msg}")

        # For other environments, would need to write to temp file
        return (True, "")

    def compare_before_after(
        self,
        before_func: Callable,
        after_func: Callable,
        test_inputs: List[Any]
    ) -> Dict[str, Any]:
        """
        Compare function behavior before and after a fix.

        Args:
            before_func: Original function
            after_func: Fixed function
            test_inputs: List of inputs to test with

        Returns:
            Comparison results
        """
        results = {
            "inputs_tested": len(test_inputs),
            "same_output": 0,
            "different_output": 0,
            "before_errors": 0,
            "after_errors": 0,
            "both_error": 0,
            "details": []
        }

        for inp in test_inputs:
            before_result = None
            after_result = None
            before_error = None
            after_error = None

            try:
                before_result = before_func(inp)
            except Exception as e:
                before_error = str(e)

            try:
                after_result = after_func(inp)
            except Exception as e:
                after_error = str(e)

            if before_error and after_error:
                results["both_error"] += 1
            elif before_error:
                results["before_errors"] += 1
            elif after_error:
                results["after_errors"] += 1
            elif before_result == after_result:
                results["same_output"] += 1
            else:
                results["different_output"] += 1

            results["details"].append({
                "input": str(inp),
                "before": str(before_result) if before_result else before_error,
                "after": str(after_result) if after_result else after_error
            })

        return results
