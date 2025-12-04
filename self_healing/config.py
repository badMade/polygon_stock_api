"""
Configuration Module for Self-Healing Code System
==================================================

This module provides configuration management for the self-healing system.
It defines all configurable parameters including retry limits, logging options,
supported environments, and safety settings.

Configuration can be loaded from environment variables, config files, or
set programmatically.
"""

import os
import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum
from pathlib import Path


class ErrorType(Enum):
    """Enumeration of error types the self-healing system can handle."""
    SYNTAX = "syntax"           # Syntax errors in code/config
    LOGIC = "logic"             # Logic bugs (incorrect behavior)
    DEPENDENCY = "dependency"   # Missing or incompatible dependencies
    RUNTIME = "runtime"         # General runtime exceptions
    CONFIGURATION = "config"    # Configuration/environment issues
    NETWORK = "network"         # Network-related errors
    PERMISSION = "permission"   # Permission/access errors
    RESOURCE = "resource"       # Resource exhaustion (memory, disk, etc.)
    UNKNOWN = "unknown"         # Unclassified errors


class EnvironmentType(Enum):
    """Supported execution environments for self-healing."""
    PYTHON = "python"
    TERRAFORM = "terraform"
    ANSIBLE = "ansible"
    BASH = "bash"


class FixStrategy(Enum):
    """Strategies for applying fixes."""
    IN_PLACE = "in_place"           # Modify the original file
    COPY_AND_REPLACE = "copy_replace"  # Work on copy, then replace
    RUNTIME_PATCH = "runtime_patch"  # Patch at runtime without file changes
    EXTERNAL_COMMAND = "external_cmd"  # Execute external command to fix


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3           # Maximum number of fix attempts per error
    backoff_multiplier: float = 2.0  # Exponential backoff multiplier
    initial_delay_seconds: float = 1.0  # Initial delay between retries
    max_delay_seconds: float = 60.0  # Maximum delay between retries


@dataclass
class LoggingConfig:
    """Configuration for logging and audit trail."""
    log_directory: str = "./self_healing_logs"
    changelog_file: str = "healing_changelog.json"
    verbose: bool = True            # Detailed logging
    log_to_console: bool = True     # Output logs to console
    log_to_file: bool = True        # Write logs to file
    include_stack_traces: bool = True  # Include full stack traces in logs
    max_log_size_mb: int = 100      # Maximum log file size before rotation
    retention_days: int = 30        # How long to keep old logs


@dataclass
class SafetyConfig:
    """Safety settings to prevent unintended damage."""
    dry_run: bool = False           # Suggest fixes without applying
    require_approval: bool = False  # Require human approval before applying
    backup_before_fix: bool = True  # Create backup before modifying files
    sandbox_execution: bool = False  # Execute fixes in sandbox first
    protected_paths: List[str] = field(default_factory=lambda: [
        "/etc", "/usr", "/bin", "/sbin", "/var", "/root"
    ])
    max_file_size_kb: int = 10240   # Maximum file size to modify (10MB)
    allowed_external_commands: List[str] = field(default_factory=lambda: [
        "pip", "npm", "terraform", "ansible", "apt-get", "yum"
    ])


@dataclass
class ValidationConfig:
    """Configuration for fix validation."""
    run_tests_after_fix: bool = True  # Run tests after applying fix
    syntax_check_after_fix: bool = True  # Run syntax/lint check after fix
    rollback_on_failure: bool = True  # Rollback fix if validation fails
    test_timeout_seconds: int = 300  # Timeout for validation tests
    test_commands: Dict[str, str] = field(default_factory=lambda: {
        "python": "python -m py_compile {file}",
        "terraform": "terraform validate",
        "ansible": "ansible-playbook --syntax-check {file}",
        "bash": "bash -n {file}"
    })


@dataclass
class SelfHealingConfig:
    """
    Main configuration class for the Self-Healing Code System.

    This class aggregates all configuration sections and provides
    methods to load/save configuration from various sources.

    Attributes:
        enabled: Master switch to enable/disable self-healing
        environments: List of environments to monitor
        retry: Retry behavior configuration
        logging: Logging and audit configuration
        safety: Safety settings configuration
        validation: Fix validation configuration
    """
    enabled: bool = True
    environments: List[EnvironmentType] = field(
        default_factory=lambda: [
            EnvironmentType.PYTHON,
            EnvironmentType.TERRAFORM,
            EnvironmentType.ANSIBLE,
            EnvironmentType.BASH
        ]
    )
    error_types: List[ErrorType] = field(
        default_factory=lambda: [
            ErrorType.SYNTAX,
            ErrorType.LOGIC,
            ErrorType.DEPENDENCY,
            ErrorType.RUNTIME,
            ErrorType.CONFIGURATION,
            ErrorType.NETWORK,
            ErrorType.PERMISSION,
            ErrorType.RESOURCE
        ]
    )
    retry: RetryConfig = field(default_factory=RetryConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)

    # Custom fix patterns (regex pattern -> fix template)
    custom_fix_patterns: Dict[str, str] = field(default_factory=dict)

    # Environment-specific settings
    python_settings: Dict[str, Any] = field(default_factory=lambda: {
        "use_virtualenv": True,
        "pip_timeout": 60,
        "lint_command": "flake8"
    })
    terraform_settings: Dict[str, Any] = field(default_factory=lambda: {
        "auto_init": True,
        "plan_before_apply": True
    })
    ansible_settings: Dict[str, Any] = field(default_factory=lambda: {
        "check_mode_first": True,
        "diff_mode": True
    })
    bash_settings: Dict[str, Any] = field(default_factory=lambda: {
        "shell": "/bin/bash",
        "strict_mode": True  # set -euo pipefail
    })

    @classmethod
    def from_file(cls, config_path: str) -> "SelfHealingConfig":
        """
        Load configuration from a JSON file.

        Args:
            config_path: Path to the configuration file

        Returns:
            SelfHealingConfig instance with loaded settings
        """
        path = Path(config_path)
        if not path.exists():
            # Return default config if file doesn't exist
            return cls()

        with open(path, 'r') as f:
            data = json.load(f)

        return cls._from_dict(data)

    @classmethod
    def from_env(cls) -> "SelfHealingConfig":
        """
        Load configuration from environment variables.

        Environment variables should be prefixed with SELF_HEAL_.
        For example: SELF_HEAL_DRY_RUN=true

        Returns:
            SelfHealingConfig instance with settings from environment
        """
        config = cls()

        # Check for environment variable overrides
        if os.getenv("SELF_HEAL_ENABLED"):
            config.enabled = os.getenv("SELF_HEAL_ENABLED", "true").lower() == "true"

        if os.getenv("SELF_HEAL_DRY_RUN"):
            config.safety.dry_run = os.getenv("SELF_HEAL_DRY_RUN", "false").lower() == "true"

        if os.getenv("SELF_HEAL_MAX_ATTEMPTS"):
            config.retry.max_attempts = int(os.getenv("SELF_HEAL_MAX_ATTEMPTS", "3"))

        if os.getenv("SELF_HEAL_LOG_DIR"):
            config.logging.log_directory = os.getenv("SELF_HEAL_LOG_DIR")

        if os.getenv("SELF_HEAL_VERBOSE"):
            config.logging.verbose = os.getenv("SELF_HEAL_VERBOSE", "true").lower() == "true"

        if os.getenv("SELF_HEAL_BACKUP"):
            config.safety.backup_before_fix = os.getenv("SELF_HEAL_BACKUP", "true").lower() == "true"

        return config

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "SelfHealingConfig":
        """Convert a dictionary to SelfHealingConfig."""
        config = cls()

        if "enabled" in data:
            config.enabled = data["enabled"]

        if "environments" in data:
            config.environments = [
                EnvironmentType(env) for env in data["environments"]
            ]

        if "error_types" in data:
            config.error_types = [
                ErrorType(et) for et in data["error_types"]
            ]

        if "retry" in data:
            config.retry = RetryConfig(**data["retry"])

        if "logging" in data:
            config.logging = LoggingConfig(**data["logging"])

        if "safety" in data:
            config.safety = SafetyConfig(**data["safety"])

        if "validation" in data:
            config.validation = ValidationConfig(**data["validation"])

        if "custom_fix_patterns" in data:
            config.custom_fix_patterns = data["custom_fix_patterns"]

        return config

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to a dictionary."""
        return {
            "enabled": self.enabled,
            "environments": [env.value for env in self.environments],
            "error_types": [et.value for et in self.error_types],
            "retry": {
                "max_attempts": self.retry.max_attempts,
                "backoff_multiplier": self.retry.backoff_multiplier,
                "initial_delay_seconds": self.retry.initial_delay_seconds,
                "max_delay_seconds": self.retry.max_delay_seconds
            },
            "logging": {
                "log_directory": self.logging.log_directory,
                "changelog_file": self.logging.changelog_file,
                "verbose": self.logging.verbose,
                "log_to_console": self.logging.log_to_console,
                "log_to_file": self.logging.log_to_file,
                "include_stack_traces": self.logging.include_stack_traces
            },
            "safety": {
                "dry_run": self.safety.dry_run,
                "require_approval": self.safety.require_approval,
                "backup_before_fix": self.safety.backup_before_fix,
                "sandbox_execution": self.safety.sandbox_execution,
                "protected_paths": self.safety.protected_paths
            },
            "validation": {
                "run_tests_after_fix": self.validation.run_tests_after_fix,
                "syntax_check_after_fix": self.validation.syntax_check_after_fix,
                "rollback_on_failure": self.validation.rollback_on_failure,
                "test_timeout_seconds": self.validation.test_timeout_seconds
            },
            "custom_fix_patterns": self.custom_fix_patterns
        }

    def save_to_file(self, config_path: str) -> None:
        """
        Save configuration to a JSON file.

        Args:
            config_path: Path where to save the configuration
        """
        path = Path(config_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

    def is_path_protected(self, file_path: str) -> bool:
        """
        Check if a file path is in a protected location.

        Args:
            file_path: Path to check

        Returns:
            True if the path is protected and should not be modified
        """
        abs_path = os.path.abspath(file_path)
        for protected in self.safety.protected_paths:
            if abs_path.startswith(protected):
                return True
        return False

    def is_command_allowed(self, command: str) -> bool:
        """
        Check if an external command is allowed to be executed.

        Args:
            command: Command to check (first word is the command name)

        Returns:
            True if the command is in the allowed list
        """
        cmd_name = command.split()[0] if command else ""
        return cmd_name in self.safety.allowed_external_commands


# Singleton instance for global configuration
_global_config: Optional[SelfHealingConfig] = None


def get_config() -> SelfHealingConfig:
    """
    Get the global configuration instance.

    Returns:
        The global SelfHealingConfig instance
    """
    global _global_config
    if _global_config is None:
        _global_config = SelfHealingConfig.from_env()
    return _global_config


def set_config(config: SelfHealingConfig) -> None:
    """
    Set the global configuration instance.

    Args:
        config: The configuration to use globally
    """
    global _global_config
    _global_config = config
