"""
Bash Environment Handler for Self-Healing Code System
======================================================

Provides specialized handling for Bash/shell scripts,
including syntax checking, command verification, and script fixing.
"""

import subprocess
import re
import os
import shutil
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path

from ..config import EnvironmentType, ErrorType, get_config
from ..detector import DetectedError


class BashEnvironment:
    """
    Handler for Bash/shell execution environment.

    Provides methods to run shell scripts, detect errors, generate fixes,
    and manage command dependencies.
    """

    def __init__(self, shell: str = "/bin/bash"):
        """
        Initialize the Bash environment handler.

        Args:
            shell: Path to the shell to use
        """
        self.config = get_config()
        self.environment_type = EnvironmentType.BASH
        self.shell = shell

    def run_script(
        self,
        script_path: str,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: int = 300
    ) -> Tuple[int, str, str]:
        """
        Run a shell script.

        Args:
            script_path: Path to the script
            args: Command line arguments
            env: Environment variables
            timeout: Timeout in seconds

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        cmd = [self.shell, script_path]
        if args:
            cmd.extend(args)

        script_env = os.environ.copy()
        if env:
            script_env.update(env)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=script_env
            )
            return (result.returncode, result.stdout, result.stderr)
        except subprocess.TimeoutExpired:
            return (-1, "", "Script execution timed out")
        except FileNotFoundError as e:
            return (-1, "", str(e))

    def run_command(
        self,
        command: str,
        timeout: int = 60
    ) -> Tuple[int, str, str]:
        """
        Run a shell command.

        Args:
            command: The command to run
            timeout: Timeout in seconds

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        try:
            result = subprocess.run(
                command,
                shell=True,
                executable=self.shell,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return (result.returncode, result.stdout, result.stderr)
        except subprocess.TimeoutExpired:
            return (-1, "", "Command execution timed out")

    def syntax_check(self, script_path: str) -> Tuple[bool, str]:
        """
        Check script syntax without execution.

        Args:
            script_path: Path to the script

        Returns:
            Tuple of (valid, error_message)
        """
        try:
            result = subprocess.run(
                [self.shell, '-n', script_path],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                return (True, "")
            return (False, result.stderr)
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            return (False, str(e))

    def check_command_exists(self, command: str) -> bool:
        """
        Check if a command exists in PATH.

        Args:
            command: Command name to check

        Returns:
            True if command exists
        """
        return shutil.which(command) is not None

    def get_missing_commands(self, script_path: str) -> List[str]:
        """
        Find commands used in a script that are not installed.

        Args:
            script_path: Path to the script

        Returns:
            List of missing command names
        """
        missing = []

        try:
            with open(script_path, 'r') as f:
                content = f.read()

            # Find command invocations (simplified)
            # This looks for words at the start of lines or after pipes/semicolons
            patterns = [
                r'^\s*(\w+)\s',           # Start of line
                r'\|\s*(\w+)\s',          # After pipe
                r';\s*(\w+)\s',           # After semicolon
                r'\$\((\w+)\s',           # Command substitution
                r'`(\w+)\s',              # Backtick substitution
            ]

            commands = set()
            for pattern in patterns:
                matches = re.findall(pattern, content, re.MULTILINE)
                commands.update(matches)

            # Filter out shell builtins and keywords
            builtins = {
                'if', 'then', 'else', 'elif', 'fi', 'case', 'esac',
                'for', 'while', 'until', 'do', 'done', 'in',
                'function', 'return', 'exit', 'break', 'continue',
                'echo', 'printf', 'read', 'local', 'export', 'unset',
                'set', 'shift', 'test', 'true', 'false', 'cd', 'pwd',
                'source', '.', 'eval', 'exec', 'trap', 'wait'
            }

            for cmd in commands:
                if cmd not in builtins and not self.check_command_exists(cmd):
                    missing.append(cmd)

        except Exception:
            pass

        return missing

    def parse_error(self, output: str, script_path: Optional[str] = None) -> DetectedError:
        """
        Parse Bash error output into a DetectedError.

        Args:
            output: Bash error output
            script_path: Path to the script (if known)

        Returns:
            DetectedError with parsed information
        """
        error_type = ErrorType.UNKNOWN
        message = output[:500]
        file_path = script_path
        line_number = None

        # Try to extract line number
        line_match = re.search(r'line\s+(\d+)', output)
        if line_match:
            line_number = int(line_match.group(1))

        output_lower = output.lower()

        # Determine error type
        if "syntax error" in output_lower or "unexpected token" in output_lower:
            error_type = ErrorType.SYNTAX
        elif "command not found" in output_lower:
            error_type = ErrorType.DEPENDENCY
            # Extract command name
            match = re.search(r'(\S+):\s*command not found', output)
            if match:
                message = f"Command not found: {match.group(1)}"
        elif "permission denied" in output_lower:
            error_type = ErrorType.PERMISSION
        elif "no such file or directory" in output_lower:
            error_type = ErrorType.CONFIGURATION
        elif "operation not permitted" in output_lower:
            error_type = ErrorType.PERMISSION

        return DetectedError(
            error_type=error_type,
            environment=EnvironmentType.BASH,
            message=message,
            file_path=file_path,
            line_number=line_number,
            stderr=output
        )

    def generate_fix(
        self,
        error: DetectedError
    ) -> Optional[Dict[str, Any]]:
        """
        Generate a fix for a Bash error.

        Args:
            error: The detected error

        Returns:
            Fix information or None if no fix available
        """
        if error.error_type == ErrorType.DEPENDENCY:
            # Extract command name
            match = re.search(r'Command not found:\s*(\S+)', error.message)
            if match:
                command = match.group(1)

                # Try to suggest package to install
                package = self._command_to_package(command)

                return {
                    "type": "command",
                    "command": f"apt-get install -y {package} || yum install -y {package}",
                    "description": f"Install missing command: {command}",
                    "reasoning": f"The command '{command}' is not installed"
                }

        elif error.error_type == ErrorType.PERMISSION:
            if error.file_path:
                return {
                    "type": "command",
                    "command": f"chmod +x {error.file_path}",
                    "description": "Make script executable",
                    "reasoning": "Script may need execute permission"
                }

        elif error.error_type == ErrorType.SYNTAX:
            return {
                "type": "code_change",
                "description": "Fix script syntax",
                "reasoning": "Script has invalid Bash syntax",
                "file_path": error.file_path
            }

        return None

    def _command_to_package(self, command: str) -> str:
        """
        Map a command name to its likely package name.

        Args:
            command: Command name

        Returns:
            Package name
        """
        # Common command to package mappings
        mapping = {
            'jq': 'jq',
            'curl': 'curl',
            'wget': 'wget',
            'git': 'git',
            'vim': 'vim',
            'nano': 'nano',
            'zip': 'zip',
            'unzip': 'unzip',
            'tar': 'tar',
            'gzip': 'gzip',
            'make': 'make',
            'gcc': 'gcc',
            'python3': 'python3',
            'pip3': 'python3-pip',
            'node': 'nodejs',
            'npm': 'npm',
            'docker': 'docker.io',
            'kubectl': 'kubectl',
            'aws': 'awscli',
            'az': 'azure-cli',
            'gcloud': 'google-cloud-sdk',
            'ssh': 'openssh-client',
            'rsync': 'rsync',
            'htop': 'htop',
            'tree': 'tree',
            'netcat': 'netcat',
            'nc': 'netcat',
            'nmap': 'nmap',
            'dig': 'dnsutils',
            'host': 'dnsutils',
        }
        return mapping.get(command, command)

    def fix_script_syntax(
        self,
        script_path: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Attempt to fix common Bash syntax issues.

        Args:
            script_path: Path to the script

        Returns:
            Tuple of (fixed, new_content or error_message)
        """
        try:
            with open(script_path, 'r') as f:
                content = f.read()

            original = content
            lines = content.split('\n')
            fixed_lines = []

            for i, line in enumerate(lines):
                fixed_line = line

                # Fix missing spaces in test conditions
                # [condition] -> [ condition ]
                fixed_line = re.sub(
                    r'\[(\S)',
                    r'[ \1',
                    fixed_line
                )
                fixed_line = re.sub(
                    r'(\S)\]',
                    r'\1 ]',
                    fixed_line
                )

                # Fix missing 'then' after 'if'
                if re.match(r'^\s*if\s+.+;\s*$', line):
                    if not line.rstrip().endswith('then'):
                        fixed_line = line.rstrip() + ' then'

                # Fix missing 'do' after 'for/while'
                if re.match(r'^\s*(for|while)\s+.+;\s*$', line):
                    if not line.rstrip().endswith('do'):
                        fixed_line = line.rstrip() + ' do'

                fixed_lines.append(fixed_line)

            new_content = '\n'.join(fixed_lines)

            if new_content != original:
                return (True, new_content)
            return (False, "No fixes applied")

        except Exception as e:
            return (False, str(e))

    def add_strict_mode(self, script_content: str) -> str:
        """
        Add strict mode to a Bash script.

        Args:
            script_content: Original script content

        Returns:
            Script with strict mode added
        """
        strict_mode = "set -euo pipefail\n"

        lines = script_content.split('\n')

        # Find where to insert (after shebang and comments)
        insert_pos = 0
        for i, line in enumerate(lines):
            if line.startswith('#!'):
                insert_pos = i + 1
            elif line.startswith('#'):
                insert_pos = i + 1
            elif line.strip():
                break

        lines.insert(insert_pos, strict_mode)
        return '\n'.join(lines)

    def get_script_info(self, script_path: str) -> Dict[str, Any]:
        """
        Get information about a Bash script.

        Args:
            script_path: Path to the script

        Returns:
            Dictionary with script information
        """
        info = {
            "path": script_path,
            "exists": False,
            "executable": False,
            "shebang": None,
            "has_strict_mode": False,
            "line_count": 0,
            "functions": [],
            "missing_commands": []
        }

        path = Path(script_path)
        if not path.exists():
            return info

        info["exists"] = True
        info["executable"] = os.access(script_path, os.X_OK)

        try:
            with open(script_path, 'r') as f:
                content = f.read()

            lines = content.split('\n')
            info["line_count"] = len(lines)

            # Check shebang
            if lines and lines[0].startswith('#!'):
                info["shebang"] = lines[0]

            # Check for strict mode
            info["has_strict_mode"] = 'set -e' in content or 'set -o errexit' in content

            # Find function definitions
            func_pattern = r'^\s*(?:function\s+)?(\w+)\s*\(\)'
            info["functions"] = re.findall(func_pattern, content, re.MULTILINE)

            # Find missing commands
            info["missing_commands"] = self.get_missing_commands(script_path)

        except Exception:
            pass

        return info
