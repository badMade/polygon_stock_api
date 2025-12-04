"""
Error Fixer Module for Self-Healing Code System
================================================

This module generates and applies fixes for detected errors. It takes
fix suggestions from the analyzer and translates them into concrete
changes that can be applied to the codebase.

Fix Strategies:
--------------
- IN_PLACE: Directly modify the source file
- COPY_AND_REPLACE: Work on a copy, validate, then replace
- RUNTIME_PATCH: Apply fix at runtime without file changes
- EXTERNAL_COMMAND: Execute shell commands to fix issues

Safety Features:
---------------
- Automatic backup before modifying files
- Protected path checking
- Diff preview generation
- Rollback capability
"""

import os
import re
import ast
import shutil
import subprocess
import tempfile
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
from difflib import unified_diff

from .config import (
    ErrorType, EnvironmentType, FixStrategy, get_config, SelfHealingConfig
)
from .detector import DetectedError
from .analyzer import FixSuggestion, FixConfidence, AnalysisResult
from .logger import HealingLogger


@dataclass
class FixResult:
    """
    Result of applying a fix.

    Attributes:
        success: Whether the fix was successfully applied
        description: Description of what was done
        diff: The diff of changes made (if applicable)
        backup_path: Path to backup file (if created)
        error_message: Error message if fix failed
        command_output: Output from external commands (if applicable)
    """
    success: bool
    description: str
    diff: Optional[str] = None
    backup_path: Optional[str] = None
    error_message: Optional[str] = None
    command_output: Optional[str] = None
    rollback_info: Dict[str, Any] = field(default_factory=dict)


class CodeTransformer:
    """
    Handles code transformations for applying fixes.

    This class provides methods to safely modify source code,
    including adding null checks, fixing indentation, etc.
    """

    @staticmethod
    def add_null_check(code: str, variable: str, line_number: int) -> str:
        """
        Add a null check for a variable.

        Args:
            code: Original source code
            variable: Variable name to check
            line_number: Line where variable is used

        Returns:
            Modified code with null check
        """
        lines = code.split('\n')
        if 0 < line_number <= len(lines):
            target_line = lines[line_number - 1]
            indent = len(target_line) - len(target_line.lstrip())
            indent_str = ' ' * indent

            # Insert null check before the line
            null_check = f"{indent_str}if {variable} is not None:\n"
            # Indent the original line
            indented_line = f"    {target_line}\n"

            lines[line_number - 1] = null_check + indented_line
            return '\n'.join(lines)

        return code

    @staticmethod
    def add_try_except(code: str, start_line: int, end_line: int, exception_type: str = "Exception") -> str:
        """
        Wrap code block in try-except.

        Args:
            code: Original source code
            start_line: First line to wrap
            end_line: Last line to wrap
            exception_type: Exception type to catch

        Returns:
            Modified code with try-except
        """
        lines = code.split('\n')
        if start_line < 1 or end_line > len(lines):
            return code

        # Get the indentation of the first line
        first_line = lines[start_line - 1]
        indent = len(first_line) - len(first_line.lstrip())
        indent_str = ' ' * indent

        # Build the try-except block
        result_lines = lines[:start_line - 1]
        result_lines.append(f"{indent_str}try:")

        # Indent the wrapped lines
        for i in range(start_line - 1, end_line):
            result_lines.append(f"    {lines[i]}")

        result_lines.append(f"{indent_str}except {exception_type} as e:")
        result_lines.append(f"{indent_str}    # Auto-generated exception handling")
        result_lines.append(f"{indent_str}    raise")

        result_lines.extend(lines[end_line:])
        return '\n'.join(result_lines)

    @staticmethod
    def add_retry_logic(code: str, line_number: int, max_retries: int = 3) -> str:
        """
        Add retry logic around a line of code.

        Args:
            code: Original source code
            line_number: Line to wrap with retry
            max_retries: Maximum retry attempts

        Returns:
            Modified code with retry logic
        """
        lines = code.split('\n')
        if 0 < line_number <= len(lines):
            target_line = lines[line_number - 1]
            indent = len(target_line) - len(target_line.lstrip())
            indent_str = ' ' * indent

            retry_code = f'''{indent_str}import time
{indent_str}for _retry_attempt in range({max_retries}):
{indent_str}    try:
    {target_line}
{indent_str}        break
{indent_str}    except Exception as e:
{indent_str}        if _retry_attempt == {max_retries - 1}:
{indent_str}            raise
{indent_str}        time.sleep(2 ** _retry_attempt)  # Exponential backoff'''

            lines[line_number - 1] = retry_code
            return '\n'.join(lines)

        return code

    @staticmethod
    def fix_indentation(code: str, use_spaces: bool = True, indent_size: int = 4) -> str:
        """
        Fix code indentation.

        Args:
            code: Original source code
            use_spaces: Use spaces instead of tabs
            indent_size: Number of spaces per indent level

        Returns:
            Code with fixed indentation
        """
        lines = code.split('\n')
        fixed_lines = []

        for line in lines:
            if not line.strip():  # Empty or whitespace-only line
                fixed_lines.append('')
                continue

            # Count leading whitespace
            stripped = line.lstrip()
            leading = line[:len(line) - len(stripped)]

            # Convert tabs to spaces or vice versa
            if use_spaces:
                # Replace tabs with spaces
                leading = leading.replace('\t', ' ' * indent_size)
            else:
                # Replace groups of spaces with tabs
                space_count = leading.count(' ')
                tab_count = space_count // indent_size
                leading = '\t' * tab_count

            fixed_lines.append(leading + stripped)

        return '\n'.join(fixed_lines)

    @staticmethod
    def add_import(code: str, import_statement: str) -> str:
        """
        Add an import statement to the top of the file.

        Args:
            code: Original source code
            import_statement: Import statement to add

        Returns:
            Code with import added
        """
        lines = code.split('\n')

        # Find the best position for the import
        insert_pos = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('import ') or stripped.startswith('from '):
                insert_pos = i + 1
            elif stripped and not stripped.startswith('#') and not stripped.startswith('"""'):
                break

        lines.insert(insert_pos, import_statement)
        return '\n'.join(lines)

    @staticmethod
    def use_dict_get(code: str, line_number: int) -> str:
        """
        Convert dict[key] to dict.get(key, default).

        Args:
            code: Original source code
            line_number: Line to modify

        Returns:
            Modified code
        """
        lines = code.split('\n')
        if 0 < line_number <= len(lines):
            line = lines[line_number - 1]
            # Simple pattern matching for dict[key]
            pattern = r'(\w+)\[([^\]]+)\]'
            replacement = r'\1.get(\2)'
            lines[line_number - 1] = re.sub(pattern, replacement, line)
            return '\n'.join(lines)
        return code

    @staticmethod
    def add_bounds_check(code: str, line_number: int, list_var: str, index_var: str) -> str:
        """
        Add bounds check before list access.

        Args:
            code: Original source code
            line_number: Line with list access
            list_var: Name of the list variable
            index_var: Name of the index variable

        Returns:
            Modified code with bounds check
        """
        lines = code.split('\n')
        if 0 < line_number <= len(lines):
            target_line = lines[line_number - 1]
            indent = len(target_line) - len(target_line.lstrip())
            indent_str = ' ' * indent

            check = f"{indent_str}if 0 <= {index_var} < len({list_var}):\n"
            indented_line = f"    {target_line}"

            lines[line_number - 1] = check + indented_line
            return '\n'.join(lines)
        return code


class ErrorFixer:
    """
    Main fixer class for the self-healing system.

    This class takes fix suggestions and applies them to the codebase,
    handling backups, rollbacks, and safety checks.

    Usage:
        fixer = ErrorFixer()
        result = fixer.apply_fix(suggestion, analysis_result)
        if not result.success:
            fixer.rollback(result)
    """

    def __init__(
        self,
        config: Optional[SelfHealingConfig] = None,
        logger: Optional[HealingLogger] = None
    ):
        """
        Initialize the error fixer.

        Args:
            config: Configuration for the fixer
            logger: Logger for recording fix actions
        """
        self.config = config or get_config()
        self.logger = logger or HealingLogger()
        self.transformer = CodeTransformer()

        # Directory for backups
        self.backup_dir = Path(self.config.logging.log_directory) / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def apply_fix(
        self,
        suggestion: FixSuggestion,
        analysis: AnalysisResult,
        dry_run: Optional[bool] = None
    ) -> FixResult:
        """
        Apply a fix suggestion.

        Args:
            suggestion: The fix suggestion to apply
            analysis: The analysis result for context
            dry_run: Override dry_run setting (uses config if None)

        Returns:
            FixResult indicating success or failure
        """
        dry_run = dry_run if dry_run is not None else self.config.safety.dry_run

        # Safety check: protected paths
        if suggestion.file_path and self.config.is_path_protected(suggestion.file_path):
            return FixResult(
                success=False,
                description=f"Cannot modify protected path: {suggestion.file_path}",
                error_message="Path is protected by configuration"
            )

        # Route to appropriate fix method
        if suggestion.fix_type == "command":
            return self._apply_command_fix(suggestion, analysis, dry_run)
        elif suggestion.fix_type == "code_change":
            return self._apply_code_fix(suggestion, analysis, dry_run)
        elif suggestion.fix_type == "config":
            return self._apply_config_fix(suggestion, analysis, dry_run)
        elif suggestion.fix_type == "retry":
            return self._apply_retry_fix(suggestion, analysis, dry_run)
        else:
            return FixResult(
                success=False,
                description=f"Unknown fix type: {suggestion.fix_type}",
                error_message="Unsupported fix type"
            )

    def _apply_command_fix(
        self,
        suggestion: FixSuggestion,
        analysis: AnalysisResult,
        dry_run: bool
    ) -> FixResult:
        """Apply a fix that requires running an external command."""
        if not suggestion.command:
            return FixResult(
                success=False,
                description="No command specified",
                error_message="Command fix requires a command"
            )

        # Safety check: allowed commands
        if not self.config.is_command_allowed(suggestion.command):
            return FixResult(
                success=False,
                description=f"Command not allowed: {suggestion.command}",
                error_message="Command is not in the allowed list"
            )

        if dry_run:
            return FixResult(
                success=True,
                description=f"[DRY RUN] Would execute: {suggestion.command}",
                diff=f"Command: {suggestion.command}"
            )

        # Execute the command
        try:
            result = subprocess.run(
                suggestion.command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.config.python_settings.get("pip_timeout", 60)
            )

            if result.returncode == 0:
                return FixResult(
                    success=True,
                    description=f"Command executed successfully: {suggestion.command}",
                    command_output=result.stdout
                )
            else:
                return FixResult(
                    success=False,
                    description=f"Command failed: {suggestion.command}",
                    error_message=result.stderr,
                    command_output=result.stdout
                )

        except subprocess.TimeoutExpired:
            return FixResult(
                success=False,
                description=f"Command timed out: {suggestion.command}",
                error_message="Command execution timed out"
            )
        except Exception as e:
            return FixResult(
                success=False,
                description=f"Command execution failed: {suggestion.command}",
                error_message=str(e)
            )

    def _apply_code_fix(
        self,
        suggestion: FixSuggestion,
        analysis: AnalysisResult,
        dry_run: bool
    ) -> FixResult:
        """Apply a fix that modifies source code."""
        error = analysis.error

        # Need a file path to modify
        file_path = suggestion.file_path or error.file_path
        if not file_path or not Path(file_path).exists():
            return FixResult(
                success=False,
                description="Cannot apply code fix without valid file path",
                error_message=f"File not found: {file_path}"
            )

        # Read the original file
        try:
            with open(file_path, 'r') as f:
                original_code = f.read()
        except Exception as e:
            return FixResult(
                success=False,
                description=f"Cannot read file: {file_path}",
                error_message=str(e)
            )

        # Generate the fix based on error type and suggestion
        try:
            fixed_code = self._generate_code_fix(
                original_code,
                error,
                suggestion
            )
        except Exception as e:
            return FixResult(
                success=False,
                description="Failed to generate code fix",
                error_message=str(e)
            )

        # If no changes, report that
        if fixed_code == original_code:
            return FixResult(
                success=False,
                description="No code changes generated",
                error_message="Fix generator did not produce any changes"
            )

        # Generate diff
        diff = self._generate_diff(original_code, fixed_code, file_path)

        if dry_run:
            return FixResult(
                success=True,
                description=f"[DRY RUN] Would modify: {file_path}",
                diff=diff
            )

        # Create backup
        backup_path = None
        if self.config.safety.backup_before_fix:
            backup_path = self._create_backup(file_path)

        # Apply the fix
        try:
            # If sandbox mode, write to temp file first
            if self.config.safety.sandbox_execution:
                with tempfile.NamedTemporaryFile(
                    mode='w', suffix='.py', delete=False
                ) as tmp:
                    tmp.write(fixed_code)
                    tmp_path = tmp.name

                # Validate the temp file
                try:
                    ast.parse(fixed_code)
                except SyntaxError as e:
                    os.unlink(tmp_path)
                    return FixResult(
                        success=False,
                        description="Generated fix has syntax errors",
                        error_message=str(e),
                        backup_path=backup_path
                    )

                # Replace original with temp
                shutil.move(tmp_path, file_path)
            else:
                # Direct write
                with open(file_path, 'w') as f:
                    f.write(fixed_code)

            return FixResult(
                success=True,
                description=f"Successfully modified: {file_path}",
                diff=diff,
                backup_path=backup_path,
                rollback_info={
                    "file_path": file_path,
                    "original_code": original_code,
                    "backup_path": backup_path
                }
            )

        except Exception as e:
            # Attempt to restore from backup
            if backup_path:
                self._restore_backup(backup_path, file_path)

            return FixResult(
                success=False,
                description=f"Failed to write fix to: {file_path}",
                error_message=str(e),
                backup_path=backup_path
            )

    def _apply_config_fix(
        self,
        suggestion: FixSuggestion,
        analysis: AnalysisResult,
        dry_run: bool
    ) -> FixResult:
        """Apply a configuration-related fix."""
        # Similar to code fix but for config files
        return self._apply_code_fix(suggestion, analysis, dry_run)

    def _apply_retry_fix(
        self,
        suggestion: FixSuggestion,
        analysis: AnalysisResult,
        dry_run: bool
    ) -> FixResult:
        """Apply a retry-based fix (just re-run the operation)."""
        return FixResult(
            success=True,
            description="Retry fix - operation will be re-attempted",
            diff=None
        )

    def _generate_code_fix(
        self,
        original_code: str,
        error: DetectedError,
        suggestion: FixSuggestion
    ) -> str:
        """
        Generate the actual code fix.

        This method implements various code transformations based on
        the error type and suggestion.
        """
        code = original_code
        line_number = suggestion.line_number or error.line_number or 0

        # If specific code_change is provided, use it
        if suggestion.code_change:
            old = suggestion.code_change.get("old", "")
            new = suggestion.code_change.get("new", "")
            if old and new:
                code = code.replace(old, new)
                return code

        # Handle specific error types
        if error.error_type == ErrorType.SYNTAX:
            code = self._fix_syntax_error(code, error, line_number)

        elif error.error_type == ErrorType.LOGIC:
            # Type error with NoneType
            if error.exception_type == "TypeError" and "NoneType" in error.message:
                # Extract variable name from error message
                match = re.search(r"'(\w+)'", error.message)
                if match:
                    var_name = match.group(1)
                    code = self.transformer.add_null_check(code, var_name, line_number)

            # KeyError - use .get()
            elif error.exception_type == "KeyError":
                code = self.transformer.use_dict_get(code, line_number)

            # IndexError - add bounds check
            elif error.exception_type == "IndexError":
                code = self._add_generic_bounds_check(code, line_number)

        elif error.error_type == ErrorType.NETWORK:
            # Add retry logic for network errors
            code = self.transformer.add_retry_logic(code, line_number)

        elif error.error_type == ErrorType.DEPENDENCY:
            # Usually handled by command fix, but if we get here...
            pass

        return code

    def _fix_syntax_error(self, code: str, error: DetectedError, line_number: int) -> str:
        """Attempt to fix syntax errors."""
        lines = code.split('\n')

        if line_number < 1 or line_number > len(lines):
            return code

        line = lines[line_number - 1]
        message = error.message.lower()

        # Missing colon
        if "expected ':'" in message or ("invalid syntax" in message and
                                         any(kw in line for kw in ['if', 'for', 'while', 'def', 'class', 'elif', 'else', 'try', 'except', 'with'])):
            # Check if line ends without colon but should have one
            stripped = line.rstrip()
            if stripped and not stripped.endswith(':') and not stripped.endswith(','):
                lines[line_number - 1] = stripped + ':'

        # Unclosed parenthesis
        elif "unexpected eof" in message or "was never closed" in message:
            # Count brackets
            open_parens = line.count('(') - line.count(')')
            open_brackets = line.count('[') - line.count(']')
            open_braces = line.count('{') - line.count('}')

            if open_parens > 0:
                lines[line_number - 1] = line + ')' * open_parens
            if open_brackets > 0:
                lines[line_number - 1] = lines[line_number - 1] + ']' * open_brackets
            if open_braces > 0:
                lines[line_number - 1] = lines[line_number - 1] + '}' * open_braces

        # Unexpected indent
        elif "unexpected indent" in message:
            lines = self.transformer.fix_indentation(code).split('\n')

        return '\n'.join(lines)

    def _add_generic_bounds_check(self, code: str, line_number: int) -> str:
        """Add a generic bounds check when we don't know the variable names."""
        lines = code.split('\n')
        if 0 < line_number <= len(lines):
            line = lines[line_number - 1]
            indent = len(line) - len(line.lstrip())
            indent_str = ' ' * indent

            # Look for list[index] pattern
            match = re.search(r'(\w+)\[(\w+)\]', line)
            if match:
                list_var, index_var = match.groups()
                return self.transformer.add_bounds_check(code, line_number, list_var, index_var)

        return code

    def _create_backup(self, file_path: str) -> str:
        """Create a backup of a file before modifying it."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = Path(file_path).name
        backup_name = f"{file_name}.{timestamp}.backup"
        backup_path = self.backup_dir / backup_name

        shutil.copy2(file_path, backup_path)
        return str(backup_path)

    def _restore_backup(self, backup_path: str, target_path: str) -> bool:
        """Restore a file from backup."""
        try:
            shutil.copy2(backup_path, target_path)
            return True
        except Exception:
            return False

    def _generate_diff(self, original: str, modified: str, file_path: str) -> str:
        """Generate a unified diff between original and modified code."""
        original_lines = original.splitlines(keepends=True)
        modified_lines = modified.splitlines(keepends=True)

        diff = unified_diff(
            original_lines,
            modified_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}"
        )
        return ''.join(diff)

    def rollback(self, fix_result: FixResult) -> bool:
        """
        Rollback a previously applied fix.

        Args:
            fix_result: The result from applying the fix

        Returns:
            True if rollback was successful
        """
        rollback_info = fix_result.rollback_info

        if not rollback_info:
            return False

        file_path = rollback_info.get("file_path")
        original_code = rollback_info.get("original_code")
        backup_path = rollback_info.get("backup_path")

        if not file_path:
            return False

        try:
            if backup_path and Path(backup_path).exists():
                # Restore from backup file
                return self._restore_backup(backup_path, file_path)
            elif original_code:
                # Restore from stored original code
                with open(file_path, 'w') as f:
                    f.write(original_code)
                return True
        except Exception:
            return False

        return False

    def generate_fix_preview(
        self,
        suggestion: FixSuggestion,
        analysis: AnalysisResult
    ) -> str:
        """
        Generate a preview of what a fix would do without applying it.

        Args:
            suggestion: The fix suggestion
            analysis: The analysis result

        Returns:
            A string describing/showing the fix
        """
        result = self.apply_fix(suggestion, analysis, dry_run=True)

        preview_parts = [
            f"Fix: {suggestion.description}",
            f"Reasoning: {suggestion.reasoning}",
            f"Confidence: {suggestion.confidence.value}",
        ]

        if result.diff:
            preview_parts.append(f"\nChanges:\n{result.diff}")

        if suggestion.command:
            preview_parts.append(f"\nCommand: {suggestion.command}")

        return '\n'.join(preview_parts)
