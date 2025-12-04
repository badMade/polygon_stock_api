# Self-Healing Code System

A comprehensive framework for automatically detecting and fixing errors in software. This system supports Python applications, Terraform configurations, Ansible playbooks, and Bash scripts, providing automated remediation while maintaining clarity and safety.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Supported Error Types](#supported-error-types)
- [Usage Guide](#usage-guide)
- [Configuration](#configuration)
- [Changelog & Auditing](#changelog--auditing)
- [Safety Features](#safety-features)
- [Environment-Specific Handlers](#environment-specific-handlers)
- [API Reference](#api-reference)
- [Examples](#examples)
- [Limitations](#limitations)
- [Contributing](#contributing)

## Overview

The Self-Healing Code System is designed to:

1. **Detect** errors automatically during code execution
2. **Analyze** errors to determine root causes
3. **Generate** appropriate fixes based on error patterns
4. **Apply** fixes safely with automatic backups
5. **Validate** that fixes actually resolve the issues
6. **Log** all actions for complete auditability

### Key Features

- 🔍 **Automatic Error Detection**: Catches syntax, logic, dependency, and runtime errors
- 🧠 **Intelligent Analysis**: Determines root causes and suggests fixes
- 🔧 **Safe Fix Application**: Backups, dry-run mode, and rollback capability
- ✅ **Fix Validation**: Verifies fixes work before finalizing
- 📝 **Complete Audit Trail**: JSON changelog of all healing actions
- 🔄 **Retry with Backoff**: Attempts multiple fixes with exponential backoff
- 🛡️ **Safety First**: Protected paths, allowed commands list, sandbox execution

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Self-Healing Orchestrator                     │
│   Coordinates the complete healing workflow                      │
└─────────────────────────────────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌───────────────┐      ┌───────────────┐      ┌───────────────┐
│   Detector    │      │   Analyzer    │      │    Fixer      │
│               │      │               │      │               │
│ • Catches     │      │ • Root cause  │      │ • Generates   │
│   exceptions  │      │   analysis    │      │   fixes       │
│ • Parses      │──────│ • Pattern     │──────│ • Applies     │
│   output      │      │   matching    │      │   changes     │
│ • Validates   │      │ • Confidence  │      │ • Creates     │
│   syntax      │      │   scoring     │      │   backups     │
└───────────────┘      └───────────────┘      └───────────────┘
                                                      │
                                                      ▼
                                              ┌───────────────┐
                                              │   Validator   │
                                              │               │
                                              │ • Syntax check│
                                              │ • Lint check  │
                                              │ • Run tests   │
                                              │ • Re-execute  │
                                              └───────────────┘
                                                      │
                                                      ▼
                                              ┌───────────────┐
                                              │    Logger     │
                                              │               │
                                              │ • Changelog   │
                                              │ • Statistics  │
                                              │ • Audit trail │
                                              └───────────────┘
```

### Components

| Component | Purpose |
|-----------|---------|
| **Orchestrator** | Coordinates the healing workflow, manages retries |
| **Detector** | Catches and classifies errors from various sources |
| **Analyzer** | Determines root cause and generates fix suggestions |
| **Fixer** | Applies fixes using appropriate strategies |
| **Validator** | Verifies fixes work correctly |
| **Logger** | Maintains complete audit trail |
| **Config** | Manages all configuration settings |

## Installation

### As a Package

```bash
# Clone or copy the self_healing directory to your project
cp -r self_healing /path/to/your/project/

# Install dependencies (optional, for full functionality)
pip install flake8 pytest
```

### Dependencies

The core system has no external dependencies beyond Python 3.8+. Optional dependencies:

- `flake8` - For Python linting
- `pytest` - For running tests during validation
- `PyYAML` - For Ansible YAML validation

## Quick Start

### Basic Usage

```python
from self_healing import SelfHealingOrchestrator

# Create the orchestrator
healer = SelfHealingOrchestrator()

# Option 1: Use as a decorator
@healer.protect
def my_function():
    # Errors here will be automatically detected and fixed
    result = risky_operation()
    return result

# Option 2: Use as a context manager
with healer.healing_context():
    # Code here is protected
    process_data()

# Option 3: Run a script with healing
session = healer.run_script("my_script.py")

# Option 4: Install global exception hook
healer.install_global_hook()
```

### Convenience Decorator

```python
from self_healing.orchestrator import self_heal

@self_heal
def my_function():
    # This function is protected with default settings
    pass
```

## Supported Error Types

### Python

| Error Type | Examples | Auto-Fix Capability |
|------------|----------|---------------------|
| **Syntax** | SyntaxError, IndentationError | Add missing colons, fix brackets |
| **Import** | ModuleNotFoundError, ImportError | Install missing packages |
| **Type** | TypeError, AttributeError | Add null checks, type guards |
| **Value** | ValueError, KeyError, IndexError | Add validation, use .get() |
| **Network** | ConnectionError, TimeoutError | Add retry logic with backoff |
| **Permission** | PermissionError | Suggest permission changes |
| **Resource** | MemoryError | Alert for manual intervention |

### Terraform

| Error Type | Examples | Auto-Fix Capability |
|------------|----------|---------------------|
| **Provider** | Provider not found | Run terraform init |
| **Syntax** | Invalid HCL | Run terraform fmt |
| **State** | State lock issues | Suggest force-unlock |
| **Resource** | Creation failures | Suggest configuration changes |

### Ansible

| Error Type | Examples | Auto-Fix Capability |
|------------|----------|---------------------|
| **Role** | Role not found | Install via ansible-galaxy |
| **Module** | Module not found | Install collection |
| **Syntax** | YAML errors | Suggest syntax fixes |
| **Connection** | SSH failures | Add retry/timeout config |

### Bash

| Error Type | Examples | Auto-Fix Capability |
|------------|----------|---------------------|
| **Command** | Command not found | Install package |
| **Syntax** | Syntax errors | Fix common issues |
| **Permission** | Permission denied | chmod +x |

## Usage Guide

### Creating an Orchestrator

```python
from self_healing import SelfHealingOrchestrator, SelfHealingConfig

# With default configuration
healer = SelfHealingOrchestrator()

# With custom configuration
config = SelfHealingConfig()
config.safety.dry_run = True  # Preview mode
config.retry.max_attempts = 5
config.logging.log_directory = "/var/log/self_healing"

healer = SelfHealingOrchestrator(config=config)
```

### Protecting Functions

```python
@healer.protect
def process_data(data):
    """This function's errors will be caught and healed."""
    result = parse_json(data)
    return transform(result)

# Errors are caught, analyzed, and fixed automatically
# If fixed, the function is re-executed
result = process_data(input_data)
```

### Context Manager

```python
with healer.healing_context(file_path="current_script.py"):
    # Multiple operations protected
    data = load_data()
    processed = transform(data)
    save_results(processed)
```

### Infrastructure as Code

```python
from self_healing.environments import TerraformEnvironment

# Terraform healing
tf = TerraformEnvironment(working_dir="/path/to/terraform")
success, output = tf.plan()

if not success:
    error = tf.parse_error(output)
    session = healer.heal(error)
```

```python
from self_healing.environments import AnsibleEnvironment

# Ansible healing
ansible = AnsibleEnvironment()
exit_code, stdout, stderr = ansible.run_playbook("site.yml")

if exit_code != 0:
    session = healer.heal_from_output(
        stderr,
        environment=EnvironmentType.ANSIBLE
    )
```

### Callbacks and Hooks

```python
# Get notified when errors are detected
def on_error(error):
    print(f"Error detected: {error.message}")

healer.on_error(on_error)

# Get notified when fixes are applied
def on_fix(fix_result):
    print(f"Fix applied: {fix_result.description}")

healer.on_fix(on_fix)

# Get notified when healing completes
def on_complete(session):
    print(f"Healing complete: {session.final_result}")

healer.on_complete(on_complete)
```

### Preview Mode (Dry Run)

```python
# Preview what fixes would be applied
from self_healing.detector import DetectedError
from self_healing.config import ErrorType, EnvironmentType

error = DetectedError(
    error_type=ErrorType.DEPENDENCY,
    environment=EnvironmentType.PYTHON,
    message="ModuleNotFoundError: No module named 'requests'"
)

previews = healer.preview_fix(error)
for preview in previews:
    print(f"Suggested: {preview['description']}")
    print(f"Reasoning: {preview['reasoning']}")
    print(f"Confidence: {preview['confidence']}")
```

## Configuration

### Configuration Options

```python
from self_healing import SelfHealingConfig

config = SelfHealingConfig()

# Master switch
config.enabled = True

# Retry behavior
config.retry.max_attempts = 3
config.retry.backoff_multiplier = 2.0
config.retry.initial_delay_seconds = 1.0
config.retry.max_delay_seconds = 60.0

# Logging
config.logging.log_directory = "./self_healing_logs"
config.logging.changelog_file = "healing_changelog.json"
config.logging.verbose = True
config.logging.log_to_console = True
config.logging.log_to_file = True

# Safety
config.safety.dry_run = False
config.safety.require_approval = False
config.safety.backup_before_fix = True
config.safety.sandbox_execution = False
config.safety.protected_paths = ["/etc", "/usr", "/bin"]
config.safety.allowed_external_commands = ["pip", "npm", "terraform"]

# Validation
config.validation.run_tests_after_fix = True
config.validation.syntax_check_after_fix = True
config.validation.rollback_on_failure = True
```

### Environment Variables

```bash
# Enable/disable self-healing
export SELF_HEAL_ENABLED=true

# Dry run mode (preview only)
export SELF_HEAL_DRY_RUN=false

# Maximum fix attempts
export SELF_HEAL_MAX_ATTEMPTS=3

# Log directory
export SELF_HEAL_LOG_DIR=./self_healing_logs

# Verbose logging
export SELF_HEAL_VERBOSE=true

# Create backups before fixing
export SELF_HEAL_BACKUP=true
```

### Configuration File

```python
# Load from file
config = SelfHealingConfig.from_file("self_healing_config.json")

# Save to file
config.save_to_file("self_healing_config.json")
```

Example configuration file:

```json
{
  "enabled": true,
  "environments": ["python", "terraform", "ansible", "bash"],
  "retry": {
    "max_attempts": 3,
    "backoff_multiplier": 2.0,
    "initial_delay_seconds": 1.0
  },
  "logging": {
    "log_directory": "./self_healing_logs",
    "verbose": true
  },
  "safety": {
    "dry_run": false,
    "backup_before_fix": true
  }
}
```

## Changelog & Auditing

### Changelog Structure

The system maintains a JSON changelog at `self_healing_logs/healing_changelog.json`:

```json
{
  "metadata": {
    "created": "2024-01-15T10:30:00.000000",
    "version": "1.0.0"
  },
  "incidents": [
    {
      "incident_id": "550e8400-e29b-41d4-a716-446655440000",
      "event_type": "error_detected",
      "timestamp": "2024-01-15T10:30:15.123456",
      "severity": "ERROR",
      "environment": "python",
      "file_path": "/path/to/script.py",
      "line_number": 42,
      "error_type": "dependency",
      "error_message": "ModuleNotFoundError: No module named 'requests'",
      "fix_description": "Install missing package: requests",
      "fix_reasoning": "The module 'requests' is not installed",
      "validation_result": "SUCCESS",
      "attempt_number": 1
    }
  ]
}
```

### Event Types

| Event | Description |
|-------|-------------|
| `error_detected` | An error was caught |
| `analysis_complete` | Root cause determined |
| `fix_generated` | Fix suggestion created |
| `fix_applied` | Fix was applied |
| `fix_validated` | Fix passed validation |
| `fix_failed` | Fix attempt failed |
| `rollback_performed` | Changes were rolled back |
| `healing_complete` | Healing session ended |
| `manual_intervention_required` | Human needed |

### Statistics

```python
stats = healer.get_statistics()
print(f"Total incidents: {stats['total_incidents']}")
print(f"Successful fixes: {stats['successful_fixes']}")
print(f"Failed fixes: {stats['failed_fixes']}")
print(f"Success rate: {stats['success_rate']:.1f}%")
print(f"Manual interventions: {stats['manual_interventions']}")
```

## Safety Features

### Automatic Backups

Before modifying any file, the system creates a backup:

```
self_healing_logs/backups/
├── script.py.20240115_103015.backup
├── main.tf.20240115_103020.backup
└── playbook.yml.20240115_103025.backup
```

### Protected Paths

Certain system paths are protected from modification:

```python
config.safety.protected_paths = [
    "/etc",
    "/usr",
    "/bin",
    "/sbin",
    "/var",
    "/root"
]
```

### Allowed Commands

Only whitelisted commands can be executed:

```python
config.safety.allowed_external_commands = [
    "pip", "npm", "terraform", "ansible", "apt-get", "yum"
]
```

### Rollback

If a fix fails validation, it's automatically rolled back:

```python
if not validation.success and config.validation.rollback_on_failure:
    fixer.rollback(fix_result)
```

### Sandbox Execution

Optional sandbox mode writes to temp files first:

```python
config.safety.sandbox_execution = True
```

## Environment-Specific Handlers

### Python Environment

```python
from self_healing.environments import PythonEnvironment

py_env = PythonEnvironment()

# Validate syntax
is_valid, error = py_env.validate_syntax(code)

# Check installed packages
packages = py_env.get_installed_packages()

# Install missing package
success, output = py_env.install_package("requests")

# Run script
exit_code, stdout, stderr = py_env.run_script("script.py")
```

### Terraform Environment

```python
from self_healing.environments import TerraformEnvironment

tf_env = TerraformEnvironment(working_dir="/path/to/terraform")

# Initialize
success, output = tf_env.init()

# Validate
valid, output = tf_env.validate()

# Plan
success, output = tf_env.plan()

# Apply
success, output = tf_env.apply(auto_approve=True)
```

### Ansible Environment

```python
from self_healing.environments import AnsibleEnvironment

ansible_env = AnsibleEnvironment()

# Syntax check
valid, output = ansible_env.syntax_check("playbook.yml")

# Install role
success, output = ansible_env.install_role("geerlingguy.docker")

# Run playbook
exit_code, stdout, stderr = ansible_env.run_playbook(
    "site.yml",
    inventory="hosts.ini",
    check_mode=True
)
```

### Bash Environment

```python
from self_healing.environments import BashEnvironment

bash_env = BashEnvironment()

# Syntax check
valid, error = bash_env.syntax_check("script.sh")

# Find missing commands
missing = bash_env.get_missing_commands("script.sh")

# Run script
exit_code, stdout, stderr = bash_env.run_script("script.sh")
```

## API Reference

### SelfHealingOrchestrator

```python
class SelfHealingOrchestrator:
    def __init__(config=None, log_directory=None): ...
    def heal(error, rerun_function=None) -> HealingSession: ...
    def protect(func) -> Callable: ...
    def healing_context(file_path=None) -> ContextManager: ...
    def run_script(script_path, globals_dict=None, locals_dict=None) -> HealingSession: ...
    def install_global_hook() -> None: ...
    def preview_fix(error) -> List[Dict]: ...
    def heal_from_output(output, environment, exit_code=1, file_path=None) -> HealingSession: ...
    def get_statistics() -> Dict: ...
    def get_changelog() -> Dict: ...
    def on_error(callback) -> None: ...
    def on_fix(callback) -> None: ...
    def on_complete(callback) -> None: ...
```

### ErrorDetector

```python
class ErrorDetector:
    def detect_from_exception(exception, file_path=None) -> DetectedError: ...
    def detect_from_output(output, environment, exit_code=None, file_path=None) -> DetectedError: ...
    def validate_python_syntax(code, file_path=None) -> DetectedError: ...
    def validate_file_syntax(file_path, environment=None) -> DetectedError: ...
    def classify_error(message, environment) -> ErrorType: ...
    def register_validator(validator) -> None: ...
    def catch_python_errors(func) -> Callable: ...
```

### ErrorAnalyzer

```python
class ErrorAnalyzer:
    def analyze(error) -> AnalysisResult: ...
```

### ErrorFixer

```python
class ErrorFixer:
    def apply_fix(suggestion, analysis, dry_run=None) -> FixResult: ...
    def rollback(fix_result) -> bool: ...
    def generate_fix_preview(suggestion, analysis) -> str: ...
```

### FixValidator

```python
class FixValidator:
    def validate(fix_result, original_error, level=STANDARD, rerun_function=None) -> ValidationResult: ...
    def quick_validate(fix_result, original_error) -> ValidationResult: ...
    def thorough_validate(fix_result, original_error, rerun_function=None) -> ValidationResult: ...
    def register_validator(validator) -> None: ...
```

## Examples

### Example 1: Auto-Fix Missing Import

```python
from self_healing import SelfHealingOrchestrator

healer = SelfHealingOrchestrator()

@healer.protect
def fetch_data():
    import requests  # This will auto-install if missing
    return requests.get("https://api.example.com/data")

# If 'requests' is not installed, the system will:
# 1. Detect the ModuleNotFoundError
# 2. Analyze and determine it's a missing package
# 3. Run 'pip install requests'
# 4. Re-execute the function
result = fetch_data()
```

### Example 2: Terraform Pipeline Integration

```python
from self_healing import SelfHealingOrchestrator
from self_healing.environments import TerraformEnvironment
from self_healing.config import EnvironmentType

healer = SelfHealingOrchestrator()
tf = TerraformEnvironment(working_dir="./infrastructure")

# Initialize (with healing)
success, output = tf.init()
if not success:
    session = healer.heal_from_output(output, EnvironmentType.TERRAFORM)
    if session.final_result == "success":
        success, output = tf.init()  # Retry

# Plan
if success:
    success, output = tf.plan()
    if not success:
        healer.heal_from_output(output, EnvironmentType.TERRAFORM)
```

### Example 3: CI/CD Integration

```python
#!/usr/bin/env python3
"""CI/CD script with self-healing."""

import sys
from self_healing import SelfHealingOrchestrator
from self_healing.config import SelfHealingConfig

# Configure for CI environment
config = SelfHealingConfig()
config.logging.log_to_console = True
config.logging.verbose = True
config.retry.max_attempts = 2

healer = SelfHealingOrchestrator(config=config)

@healer.protect
def run_tests():
    import pytest
    return pytest.main(["-v", "tests/"])

@healer.protect
def run_linting():
    import subprocess
    return subprocess.run(["flake8", "src/"])

if __name__ == "__main__":
    # Install global hook for any uncaught exceptions
    healer.install_global_hook()

    # Run with healing
    test_result = run_tests()
    lint_result = run_linting()

    # Print statistics
    stats = healer.get_statistics()
    print(f"Healing stats: {stats}")

    sys.exit(0 if test_result == 0 and lint_result.returncode == 0 else 1)
```

## Limitations

### Known Limitations

1. **Logic Bugs**: While the system can detect some logic bugs through validators, fully automatic logic bug fixing requires more context than can be inferred

2. **Complex Refactoring**: The system won't perform major code restructuring - only targeted fixes

3. **Security Vulnerabilities**: The system doesn't detect or fix security issues

4. **Performance Issues**: Performance problems are not detected

5. **External Services**: Can't fix issues with external services (can only add retry logic)

### When Manual Intervention is Required

The system will request manual intervention for:
- Errors it can't classify
- Low-confidence fixes
- After max retry attempts
- Protected path modifications
- Disallowed commands

### Best Practices

1. **Review the Changelog**: Regularly review `healing_changelog.json` to understand what fixes were applied

2. **Use Dry Run First**: Test with `dry_run=True` in new environments

3. **Set Appropriate Limits**: Configure `max_attempts` based on your tolerance

4. **Monitor Statistics**: Track success rates to identify recurring issues

5. **Integrate with CI/CD**: Let the system handle transient issues in pipelines

## Contributing

### Development Setup

```bash
cd self_healing
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest tests/ -v
```

### Code Style

```bash
flake8 self_healing/
black self_healing/
```

---

**Version**: 1.0.0
**License**: MIT
**Documentation**: See inline docstrings for detailed API documentation
