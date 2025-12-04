"""
Ansible Environment Handler for Self-Healing Code System
=========================================================

Provides specialized handling for Ansible playbooks and roles,
including syntax checking, role management, and connection handling.
"""

import subprocess
import re
import os
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path

from ..config import EnvironmentType, ErrorType, get_config
from ..detector import DetectedError


class AnsibleEnvironment:
    """
    Handler for Ansible execution environment.

    Provides methods to run Ansible playbooks, detect errors, generate fixes,
    and manage roles and collections.
    """

    def __init__(self, working_dir: Optional[str] = None):
        """
        Initialize the Ansible environment handler.

        Args:
            working_dir: Ansible working directory
        """
        self.config = get_config()
        self.environment_type = EnvironmentType.ANSIBLE
        self.working_dir = working_dir or os.getcwd()

    def run_playbook(
        self,
        playbook_path: str,
        inventory: Optional[str] = None,
        extra_vars: Optional[Dict[str, str]] = None,
        check_mode: bool = False,
        diff_mode: bool = False,
        timeout: int = 3600
    ) -> Tuple[int, str, str]:
        """
        Run an Ansible playbook.

        Args:
            playbook_path: Path to the playbook
            inventory: Inventory file or host pattern
            extra_vars: Extra variables to pass
            check_mode: Run in check mode (dry run)
            diff_mode: Show diffs of changes
            timeout: Timeout in seconds

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        cmd = ['ansible-playbook', playbook_path]

        if inventory:
            cmd.extend(['-i', inventory])

        if extra_vars:
            for key, value in extra_vars.items():
                cmd.extend(['-e', f'{key}={value}'])

        if check_mode:
            cmd.append('--check')

        if diff_mode:
            cmd.append('--diff')

        try:
            result = subprocess.run(
                cmd,
                cwd=self.working_dir,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return (result.returncode, result.stdout, result.stderr)
        except subprocess.TimeoutExpired:
            return (-1, "", "Ansible playbook execution timed out")
        except FileNotFoundError:
            return (-1, "", "Ansible not found in PATH")

    def syntax_check(self, playbook_path: str) -> Tuple[bool, str]:
        """
        Run ansible-playbook syntax check.

        Args:
            playbook_path: Path to the playbook

        Returns:
            Tuple of (valid, output)
        """
        cmd = ['ansible-playbook', '--syntax-check', playbook_path]

        try:
            result = subprocess.run(
                cmd,
                cwd=self.working_dir,
                capture_output=True,
                text=True,
                timeout=60
            )
            return (result.returncode == 0, result.stdout + result.stderr)
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            return (False, str(e))

    def lint(self, playbook_path: str) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Run ansible-lint on a playbook.

        Args:
            playbook_path: Path to the playbook

        Returns:
            Tuple of (passed, list of issues)
        """
        issues = []

        try:
            result = subprocess.run(
                ['ansible-lint', '--parseable', playbook_path],
                cwd=self.working_dir,
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode != 0:
                # Parse lint output
                for line in result.stdout.split('\n'):
                    if ':' in line:
                        parts = line.split(':')
                        if len(parts) >= 3:
                            issues.append({
                                "file": parts[0],
                                "line": parts[1],
                                "message": ':'.join(parts[2:])
                            })

            return (result.returncode == 0, issues)
        except FileNotFoundError:
            return (True, [])  # ansible-lint not installed
        except subprocess.TimeoutExpired:
            return (False, [{"message": "Lint check timed out"}])

    def install_role(self, role: str) -> Tuple[bool, str]:
        """
        Install an Ansible role using ansible-galaxy.

        Args:
            role: Role name to install

        Returns:
            Tuple of (success, output)
        """
        try:
            result = subprocess.run(
                ['ansible-galaxy', 'install', role],
                capture_output=True,
                text=True,
                timeout=300
            )
            return (result.returncode == 0, result.stdout + result.stderr)
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            return (False, str(e))

    def install_collection(self, collection: str) -> Tuple[bool, str]:
        """
        Install an Ansible collection using ansible-galaxy.

        Args:
            collection: Collection name to install

        Returns:
            Tuple of (success, output)
        """
        try:
            result = subprocess.run(
                ['ansible-galaxy', 'collection', 'install', collection],
                capture_output=True,
                text=True,
                timeout=300
            )
            return (result.returncode == 0, result.stdout + result.stderr)
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            return (False, str(e))

    def get_installed_roles(self) -> List[str]:
        """
        Get list of installed Ansible roles.

        Returns:
            List of role names
        """
        try:
            result = subprocess.run(
                ['ansible-galaxy', 'list'],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                roles = []
                for line in result.stdout.split('\n'):
                    if ',' in line:
                        role_name = line.split(',')[0].strip().lstrip('-').strip()
                        if role_name:
                            roles.append(role_name)
                return roles
        except Exception:
            pass
        return []

    def parse_error(self, output: str) -> DetectedError:
        """
        Parse Ansible error output into a DetectedError.

        Args:
            output: Ansible error output

        Returns:
            DetectedError with parsed information
        """
        error_type = ErrorType.UNKNOWN
        message = output[:500]
        file_path = None
        line_number = None

        # Try to extract file information
        file_match = re.search(r'in\s+(\S+\.ya?ml)', output)
        if file_match:
            file_path = file_match.group(1)

        line_match = re.search(r'line\s+(\d+)', output)
        if line_match:
            line_number = int(line_match.group(1))

        # Determine error type
        output_lower = output.lower()

        if "syntax error" in output_lower:
            error_type = ErrorType.SYNTAX
        elif "role" in output_lower and "not found" in output_lower:
            error_type = ErrorType.DEPENDENCY
            match = re.search(r"role '([^']+)'", output)
            if match:
                message = f"Missing role: {match.group(1)}"
        elif "module" in output_lower and ("not found" in output_lower or "couldn't resolve" in output_lower):
            error_type = ErrorType.DEPENDENCY
        elif "unreachable" in output_lower:
            error_type = ErrorType.NETWORK
            message = "Host unreachable"
        elif "permission denied" in output_lower:
            error_type = ErrorType.PERMISSION
        elif "fatal" in output_lower:
            error_type = ErrorType.RUNTIME

        return DetectedError(
            error_type=error_type,
            environment=EnvironmentType.ANSIBLE,
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
        Generate a fix for an Ansible error.

        Args:
            error: The detected error

        Returns:
            Fix information or None if no fix available
        """
        if error.error_type == ErrorType.DEPENDENCY:
            # Extract role/collection name from error
            message = error.message

            role_match = re.search(r"role '([^']+)'", message)
            if role_match:
                role = role_match.group(1)
                return {
                    "type": "command",
                    "command": f"ansible-galaxy install {role}",
                    "description": f"Install missing role: {role}",
                    "reasoning": "The required Ansible role is not installed"
                }

            module_match = re.search(r"module/action '([^']+)'", message)
            if module_match:
                module = module_match.group(1)
                # Try to find the collection
                if '.' in module:
                    collection = '.'.join(module.split('.')[:2])
                    return {
                        "type": "command",
                        "command": f"ansible-galaxy collection install {collection}",
                        "description": f"Install collection containing: {module}",
                        "reasoning": "The module is in a collection that's not installed"
                    }

        elif error.error_type == ErrorType.NETWORK:
            return {
                "type": "code_change",
                "description": "Add retry and connection timeout",
                "reasoning": "Network issues may be temporary",
                "suggested_addition": """
  vars:
    ansible_ssh_common_args: '-o ConnectTimeout=10'
  retries: 3
  delay: 5
"""
            }

        elif error.error_type == ErrorType.SYNTAX:
            return {
                "type": "code_change",
                "description": "Fix YAML syntax",
                "reasoning": "Playbook has invalid YAML syntax",
                "file_path": error.file_path
            }

        return None

    def validate_yaml(self, file_path: str) -> Tuple[bool, str]:
        """
        Validate YAML syntax of a file.

        Args:
            file_path: Path to YAML file

        Returns:
            Tuple of (valid, error_message)
        """
        try:
            import yaml
            with open(file_path, 'r') as f:
                yaml.safe_load(f)
            return (True, "")
        except yaml.YAMLError as e:
            return (False, str(e))
        except FileNotFoundError:
            return (False, f"File not found: {file_path}")
        except ImportError:
            # PyYAML not installed, try ansible-playbook syntax check instead
            return self.syntax_check(file_path)
