"""
Logging Module for Self-Healing Code System
============================================

This module provides comprehensive logging and audit trail functionality
for the self-healing system. It maintains a detailed changelog of all
healing actions, including timestamps, error descriptions, fixes applied,
and reasoning for each action.

Features:
---------
- Structured JSON changelog for machine parsing
- Human-readable console output with colored indicators
- Automatic log rotation
- Unique incident IDs for tracking
- Severity levels for filtering
"""

import json
import logging
import os
import sys
import uuid
from datetime import datetime
from dataclasses import dataclass, asdict, field
from typing import Optional, List, Dict, Any
from pathlib import Path
from enum import Enum


class Severity(Enum):
    """Severity levels for healing events."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class HealingEventType(Enum):
    """Types of events logged by the healing system."""
    ERROR_DETECTED = "error_detected"
    ANALYSIS_COMPLETE = "analysis_complete"
    FIX_GENERATED = "fix_generated"
    FIX_APPLIED = "fix_applied"
    FIX_VALIDATED = "fix_validated"
    FIX_FAILED = "fix_failed"
    ROLLBACK_PERFORMED = "rollback_performed"
    RETRY_ATTEMPTED = "retry_attempted"
    HEALING_COMPLETE = "healing_complete"
    MANUAL_INTERVENTION_REQUIRED = "manual_intervention_required"


@dataclass
class HealingEvent:
    """
    Represents a single healing event in the changelog.

    This class captures all relevant information about a healing action,
    including the error that triggered it, the fix applied, and the outcome.
    """
    incident_id: str                    # Unique identifier for this incident
    event_type: str                     # Type of event (from HealingEventType)
    timestamp: str                      # ISO 8601 timestamp
    severity: str                       # Severity level
    environment: str                    # Environment type (python, terraform, etc.)
    file_path: Optional[str]            # File where error occurred
    line_number: Optional[int]          # Line number of error
    error_type: Optional[str]           # Classification of the error
    error_message: Optional[str]        # Original error message
    stack_trace: Optional[str]          # Full stack trace if available
    fix_description: Optional[str]      # Description of the fix applied
    fix_reasoning: Optional[str]        # Why this fix was chosen
    fix_diff: Optional[str]             # Diff of changes made
    validation_result: Optional[str]    # Result of fix validation
    attempt_number: int = 1             # Which attempt this is (1, 2, 3...)
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional context

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for JSON serialization."""
        return asdict(self)

    def to_log_message(self) -> str:
        """Format event as a human-readable log message."""
        parts = [
            f"[{self.timestamp}]",
            f"[{self.severity}]",
            f"[{self.event_type.upper()}]",
            f"Incident: {self.incident_id[:8]}..."
        ]

        if self.file_path:
            location = f"{self.file_path}"
            if self.line_number:
                location += f":{self.line_number}"
            parts.append(f"Location: {location}")

        if self.error_message:
            parts.append(f"Error: {self.error_message[:100]}...")

        if self.fix_description:
            parts.append(f"Fix: {self.fix_description}")

        if self.fix_reasoning:
            parts.append(f"Reason: {self.fix_reasoning}")

        if self.validation_result:
            parts.append(f"Validation: {self.validation_result}")

        return " | ".join(parts)


class HealingLogger:
    """
    Main logger class for the self-healing system.

    This class manages all logging operations, including writing to
    the changelog file, console output, and maintaining incident records.

    Usage:
        logger = HealingLogger()
        incident_id = logger.new_incident()
        logger.log_error_detected(incident_id, error_info)
        logger.log_fix_applied(incident_id, fix_info)
    """

    # Emoji indicators for different event types
    INDICATORS = {
        HealingEventType.ERROR_DETECTED: "❌",
        HealingEventType.ANALYSIS_COMPLETE: "🔍",
        HealingEventType.FIX_GENERATED: "🔧",
        HealingEventType.FIX_APPLIED: "✅",
        HealingEventType.FIX_VALIDATED: "✓",
        HealingEventType.FIX_FAILED: "⚠️",
        HealingEventType.ROLLBACK_PERFORMED: "↩️",
        HealingEventType.RETRY_ATTEMPTED: "🔄",
        HealingEventType.HEALING_COMPLETE: "🎉",
        HealingEventType.MANUAL_INTERVENTION_REQUIRED: "👤",
    }

    def __init__(
        self,
        log_directory: str = "./self_healing_logs",
        changelog_file: str = "healing_changelog.json",
        verbose: bool = True,
        log_to_console: bool = True,
        log_to_file: bool = True
    ):
        """
        Initialize the healing logger.

        Args:
            log_directory: Directory to store log files
            changelog_file: Name of the changelog JSON file
            verbose: Whether to include detailed information in logs
            log_to_console: Whether to output logs to console
            log_to_file: Whether to write logs to file
        """
        self.log_directory = Path(log_directory)
        self.changelog_file = self.log_directory / changelog_file
        self.verbose = verbose
        self.log_to_console = log_to_console
        self.log_to_file = log_to_file

        # Ensure log directory exists
        self.log_directory.mkdir(parents=True, exist_ok=True)

        # Track active incidents
        self._active_incidents: Dict[str, List[HealingEvent]] = {}

        # Initialize the changelog file if it doesn't exist
        if not self.changelog_file.exists():
            self._initialize_changelog()

        # Set up Python logging
        self._setup_python_logging()

    def _setup_python_logging(self) -> None:
        """Configure Python's logging module for console output."""
        self.python_logger = logging.getLogger("self_healing")
        self.python_logger.setLevel(logging.DEBUG if self.verbose else logging.INFO)

        # Remove existing handlers to avoid duplicates
        self.python_logger.handlers = []

        if self.log_to_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.DEBUG if self.verbose else logging.INFO)
            formatter = logging.Formatter(
                "%(asctime)s | %(levelname)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            console_handler.setFormatter(formatter)
            self.python_logger.addHandler(console_handler)

        if self.log_to_file:
            file_handler = logging.FileHandler(
                self.log_directory / "self_healing.log"
            )
            file_handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter(
                "%(asctime)s | %(levelname)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            file_handler.setFormatter(formatter)
            self.python_logger.addHandler(file_handler)

    def _initialize_changelog(self) -> None:
        """Create an empty changelog file with metadata."""
        initial_data = {
            "metadata": {
                "created": datetime.now().isoformat(),
                "version": "1.0.0",
                "description": "Self-Healing Code System Changelog"
            },
            "incidents": []
        }
        with open(self.changelog_file, 'w') as f:
            json.dump(initial_data, f, indent=2)

    def new_incident(self) -> str:
        """
        Generate a new unique incident ID.

        Returns:
            A unique incident identifier (UUID)
        """
        incident_id = str(uuid.uuid4())
        self._active_incidents[incident_id] = []
        return incident_id

    def _log_event(self, event: HealingEvent) -> None:
        """
        Log a healing event to all configured destinations.

        Args:
            event: The HealingEvent to log
        """
        # Track in active incidents
        if event.incident_id in self._active_incidents:
            self._active_incidents[event.incident_id].append(event)

        # Log to console with indicator
        if self.log_to_console:
            indicator = self.INDICATORS.get(
                HealingEventType(event.event_type),
                "📝"
            )
            log_level = getattr(logging, event.severity, logging.INFO)
            self.python_logger.log(
                log_level,
                f"{indicator} {event.to_log_message()}"
            )

        # Append to changelog file
        if self.log_to_file:
            self._append_to_changelog(event)

    def _append_to_changelog(self, event: HealingEvent) -> None:
        """Append an event to the changelog JSON file."""
        try:
            with open(self.changelog_file, 'r') as f:
                changelog = json.load(f)

            changelog["incidents"].append(event.to_dict())

            with open(self.changelog_file, 'w') as f:
                json.dump(changelog, f, indent=2)
        except Exception as e:
            self.python_logger.error(f"Failed to write to changelog: {e}")

    def log_error_detected(
        self,
        incident_id: str,
        environment: str,
        error_type: str,
        error_message: str,
        file_path: Optional[str] = None,
        line_number: Optional[int] = None,
        stack_trace: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log that an error has been detected.

        Args:
            incident_id: Unique incident identifier
            environment: Environment type (python, terraform, etc.)
            error_type: Classification of the error
            error_message: The error message
            file_path: File where error occurred
            line_number: Line number of error
            stack_trace: Full stack trace
            metadata: Additional context
        """
        event = HealingEvent(
            incident_id=incident_id,
            event_type=HealingEventType.ERROR_DETECTED.value,
            timestamp=datetime.now().isoformat(),
            severity=Severity.ERROR.value,
            environment=environment,
            file_path=file_path,
            line_number=line_number,
            error_type=error_type,
            error_message=error_message,
            stack_trace=stack_trace if self.verbose else None,
            fix_description=None,
            fix_reasoning=None,
            fix_diff=None,
            validation_result=None,
            metadata=metadata or {}
        )
        self._log_event(event)

    def log_analysis_complete(
        self,
        incident_id: str,
        environment: str,
        analysis_summary: str,
        root_cause: str,
        suggested_fixes: List[str],
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log that error analysis is complete.

        Args:
            incident_id: Unique incident identifier
            environment: Environment type
            analysis_summary: Summary of the analysis
            root_cause: Identified root cause
            suggested_fixes: List of potential fixes
            metadata: Additional context
        """
        event = HealingEvent(
            incident_id=incident_id,
            event_type=HealingEventType.ANALYSIS_COMPLETE.value,
            timestamp=datetime.now().isoformat(),
            severity=Severity.INFO.value,
            environment=environment,
            file_path=None,
            line_number=None,
            error_type=None,
            error_message=None,
            stack_trace=None,
            fix_description=analysis_summary,
            fix_reasoning=f"Root cause: {root_cause}. Suggested fixes: {', '.join(suggested_fixes)}",
            fix_diff=None,
            validation_result=None,
            metadata=metadata or {}
        )
        self._log_event(event)

    def log_fix_generated(
        self,
        incident_id: str,
        environment: str,
        fix_description: str,
        fix_reasoning: str,
        fix_diff: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log that a fix has been generated.

        Args:
            incident_id: Unique incident identifier
            environment: Environment type
            fix_description: Description of the fix
            fix_reasoning: Why this fix was chosen
            fix_diff: The diff of changes to be made
            metadata: Additional context
        """
        event = HealingEvent(
            incident_id=incident_id,
            event_type=HealingEventType.FIX_GENERATED.value,
            timestamp=datetime.now().isoformat(),
            severity=Severity.INFO.value,
            environment=environment,
            file_path=None,
            line_number=None,
            error_type=None,
            error_message=None,
            stack_trace=None,
            fix_description=fix_description,
            fix_reasoning=fix_reasoning,
            fix_diff=fix_diff,
            validation_result=None,
            metadata=metadata or {}
        )
        self._log_event(event)

    def log_fix_applied(
        self,
        incident_id: str,
        environment: str,
        file_path: str,
        fix_description: str,
        fix_reasoning: str,
        fix_diff: Optional[str] = None,
        attempt_number: int = 1,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log that a fix has been applied.

        Args:
            incident_id: Unique incident identifier
            environment: Environment type
            file_path: File that was modified
            fix_description: Description of the fix
            fix_reasoning: Why this fix was chosen
            fix_diff: The diff of changes made
            attempt_number: Which attempt this is
            metadata: Additional context
        """
        event = HealingEvent(
            incident_id=incident_id,
            event_type=HealingEventType.FIX_APPLIED.value,
            timestamp=datetime.now().isoformat(),
            severity=Severity.INFO.value,
            environment=environment,
            file_path=file_path,
            line_number=None,
            error_type=None,
            error_message=None,
            stack_trace=None,
            fix_description=fix_description,
            fix_reasoning=fix_reasoning,
            fix_diff=fix_diff,
            validation_result=None,
            attempt_number=attempt_number,
            metadata=metadata or {}
        )
        self._log_event(event)

    def log_fix_validated(
        self,
        incident_id: str,
        environment: str,
        validation_result: str,
        tests_run: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log that a fix has been validated successfully.

        Args:
            incident_id: Unique incident identifier
            environment: Environment type
            validation_result: Result of validation
            tests_run: List of tests that were run
            metadata: Additional context
        """
        event = HealingEvent(
            incident_id=incident_id,
            event_type=HealingEventType.FIX_VALIDATED.value,
            timestamp=datetime.now().isoformat(),
            severity=Severity.INFO.value,
            environment=environment,
            file_path=None,
            line_number=None,
            error_type=None,
            error_message=None,
            stack_trace=None,
            fix_description=None,
            fix_reasoning=None,
            fix_diff=None,
            validation_result=validation_result,
            metadata={"tests_run": tests_run or [], **(metadata or {})}
        )
        self._log_event(event)

    def log_fix_failed(
        self,
        incident_id: str,
        environment: str,
        failure_reason: str,
        attempt_number: int,
        will_retry: bool,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log that a fix attempt failed.

        Args:
            incident_id: Unique incident identifier
            environment: Environment type
            failure_reason: Why the fix failed
            attempt_number: Which attempt this was
            will_retry: Whether another attempt will be made
            metadata: Additional context
        """
        event = HealingEvent(
            incident_id=incident_id,
            event_type=HealingEventType.FIX_FAILED.value,
            timestamp=datetime.now().isoformat(),
            severity=Severity.WARNING.value,
            environment=environment,
            file_path=None,
            line_number=None,
            error_type=None,
            error_message=failure_reason,
            stack_trace=None,
            fix_description=None,
            fix_reasoning=f"Will {'retry' if will_retry else 'not retry'}",
            fix_diff=None,
            validation_result="FAILED",
            attempt_number=attempt_number,
            metadata=metadata or {}
        )
        self._log_event(event)

    def log_rollback(
        self,
        incident_id: str,
        environment: str,
        file_path: str,
        rollback_reason: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log that a rollback was performed.

        Args:
            incident_id: Unique incident identifier
            environment: Environment type
            file_path: File that was rolled back
            rollback_reason: Why the rollback was performed
            metadata: Additional context
        """
        event = HealingEvent(
            incident_id=incident_id,
            event_type=HealingEventType.ROLLBACK_PERFORMED.value,
            timestamp=datetime.now().isoformat(),
            severity=Severity.WARNING.value,
            environment=environment,
            file_path=file_path,
            line_number=None,
            error_type=None,
            error_message=None,
            stack_trace=None,
            fix_description=f"Rolled back changes to {file_path}",
            fix_reasoning=rollback_reason,
            fix_diff=None,
            validation_result=None,
            metadata=metadata or {}
        )
        self._log_event(event)

    def log_healing_complete(
        self,
        incident_id: str,
        environment: str,
        success: bool,
        total_attempts: int,
        summary: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log that the healing process is complete.

        Args:
            incident_id: Unique incident identifier
            environment: Environment type
            success: Whether healing was successful
            total_attempts: Total number of fix attempts
            summary: Summary of the healing process
            metadata: Additional context
        """
        event = HealingEvent(
            incident_id=incident_id,
            event_type=HealingEventType.HEALING_COMPLETE.value,
            timestamp=datetime.now().isoformat(),
            severity=Severity.INFO.value if success else Severity.ERROR.value,
            environment=environment,
            file_path=None,
            line_number=None,
            error_type=None,
            error_message=None,
            stack_trace=None,
            fix_description=summary,
            fix_reasoning=f"Completed after {total_attempts} attempt(s)",
            fix_diff=None,
            validation_result="SUCCESS" if success else "FAILED",
            metadata=metadata or {}
        )
        self._log_event(event)

        # Remove from active incidents
        if incident_id in self._active_incidents:
            del self._active_incidents[incident_id]

    def log_manual_intervention_required(
        self,
        incident_id: str,
        environment: str,
        reason: str,
        suggested_action: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log that manual intervention is required.

        Args:
            incident_id: Unique incident identifier
            environment: Environment type
            reason: Why manual intervention is needed
            suggested_action: What the human should do
            metadata: Additional context
        """
        event = HealingEvent(
            incident_id=incident_id,
            event_type=HealingEventType.MANUAL_INTERVENTION_REQUIRED.value,
            timestamp=datetime.now().isoformat(),
            severity=Severity.CRITICAL.value,
            environment=environment,
            file_path=None,
            line_number=None,
            error_type=None,
            error_message=reason,
            stack_trace=None,
            fix_description=suggested_action,
            fix_reasoning="Automatic fix not possible or not safe",
            fix_diff=None,
            validation_result=None,
            metadata=metadata or {}
        )
        self._log_event(event)

    def get_incident_history(self, incident_id: str) -> List[HealingEvent]:
        """
        Get the history of events for a specific incident.

        Args:
            incident_id: The incident identifier

        Returns:
            List of HealingEvent objects for the incident
        """
        return self._active_incidents.get(incident_id, [])

    def get_changelog(self) -> Dict[str, Any]:
        """
        Read the entire changelog.

        Returns:
            The changelog data as a dictionary
        """
        try:
            with open(self.changelog_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.python_logger.error(f"Failed to read changelog: {e}")
            return {"metadata": {}, "incidents": []}

    def get_statistics(self) -> Dict[str, Any]:
        """
        Calculate statistics from the changelog.

        Returns:
            Dictionary with statistics about healing activities
        """
        changelog = self.get_changelog()
        incidents = changelog.get("incidents", [])

        total_incidents = len([
            i for i in incidents
            if i.get("event_type") == HealingEventType.ERROR_DETECTED.value
        ])
        successful_fixes = len([
            i for i in incidents
            if i.get("event_type") == HealingEventType.HEALING_COMPLETE.value
            and i.get("validation_result") == "SUCCESS"
        ])
        failed_fixes = len([
            i for i in incidents
            if i.get("event_type") == HealingEventType.HEALING_COMPLETE.value
            and i.get("validation_result") == "FAILED"
        ])

        # Count by error type
        error_types: Dict[str, int] = {}
        for incident in incidents:
            if incident.get("event_type") == HealingEventType.ERROR_DETECTED.value:
                et = incident.get("error_type", "unknown")
                error_types[et] = error_types.get(et, 0) + 1

        return {
            "total_incidents": total_incidents,
            "successful_fixes": successful_fixes,
            "failed_fixes": failed_fixes,
            "success_rate": (
                successful_fixes / total_incidents * 100
                if total_incidents > 0 else 0
            ),
            "error_types": error_types,
            "manual_interventions": len([
                i for i in incidents
                if i.get("event_type") == HealingEventType.MANUAL_INTERVENTION_REQUIRED.value
            ])
        }

    def clear_changelog(self) -> None:
        """Clear the changelog file (for testing or reset)."""
        self._initialize_changelog()
        self._active_incidents.clear()
