"""
Terraform Environment Handler for Self-Healing Code System
===========================================================

Provides specialized handling for Terraform infrastructure-as-code,
including configuration validation, provider management, and state handling.
"""

import subprocess
import re
import json
import os
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path

from ..config import EnvironmentType, ErrorType, get_config
from ..detector import DetectedError


class TerraformEnvironment:
    """
    Handler for Terraform execution environment.

    Provides methods to run Terraform commands, detect errors, generate fixes,
    and manage infrastructure state.
    """

    def __init__(self, working_dir: Optional[str] = None):
        """
        Initialize the Terraform environment handler.

        Args:
            working_dir: Terraform working directory
        """
        self.config = get_config()
        self.environment_type = EnvironmentType.TERRAFORM
        self.working_dir = working_dir or os.getcwd()

    def run_command(
        self,
        command: str,
        args: Optional[List[str]] = None,
        timeout: int = 600
    ) -> Tuple[int, str, str]:
        """
        Run a Terraform command.

        Args:
            command: Terraform command (init, plan, apply, etc.)
            args: Additional arguments
            timeout: Timeout in seconds

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        cmd = ['terraform', command]
        if args:
            cmd.extend(args)

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
            return (-1, "", "Terraform command timed out")
        except FileNotFoundError:
            return (-1, "", "Terraform not found in PATH")

    def init(self, upgrade: bool = False) -> Tuple[bool, str]:
        """
        Run terraform init.

        Args:
            upgrade: Whether to upgrade providers

        Returns:
            Tuple of (success, output)
        """
        args = []
        if upgrade:
            args.append('-upgrade')

        exit_code, stdout, stderr = self.run_command('init', args)
        return (exit_code == 0, stdout + stderr)

    def validate(self) -> Tuple[bool, str]:
        """
        Run terraform validate.

        Returns:
            Tuple of (valid, output)
        """
        exit_code, stdout, stderr = self.run_command('validate', ['-json'])

        if exit_code == 0:
            return (True, "Configuration is valid")

        # Parse JSON output for detailed errors
        try:
            result = json.loads(stdout)
            if not result.get('valid', False):
                errors = result.get('diagnostics', [])
                messages = [
                    f"{e.get('summary', 'Unknown error')}: {e.get('detail', '')}"
                    for e in errors if e.get('severity') == 'error'
                ]
                return (False, "; ".join(messages))
        except json.JSONDecodeError:
            pass

        return (False, stderr or stdout)

    def plan(self, out_file: Optional[str] = None) -> Tuple[bool, str]:
        """
        Run terraform plan.

        Args:
            out_file: Optional file to save the plan

        Returns:
            Tuple of (success, output)
        """
        args = ['-no-color']
        if out_file:
            args.extend(['-out', out_file])

        exit_code, stdout, stderr = self.run_command('plan', args)
        return (exit_code == 0, stdout + stderr)

    def apply(self, auto_approve: bool = False) -> Tuple[bool, str]:
        """
        Run terraform apply.

        Args:
            auto_approve: Skip interactive approval

        Returns:
            Tuple of (success, output)
        """
        args = ['-no-color']
        if auto_approve:
            args.append('-auto-approve')

        exit_code, stdout, stderr = self.run_command('apply', args)
        return (exit_code == 0, stdout + stderr)

    def fmt(self, check: bool = False) -> Tuple[bool, str]:
        """
        Run terraform fmt.

        Args:
            check: Only check formatting, don't fix

        Returns:
            Tuple of (success/formatted, output)
        """
        args = []
        if check:
            args.append('-check')

        exit_code, stdout, stderr = self.run_command('fmt', args)
        return (exit_code == 0, stdout + stderr)

    def parse_error(self, output: str) -> DetectedError:
        """
        Parse Terraform error output into a DetectedError.

        Args:
            output: Terraform error output

        Returns:
            DetectedError with parsed information
        """
        error_type = ErrorType.UNKNOWN
        message = output[:500]
        file_path = None
        line_number = None

        # Try to extract file and line from error
        file_match = re.search(r'on (\S+\.tf) line (\d+)', output)
        if file_match:
            file_path = os.path.join(self.working_dir, file_match.group(1))
            line_number = int(file_match.group(2))

        # Determine error type
        if 'provider' in output.lower() and 'not found' in output.lower():
            error_type = ErrorType.DEPENDENCY
            message = "Terraform provider not found"
        elif 'invalid' in output.lower() or 'unsupported' in output.lower():
            error_type = ErrorType.SYNTAX
        elif 'error creating' in output.lower() or 'error applying' in output.lower():
            error_type = ErrorType.CONFIGURATION
        elif 'state' in output.lower() and 'lock' in output.lower():
            error_type = ErrorType.RESOURCE

        return DetectedError(
            error_type=error_type,
            environment=EnvironmentType.TERRAFORM,
            message=message,
            file_path=file_path,
            line_number=line_number,
            stderr=output
        )

    def get_providers(self) -> List[Dict[str, str]]:
        """
        Get list of required providers from configuration.

        Returns:
            List of provider dictionaries
        """
        providers = []

        for tf_file in Path(self.working_dir).glob('*.tf'):
            try:
                with open(tf_file, 'r') as f:
                    content = f.read()

                # Simple regex to find provider blocks
                matches = re.findall(
                    r'provider\s+"([^"]+)"',
                    content
                )
                for match in matches:
                    providers.append({
                        "name": match,
                        "source": f"hashicorp/{match}"
                    })
            except Exception:
                pass

        return providers

    def generate_fix(
        self,
        error: DetectedError
    ) -> Optional[Dict[str, Any]]:
        """
        Generate a fix for a Terraform error.

        Args:
            error: The detected error

        Returns:
            Fix information or None if no fix available
        """
        if error.error_type == ErrorType.DEPENDENCY:
            # Provider not found - run init
            return {
                "type": "command",
                "command": "terraform init",
                "description": "Initialize Terraform to install providers",
                "reasoning": "Terraform providers need to be installed before use"
            }

        elif error.error_type == ErrorType.SYNTAX:
            # Try formatting
            return {
                "type": "command",
                "command": "terraform fmt",
                "description": "Format Terraform files",
                "reasoning": "Formatting may fix some syntax issues"
            }

        elif error.error_type == ErrorType.RESOURCE:
            if 'lock' in error.message.lower():
                # State lock issue
                return {
                    "type": "command",
                    "command": "terraform force-unlock <LOCK_ID>",
                    "description": "Force unlock the state file",
                    "reasoning": "State file is locked by another process",
                    "requires_input": True
                }

        return None

    def get_state_resources(self) -> List[str]:
        """
        Get list of resources in current state.

        Returns:
            List of resource addresses
        """
        exit_code, stdout, stderr = self.run_command('state', ['list'])
        if exit_code == 0:
            return [r.strip() for r in stdout.split('\n') if r.strip()]
        return []
