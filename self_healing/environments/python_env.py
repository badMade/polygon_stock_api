"""
Python Environment Handler for Self-Healing Code System
========================================================

Provides specialized handling for Python scripts and applications,
including dependency management, syntax fixing, and runtime patching.
"""

import ast
import subprocess
import sys
import re
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path

from ..config import EnvironmentType, ErrorType, get_config
from ..detector import DetectedError


class PythonEnvironment:
    """
    Handler for Python execution environment.

    Provides methods to run Python code, detect errors, generate fixes,
    and manage dependencies.
    """

    def __init__(self):
        """Initialize the Python environment handler."""
        self.config = get_config()
        self.environment_type = EnvironmentType.PYTHON

        # Cache for installed packages
        self._installed_packages: Optional[set] = None

    def run_script(
        self,
        script_path: str,
        args: Optional[List[str]] = None,
        timeout: int = 300
    ) -> Tuple[int, str, str]:
        """
        Run a Python script and capture output.

        Args:
            script_path: Path to the Python script
            args: Command line arguments
            timeout: Timeout in seconds

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        cmd = [sys.executable, script_path]
        if args:
            cmd.extend(args)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return (result.returncode, result.stdout, result.stderr)
        except subprocess.TimeoutExpired:
            return (-1, "", "Script execution timed out")

    def run_code(
        self,
        code: str,
        globals_dict: Optional[Dict[str, Any]] = None,
        locals_dict: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[Any], Optional[Exception]]:
        """
        Execute Python code and capture result or error.

        Args:
            code: Python code to execute
            globals_dict: Global namespace
            locals_dict: Local namespace

        Returns:
            Tuple of (success, result, exception)
        """
        globals_dict = globals_dict or {}
        locals_dict = locals_dict or {}

        try:
            compiled = compile(code, '<string>', 'exec')
            exec(compiled, globals_dict, locals_dict)
            return (True, locals_dict, None)
        except Exception as e:
            return (False, None, e)

    def validate_syntax(self, code: str) -> Tuple[bool, Optional[str]]:
        """
        Validate Python syntax without execution.

        Args:
            code: Python code to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            ast.parse(code)
            return (True, None)
        except SyntaxError as e:
            return (False, f"Line {e.lineno}: {e.msg}")

    def get_installed_packages(self, refresh: bool = False) -> set:
        """
        Get the set of installed Python packages.

        Args:
            refresh: Force refresh of package list

        Returns:
            Set of installed package names
        """
        if self._installed_packages is None or refresh:
            try:
                result = subprocess.run(
                    [sys.executable, '-m', 'pip', 'list', '--format=json'],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    import json
                    packages = json.loads(result.stdout)
                    self._installed_packages = {
                        pkg['name'].lower() for pkg in packages
                    }
                else:
                    self._installed_packages = set()
            except Exception:
                self._installed_packages = set()

        return self._installed_packages

    def install_package(self, package: str) -> Tuple[bool, str]:
        """
        Install a Python package using pip.

        Args:
            package: Package name to install

        Returns:
            Tuple of (success, output)
        """
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'install', package],
                capture_output=True,
                text=True,
                timeout=self.config.python_settings.get("pip_timeout", 60)
            )
            # Refresh package cache
            self._installed_packages = None
            return (result.returncode == 0, result.stdout + result.stderr)
        except subprocess.TimeoutExpired:
            return (False, "Package installation timed out")

    def extract_missing_module(self, error_message: str) -> Optional[str]:
        """
        Extract missing module name from ImportError message.

        Args:
            error_message: The error message

        Returns:
            Module name if found, None otherwise
        """
        patterns = [
            r"No module named '([^']+)'",
            r"cannot import name '([^']+)'",
            r"ModuleNotFoundError: No module named '([^']+)'"
        ]

        for pattern in patterns:
            match = re.search(pattern, error_message)
            if match:
                return match.group(1).split('.')[0]  # Get top-level module

        return None

    def module_to_package(self, module: str) -> str:
        """
        Convert module name to pip package name.

        Args:
            module: Module name

        Returns:
            Package name for pip
        """
        # Common module to package mappings
        mapping = {
            "PIL": "Pillow",
            "cv2": "opencv-python",
            "sklearn": "scikit-learn",
            "skimage": "scikit-image",
            "yaml": "PyYAML",
            "bs4": "beautifulsoup4",
            "dateutil": "python-dateutil",
            "dotenv": "python-dotenv",
            "jwt": "PyJWT",
            "crypto": "pycryptodome",
            "serial": "pyserial",
        }
        return mapping.get(module, module)

    def generate_syntax_fix(
        self,
        code: str,
        error: DetectedError
    ) -> Optional[str]:
        """
        Attempt to fix Python syntax errors.

        Args:
            code: Original code
            error: The detected syntax error

        Returns:
            Fixed code or None if unable to fix
        """
        lines = code.split('\n')
        line_num = error.line_number

        if not line_num or line_num < 1 or line_num > len(lines):
            return None

        line = lines[line_num - 1]
        message = error.message.lower()

        # Missing colon
        if "expected ':'" in message:
            if not line.rstrip().endswith(':'):
                lines[line_num - 1] = line.rstrip() + ':'
                return '\n'.join(lines)

        # Unclosed parenthesis/bracket
        if "eof" in message or "was never closed" in message:
            # Count brackets in the problematic line
            open_count = line.count('(') + line.count('[') + line.count('{')
            close_count = line.count(')') + line.count(']') + line.count('}')

            if open_count > close_count:
                # Try to close with appropriate bracket
                if line.count('(') > line.count(')'):
                    lines[line_num - 1] = line.rstrip() + ')'
                elif line.count('[') > line.count(']'):
                    lines[line_num - 1] = line.rstrip() + ']'
                elif line.count('{') > line.count('}'):
                    lines[line_num - 1] = line.rstrip() + '}'
                return '\n'.join(lines)

        # Invalid syntax - try removing trailing characters
        if "invalid syntax" in message:
            # Common fix: remove trailing semicolon
            if line.rstrip().endswith(';'):
                lines[line_num - 1] = line.rstrip()[:-1]
                return '\n'.join(lines)

        return None

    def lint_code(self, code: str) -> List[Dict[str, Any]]:
        """
        Run linting on Python code.

        Args:
            code: Python code to lint

        Returns:
            List of lint issues
        """
        issues = []

        # Use AST to find some issues
        try:
            tree = ast.parse(code)

            for node in ast.walk(tree):
                # Check for bare except
                if isinstance(node, ast.ExceptHandler) and node.type is None:
                    issues.append({
                        "line": node.lineno,
                        "message": "Bare except clause (catches all exceptions)",
                        "severity": "warning"
                    })

                # Check for mutable default argument
                if isinstance(node, ast.FunctionDef):
                    for default in node.args.defaults:
                        if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                            issues.append({
                                "line": node.lineno,
                                "message": f"Mutable default argument in {node.name}()",
                                "severity": "warning"
                            })

                # Check for unused imports (simplified)
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        # This is a simplified check
                        pass

        except SyntaxError:
            pass

        return issues

    def get_function_at_line(
        self,
        code: str,
        line_number: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get the function containing a specific line.

        Args:
            code: Python source code
            line_number: Line number to find

        Returns:
            Dict with function info or None
        """
        try:
            tree = ast.parse(code)

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    if hasattr(node, 'lineno') and hasattr(node, 'end_lineno'):
                        if node.lineno <= line_number <= node.end_lineno:
                            return {
                                "name": node.name,
                                "start_line": node.lineno,
                                "end_line": node.end_lineno,
                                "args": [arg.arg for arg in node.args.args]
                            }
        except SyntaxError:
            pass

        return None
