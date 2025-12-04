"""
Error Analyzer Module for Self-Healing Code System
===================================================

This module provides error analysis capabilities to determine root causes
and suggest appropriate fixes. It examines error context, patterns, and
historical data to make intelligent recommendations.

Analysis Process:
-----------------
1. Parse the error message and type
2. Examine the source code context
3. Check for known patterns
4. Determine root cause
5. Generate fix suggestions ranked by confidence

Key Features:
-------------
- Pattern-based error recognition
- Source code analysis for context
- Historical fix success tracking
- Confidence scoring for suggestions
"""

import re
import ast
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
from enum import Enum

from .config import ErrorType, EnvironmentType, get_config
from .detector import DetectedError


class FixConfidence(Enum):
    """Confidence levels for fix suggestions."""
    HIGH = "high"        # Very likely to work
    MEDIUM = "medium"    # Should work in most cases
    LOW = "low"          # May or may not work
    EXPERIMENTAL = "experimental"  # Try with caution


@dataclass
class FixSuggestion:
    """
    A suggested fix for a detected error.

    Attributes:
        description: Human-readable description of the fix
        reasoning: Why this fix is suggested
        confidence: How confident we are in this fix
        fix_type: Type of fix (code_change, command, config)
        code_change: The code change to apply (if applicable)
        command: Shell command to run (if applicable)
        file_path: File to modify (if applicable)
        line_number: Line to modify (if applicable)
        priority: Priority order (lower = try first)
    """
    description: str
    reasoning: str
    confidence: FixConfidence
    fix_type: str  # "code_change", "command", "config", "retry"
    code_change: Optional[Dict[str, str]] = None  # {"old": "...", "new": "..."}
    command: Optional[str] = None
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    priority: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalysisResult:
    """
    Result of error analysis.

    Contains the root cause determination and suggested fixes.
    """
    error: DetectedError                    # Original detected error
    root_cause: str                         # Determined root cause
    root_cause_confidence: FixConfidence    # Confidence in root cause
    suggestions: List[FixSuggestion]        # Ordered list of fix suggestions
    analysis_notes: str                     # Additional analysis notes
    requires_human_review: bool             # Whether human review is recommended
    context: Dict[str, Any] = field(default_factory=dict)  # Additional context


class ErrorAnalyzer:
    """
    Main error analysis class for the self-healing system.

    This class examines detected errors, determines their root causes,
    and generates prioritized fix suggestions.

    Usage:
        analyzer = ErrorAnalyzer()
        result = analyzer.analyze(detected_error)
        for suggestion in result.suggestions:
            print(f"Try: {suggestion.description}")
    """

    # Common fix patterns mapped by error type and pattern
    FIX_PATTERNS: Dict[Tuple[ErrorType, str], Dict[str, Any]] = {
        # Python syntax errors
        (ErrorType.SYNTAX, r"expected ':'"): {
            "description": "Add missing colon",
            "reasoning": "Python requires colons after control statements",
            "fix_type": "code_change",
            "confidence": FixConfidence.HIGH,
        },
        (ErrorType.SYNTAX, r"unexpected indent"): {
            "description": "Fix indentation",
            "reasoning": "Python is sensitive to indentation",
            "fix_type": "code_change",
            "confidence": FixConfidence.MEDIUM,
        },
        (ErrorType.SYNTAX, r"unexpected EOF"): {
            "description": "Add missing closing bracket/parenthesis",
            "reasoning": "Code has unclosed brackets or parentheses",
            "fix_type": "code_change",
            "confidence": FixConfidence.MEDIUM,
        },

        # Python import errors
        (ErrorType.DEPENDENCY, r"No module named '([^']+)'"): {
            "description": "Install missing package: {module}",
            "reasoning": "The required package is not installed",
            "fix_type": "command",
            "command_template": "pip install {module}",
            "confidence": FixConfidence.HIGH,
        },

        # Python type errors
        (ErrorType.LOGIC, r"'NoneType' object"): {
            "description": "Add null check before operation",
            "reasoning": "Variable is None when it shouldn't be",
            "fix_type": "code_change",
            "confidence": FixConfidence.MEDIUM,
        },
        (ErrorType.LOGIC, r"unsupported operand type"): {
            "description": "Add type conversion or check",
            "reasoning": "Incompatible types in operation",
            "fix_type": "code_change",
            "confidence": FixConfidence.MEDIUM,
        },

        # Network errors
        (ErrorType.NETWORK, r"Connection refused"): {
            "description": "Add retry logic with backoff",
            "reasoning": "Service may be temporarily unavailable",
            "fix_type": "code_change",
            "confidence": FixConfidence.MEDIUM,
        },
        (ErrorType.NETWORK, r"timed out"): {
            "description": "Increase timeout or add retry",
            "reasoning": "Operation took too long, may need more time",
            "fix_type": "code_change",
            "confidence": FixConfidence.MEDIUM,
        },

        # Permission errors
        (ErrorType.PERMISSION, r"Permission denied"): {
            "description": "Check file permissions or run with elevated privileges",
            "reasoning": "Insufficient permissions to access resource",
            "fix_type": "command",
            "confidence": FixConfidence.LOW,
        },

        # Resource errors
        (ErrorType.RESOURCE, r"No space left"): {
            "description": "Free up disk space",
            "reasoning": "Disk is full",
            "fix_type": "command",
            "command_template": "df -h && echo 'Clean up disk space'",
            "confidence": FixConfidence.LOW,
        },

        # Terraform errors
        (ErrorType.DEPENDENCY, r"provider (.+) not found"): {
            "description": "Run terraform init to install provider",
            "reasoning": "Terraform provider needs to be installed",
            "fix_type": "command",
            "command_template": "terraform init",
            "confidence": FixConfidence.HIGH,
        },

        # Ansible errors
        (ErrorType.DEPENDENCY, r"role '([^']+)' was not found"): {
            "description": "Install missing Ansible role",
            "reasoning": "Required Ansible role is not installed",
            "fix_type": "command",
            "command_template": "ansible-galaxy install {role}",
            "confidence": FixConfidence.HIGH,
        },

        # Bash errors
        (ErrorType.DEPENDENCY, r"command not found: (.+)"): {
            "description": "Install missing command: {command}",
            "reasoning": "Required command is not installed",
            "fix_type": "command",
            "confidence": FixConfidence.MEDIUM,
        },
    }

    def __init__(self):
        """Initialize the error analyzer."""
        self.config = get_config()

        # Compile patterns for efficiency
        self._compiled_patterns: Dict[
            Tuple[ErrorType, re.Pattern], Dict[str, Any]
        ] = {}
        for (error_type, pattern), fix_info in self.FIX_PATTERNS.items():
            compiled = re.compile(pattern, re.IGNORECASE)
            self._compiled_patterns[(error_type, compiled)] = fix_info

    def analyze(self, error: DetectedError) -> AnalysisResult:
        """
        Analyze a detected error and generate fix suggestions.

        Args:
            error: The DetectedError to analyze

        Returns:
            AnalysisResult with root cause and suggestions
        """
        suggestions: List[FixSuggestion] = []
        root_cause = "Unknown"
        root_cause_confidence = FixConfidence.LOW
        analysis_notes = ""
        requires_human_review = False

        # Step 1: Pattern matching for known errors
        pattern_suggestions = self._analyze_patterns(error)
        suggestions.extend(pattern_suggestions)

        # Step 2: Environment-specific analysis
        if error.environment == EnvironmentType.PYTHON:
            env_result = self._analyze_python_error(error)
            suggestions.extend(env_result["suggestions"])
            if env_result.get("root_cause"):
                root_cause = env_result["root_cause"]
                root_cause_confidence = env_result.get(
                    "confidence", FixConfidence.MEDIUM
                )
        elif error.environment == EnvironmentType.TERRAFORM:
            env_result = self._analyze_terraform_error(error)
            suggestions.extend(env_result["suggestions"])
            if env_result.get("root_cause"):
                root_cause = env_result["root_cause"]
        elif error.environment == EnvironmentType.ANSIBLE:
            env_result = self._analyze_ansible_error(error)
            suggestions.extend(env_result["suggestions"])
            if env_result.get("root_cause"):
                root_cause = env_result["root_cause"]
        elif error.environment == EnvironmentType.BASH:
            env_result = self._analyze_bash_error(error)
            suggestions.extend(env_result["suggestions"])
            if env_result.get("root_cause"):
                root_cause = env_result["root_cause"]

        # Step 3: Source code analysis (if available)
        if error.source_code and error.environment == EnvironmentType.PYTHON:
            code_suggestions = self._analyze_source_code(error)
            suggestions.extend(code_suggestions)

        # Step 4: Determine if human review is needed
        if not suggestions:
            requires_human_review = True
            analysis_notes = (
                "No automatic fix could be determined. "
                "Manual investigation required."
            )
        elif all(s.confidence in [FixConfidence.LOW, FixConfidence.EXPERIMENTAL]
                 for s in suggestions):
            requires_human_review = True
            analysis_notes = (
                "Only low-confidence fixes available. "
                "Human review recommended before applying."
            )

        # Step 5: Sort suggestions by priority and confidence
        suggestions.sort(
            key=lambda s: (s.priority, self._confidence_order(s.confidence))
        )

        # If root cause still unknown, try to infer from error type
        if root_cause == "Unknown":
            root_cause = self._infer_root_cause(error)

        return AnalysisResult(
            error=error,
            root_cause=root_cause,
            root_cause_confidence=root_cause_confidence,
            suggestions=suggestions,
            analysis_notes=analysis_notes,
            requires_human_review=requires_human_review,
        )

    def _confidence_order(self, confidence: FixConfidence) -> int:
        """Convert confidence to numeric order for sorting."""
        order = {
            FixConfidence.HIGH: 0,
            FixConfidence.MEDIUM: 1,
            FixConfidence.LOW: 2,
            FixConfidence.EXPERIMENTAL: 3,
        }
        return order.get(confidence, 4)

    def _analyze_patterns(self, error: DetectedError) -> List[FixSuggestion]:
        """Analyze error against known patterns."""
        suggestions = []

        for (error_type, pattern), fix_info in self._compiled_patterns.items():
            if error.error_type != error_type:
                continue

            match = pattern.search(error.message)
            if match:
                # Extract captured groups for template substitution
                groups = match.groups()
                group_dict = match.groupdict() if match.lastgroup else {}

                # Build description with captured values
                description = fix_info["description"]
                if groups and "{" in description:
                    # Try to substitute captured groups
                    try:
                        if group_dict:
                            description = description.format(**group_dict)
                        elif len(groups) == 1:
                            # Common case: single capture group
                            key = description[description.find("{")+1:description.find("}")]
                            description = description.format(**{key: groups[0]})
                    except (KeyError, IndexError):
                        pass

                # Build command if applicable
                command = None
                if "command_template" in fix_info:
                    command = fix_info["command_template"]
                    if groups:
                        try:
                            if group_dict:
                                command = command.format(**group_dict)
                            elif len(groups) == 1:
                                key = command[command.find("{")+1:command.find("}")]
                                command = command.format(**{key: groups[0]})
                        except (KeyError, IndexError):
                            pass

                suggestion = FixSuggestion(
                    description=description,
                    reasoning=fix_info["reasoning"],
                    confidence=fix_info["confidence"],
                    fix_type=fix_info["fix_type"],
                    command=command,
                    file_path=error.file_path,
                    line_number=error.line_number,
                )
                suggestions.append(suggestion)

        return suggestions

    def _analyze_python_error(self, error: DetectedError) -> Dict[str, Any]:
        """Perform Python-specific error analysis."""
        suggestions = []
        root_cause = None
        confidence = FixConfidence.MEDIUM

        exception_type = error.exception_type or ""
        message = error.message

        # SyntaxError analysis
        if exception_type == "SyntaxError":
            root_cause = f"Syntax error: {message}"
            confidence = FixConfidence.HIGH

            # Missing colon
            if "expected ':'" in message or "invalid syntax" in message:
                if error.source_code:
                    suggestions.append(self._suggest_colon_fix(error))

            # Unclosed brackets
            if "unexpected EOF" in message or "was never closed" in message:
                suggestions.append(FixSuggestion(
                    description="Close unclosed bracket/parenthesis",
                    reasoning="The code has unclosed brackets, parentheses, or braces",
                    confidence=FixConfidence.MEDIUM,
                    fix_type="code_change",
                    file_path=error.file_path,
                    line_number=error.line_number,
                ))

        # IndentationError analysis
        elif exception_type == "IndentationError":
            root_cause = f"Indentation error: {message}"
            confidence = FixConfidence.HIGH
            suggestions.append(FixSuggestion(
                description="Fix code indentation",
                reasoning="Python requires consistent indentation (4 spaces recommended)",
                confidence=FixConfidence.MEDIUM,
                fix_type="code_change",
                file_path=error.file_path,
                line_number=error.line_number,
            ))

        # ImportError/ModuleNotFoundError analysis
        elif exception_type in ["ImportError", "ModuleNotFoundError"]:
            # Extract module name
            match = re.search(r"No module named '([^']+)'", message)
            if match:
                module = match.group(1)
                root_cause = f"Missing Python package: {module}"
                confidence = FixConfidence.HIGH

                # Map common module names to package names
                package_map = {
                    "PIL": "Pillow",
                    "cv2": "opencv-python",
                    "sklearn": "scikit-learn",
                    "yaml": "PyYAML",
                }
                package = package_map.get(module, module)

                suggestions.append(FixSuggestion(
                    description=f"Install missing package: {package}",
                    reasoning=f"The module '{module}' is not installed",
                    confidence=FixConfidence.HIGH,
                    fix_type="command",
                    command=f"pip install {package}",
                    priority=1,
                ))

        # TypeError analysis
        elif exception_type == "TypeError":
            root_cause = f"Type error: {message}"

            if "'NoneType'" in message:
                suggestions.append(FixSuggestion(
                    description="Add null check for None value",
                    reasoning="A variable is None when an object was expected",
                    confidence=FixConfidence.MEDIUM,
                    fix_type="code_change",
                    file_path=error.file_path,
                    line_number=error.line_number,
                ))

            if "argument" in message and "required" in message:
                suggestions.append(FixSuggestion(
                    description="Add missing function argument",
                    reasoning="A required argument is missing from the function call",
                    confidence=FixConfidence.MEDIUM,
                    fix_type="code_change",
                    file_path=error.file_path,
                    line_number=error.line_number,
                ))

        # AttributeError analysis
        elif exception_type == "AttributeError":
            root_cause = f"Attribute error: {message}"

            match = re.search(r"'(\w+)' object has no attribute '(\w+)'", message)
            if match:
                obj_type, attr = match.groups()
                suggestions.append(FixSuggestion(
                    description=f"Check attribute '{attr}' on {obj_type} object",
                    reasoning=f"The {obj_type} type doesn't have attribute '{attr}'",
                    confidence=FixConfidence.MEDIUM,
                    fix_type="code_change",
                    file_path=error.file_path,
                    line_number=error.line_number,
                ))

        # KeyError analysis
        elif exception_type == "KeyError":
            root_cause = f"Key error: {message}"
            suggestions.append(FixSuggestion(
                description="Use .get() method or check key existence",
                reasoning="Trying to access a dictionary key that doesn't exist",
                confidence=FixConfidence.MEDIUM,
                fix_type="code_change",
                file_path=error.file_path,
                line_number=error.line_number,
                metadata={"suggested_pattern": "dict.get(key, default)"},
            ))

        # IndexError analysis
        elif exception_type == "IndexError":
            root_cause = f"Index error: {message}"
            suggestions.append(FixSuggestion(
                description="Add bounds check before accessing list",
                reasoning="Trying to access a list index that's out of range",
                confidence=FixConfidence.MEDIUM,
                fix_type="code_change",
                file_path=error.file_path,
                line_number=error.line_number,
            ))

        # ValueError analysis
        elif exception_type == "ValueError":
            root_cause = f"Value error: {message}"
            suggestions.append(FixSuggestion(
                description="Add input validation",
                reasoning="A function received an argument of the right type but wrong value",
                confidence=FixConfidence.MEDIUM,
                fix_type="code_change",
                file_path=error.file_path,
                line_number=error.line_number,
            ))

        # RecursionError analysis
        elif exception_type == "RecursionError":
            root_cause = "Infinite recursion detected"
            confidence = FixConfidence.HIGH
            suggestions.append(FixSuggestion(
                description="Add base case or fix recursion logic",
                reasoning="Recursive function has no terminating condition",
                confidence=FixConfidence.MEDIUM,
                fix_type="code_change",
                file_path=error.file_path,
                line_number=error.line_number,
            ))

        # Connection/Network errors
        elif exception_type in ["ConnectionError", "TimeoutError"]:
            root_cause = f"Network error: {message}"
            suggestions.extend([
                FixSuggestion(
                    description="Add retry logic with exponential backoff",
                    reasoning="Network operations can fail temporarily",
                    confidence=FixConfidence.MEDIUM,
                    fix_type="code_change",
                    file_path=error.file_path,
                    line_number=error.line_number,
                ),
                FixSuggestion(
                    description="Increase timeout value",
                    reasoning="Operation may need more time to complete",
                    confidence=FixConfidence.MEDIUM,
                    fix_type="code_change",
                    file_path=error.file_path,
                    priority=2,
                ),
            ])

        return {
            "suggestions": suggestions,
            "root_cause": root_cause,
            "confidence": confidence,
        }

    def _analyze_terraform_error(self, error: DetectedError) -> Dict[str, Any]:
        """Perform Terraform-specific error analysis."""
        suggestions = []
        root_cause = None
        message = error.message

        # Provider initialization
        if "provider" in message.lower() and ("not found" in message.lower() or "failed to install" in message.lower()):
            root_cause = "Terraform provider not initialized"
            suggestions.append(FixSuggestion(
                description="Initialize Terraform providers",
                reasoning="Terraform needs to download and install provider plugins",
                confidence=FixConfidence.HIGH,
                fix_type="command",
                command="terraform init",
            ))

        # Invalid resource configuration
        elif "invalid" in message.lower() or "unsupported" in message.lower():
            root_cause = "Invalid Terraform configuration"
            suggestions.append(FixSuggestion(
                description="Review and fix Terraform configuration",
                reasoning="Configuration contains invalid or unsupported syntax",
                confidence=FixConfidence.MEDIUM,
                fix_type="code_change",
                file_path=error.file_path,
            ))

        # State lock issues
        elif "lock" in message.lower() or "state" in message.lower():
            root_cause = "Terraform state lock issue"
            suggestions.append(FixSuggestion(
                description="Force unlock Terraform state",
                reasoning="State file may be locked by another process",
                confidence=FixConfidence.LOW,
                fix_type="command",
                command="terraform force-unlock <LOCK_ID>",
            ))

        return {
            "suggestions": suggestions,
            "root_cause": root_cause,
        }

    def _analyze_ansible_error(self, error: DetectedError) -> Dict[str, Any]:
        """Perform Ansible-specific error analysis."""
        suggestions = []
        root_cause = None
        message = error.message

        # Role not found
        match = re.search(r"role '([^']+)' was not found", message)
        if match:
            role = match.group(1)
            root_cause = f"Missing Ansible role: {role}"
            suggestions.append(FixSuggestion(
                description=f"Install Ansible role: {role}",
                reasoning="The required Ansible role is not installed",
                confidence=FixConfidence.HIGH,
                fix_type="command",
                command=f"ansible-galaxy install {role}",
            ))

        # Module not found
        match = re.search(r"couldn't resolve module/action '([^']+)'", message)
        if match:
            module = match.group(1)
            root_cause = f"Unknown Ansible module: {module}"
            suggestions.append(FixSuggestion(
                description=f"Check module name or install collection containing: {module}",
                reasoning="The module may be misspelled or from an uninstalled collection",
                confidence=FixConfidence.MEDIUM,
                fix_type="code_change",
            ))

        # Connection/SSH errors
        if "unreachable" in message.lower() or "ssh" in message.lower():
            root_cause = "SSH connection failure"
            suggestions.extend([
                FixSuggestion(
                    description="Check SSH connectivity and credentials",
                    reasoning="Ansible cannot connect to the target host",
                    confidence=FixConfidence.LOW,
                    fix_type="command",
                    command="ssh -vvv user@host",
                ),
                FixSuggestion(
                    description="Add retry to playbook",
                    reasoning="Connection might be temporarily unavailable",
                    confidence=FixConfidence.MEDIUM,
                    fix_type="code_change",
                ),
            ])

        # Syntax errors
        if "syntax error" in message.lower():
            root_cause = "Ansible playbook syntax error"
            suggestions.append(FixSuggestion(
                description="Fix YAML syntax in playbook",
                reasoning="Playbook has invalid YAML syntax",
                confidence=FixConfidence.MEDIUM,
                fix_type="code_change",
                file_path=error.file_path,
            ))

        return {
            "suggestions": suggestions,
            "root_cause": root_cause,
        }

    def _analyze_bash_error(self, error: DetectedError) -> Dict[str, Any]:
        """Perform Bash-specific error analysis."""
        suggestions = []
        root_cause = None
        message = error.message

        # Command not found
        match = re.search(r"command not found: (\S+)", message)
        if match:
            command = match.group(1)
            root_cause = f"Missing command: {command}"
            suggestions.append(FixSuggestion(
                description=f"Install missing command: {command}",
                reasoning="The required command is not installed",
                confidence=FixConfidence.MEDIUM,
                fix_type="command",
                command=f"apt-get install {command} || yum install {command}",
            ))

        # Syntax errors
        if "syntax error" in message.lower() or "unexpected token" in message.lower():
            root_cause = "Bash script syntax error"
            suggestions.append(FixSuggestion(
                description="Fix Bash script syntax",
                reasoning="Script has invalid Bash syntax",
                confidence=FixConfidence.MEDIUM,
                fix_type="code_change",
                file_path=error.file_path,
            ))

        # File not found
        if "no such file or directory" in message.lower():
            root_cause = "File or directory not found"
            suggestions.append(FixSuggestion(
                description="Create missing file/directory or fix path",
                reasoning="Referenced file or directory doesn't exist",
                confidence=FixConfidence.MEDIUM,
                fix_type="code_change",
            ))

        # Permission denied
        if "permission denied" in message.lower():
            root_cause = "Permission denied"
            suggestions.extend([
                FixSuggestion(
                    description="Make file executable",
                    reasoning="Script may need execute permission",
                    confidence=FixConfidence.HIGH,
                    fix_type="command",
                    command=f"chmod +x {error.file_path}" if error.file_path else "chmod +x <script>",
                ),
                FixSuggestion(
                    description="Run with elevated privileges",
                    reasoning="Operation may require root access",
                    confidence=FixConfidence.LOW,
                    fix_type="command",
                    command="sudo <command>",
                    priority=2,
                ),
            ])

        return {
            "suggestions": suggestions,
            "root_cause": root_cause,
        }

    def _analyze_source_code(self, error: DetectedError) -> List[FixSuggestion]:
        """Analyze source code for potential issues."""
        suggestions = []

        if not error.source_code:
            return suggestions

        # Try to parse the source code
        try:
            tree = ast.parse(error.source_code)

            # Look for common issues in the AST
            for node in ast.walk(tree):
                # Check for bare except clauses
                if isinstance(node, ast.ExceptHandler) and node.type is None:
                    suggestions.append(FixSuggestion(
                        description="Specify exception type in except clause",
                        reasoning="Bare except clauses can hide bugs",
                        confidence=FixConfidence.LOW,
                        fix_type="code_change",
                        file_path=error.file_path,
                    ))

                # Check for mutable default arguments
                if isinstance(node, ast.FunctionDef):
                    for default in node.args.defaults:
                        if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                            suggestions.append(FixSuggestion(
                                description=f"Replace mutable default argument in function '{node.name}'",
                                reasoning="Mutable default arguments are shared between calls",
                                confidence=FixConfidence.MEDIUM,
                                fix_type="code_change",
                                file_path=error.file_path,
                                line_number=node.lineno,
                            ))

        except SyntaxError:
            # Can't parse - already a syntax error
            pass

        return suggestions

    def _suggest_colon_fix(self, error: DetectedError) -> FixSuggestion:
        """Generate a fix suggestion for missing colon."""
        return FixSuggestion(
            description="Add missing colon to control statement",
            reasoning="Python control statements (if, for, while, def, class) require a colon",
            confidence=FixConfidence.HIGH,
            fix_type="code_change",
            file_path=error.file_path,
            line_number=error.line_number,
        )

    def _infer_root_cause(self, error: DetectedError) -> str:
        """Infer root cause from error type when specific cause is unknown."""
        causes = {
            ErrorType.SYNTAX: "Code or configuration syntax is invalid",
            ErrorType.LOGIC: "Incorrect program logic or control flow",
            ErrorType.DEPENDENCY: "Missing or incompatible dependency",
            ErrorType.RUNTIME: "Runtime execution failure",
            ErrorType.CONFIGURATION: "Environment or configuration mismatch",
            ErrorType.NETWORK: "Network connectivity or timeout issue",
            ErrorType.PERMISSION: "Insufficient permissions or access denied",
            ErrorType.RESOURCE: "System resource exhaustion",
            ErrorType.UNKNOWN: "Unable to determine root cause",
        }
        return causes.get(error.error_type, "Unable to determine root cause")
