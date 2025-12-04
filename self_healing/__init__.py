"""
Self-Healing Code System
========================

A comprehensive framework for automatically detecting and fixing errors in software.
This system supports Python applications, Terraform configurations, Ansible playbooks,
and Bash scripts.

Components:
-----------
- Detector: Monitors execution and catches errors (syntax, logic, dependencies)
- Analyzer: Examines error context to determine root cause
- Fixer: Generates and applies appropriate fixes
- Validator: Verifies that fixes resolved the issues
- Logger: Maintains an audit trail of all healing actions
- Orchestrator: Coordinates the self-healing workflow

Usage:
------
    from self_healing import SelfHealingOrchestrator

    # Initialize the self-healing system
    healer = SelfHealingOrchestrator()

    # Protect a function with automatic healing
    @healer.protect
    def my_function():
        # Your code here
        pass

    # Or run code with healing enabled
    healer.run_with_healing(my_script_path)

Author: Self-Healing Code System
Version: 1.0.0
"""

from .config import SelfHealingConfig
from .logger import HealingLogger
from .detector import ErrorDetector
from .analyzer import ErrorAnalyzer
from .fixer import ErrorFixer
from .validator import FixValidator
from .orchestrator import SelfHealingOrchestrator

__version__ = "1.0.0"
__all__ = [
    "SelfHealingConfig",
    "HealingLogger",
    "ErrorDetector",
    "ErrorAnalyzer",
    "ErrorFixer",
    "FixValidator",
    "SelfHealingOrchestrator",
]
