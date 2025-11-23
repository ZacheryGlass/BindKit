"""
Schedule Runtime - Manages time-based/scheduled script execution.

This module provides scheduling for periodic script execution using QTimer.
Features:
- Interval-based scheduling (every X minutes/hours/days)
- Overlap prevention (prevents simultaneous executions)
- Timestamp tracking (last run, next run)
- Integration with ScriptExecutor for actual execution
"""

import logging
import time
from pathlib import Path
from typing import Optional, Dict, Any, Callable, List, Tuple
from dataclasses import dataclass
from enum import Enum
from threading import Lock
from PyQt6.QtCore import QTimer, QObject, pyqtSignal
from croniter import croniter
from datetime import datetime

logger = logging.getLogger('Core.ScheduleRuntime')

# Constants for interval validation
# QTimer uses 32-bit signed integer for milliseconds
# Maximum safe value: 2^31-1 = 2,147,483,647 ms ≈ 24.8 days
MAX_TIMER_INTERVAL_SECONDS = 2147483  # ~24.8 days
MIN_INTERVAL_SECONDS = 10  # Minimum interval to prevent excessive executions


class ScheduleState(Enum):
    """Schedule states"""
    STOPPED = "stopped"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    ERROR = "error"


class ScheduleType(Enum):
    """Schedule execution types"""
    INTERVAL = "interval"
    CRON = "cron"


@dataclass
class ScheduleHandle:
    """Tracks a scheduled script execution"""
    script_name: str
    script_path: Path
    schedule_type: ScheduleType
    timer: QTimer
    interval_seconds: Optional[int] = None  # For INTERVAL type
    cron_expression: Optional[str] = None  # For CRON type
    cron_iterator: Optional[Any] = None  # croniter object to maintain state for CRON schedules
    last_run: Optional[float] = None
    next_run: Optional[float] = None
    is_executing: bool = False
    is_stopping: bool = False  # Flag to prevent race condition during stop
    state: ScheduleState = ScheduleState.SCHEDULED
    execution_callback: Optional[Callable] = None  # Called when schedule fires


class ScheduleRuntime(QObject):
    """
    Manages scheduled script execution with QTimer.

    Features:
    - Interval-based scheduling (no external dependencies)
    - Overlap prevention (prevents simultaneous executions)
    - Timestamp tracking for last/next run times
    - Qt integration for event loop coordination
    """

    # Signals
    schedule_started = pyqtSignal(str)  # script_name
    schedule_stopped = pyqtSignal(str)  # script_name
    schedule_executed = pyqtSignal(str)  # script_name
    schedule_error = pyqtSignal(str, str)  # script_name, error_message
    schedule_execution_blocked = pyqtSignal(str)  # script_name (overlap prevention)

    def __init__(self):
        """Initialize schedule runtime."""
        super().__init__()
        # Track active schedules
        self._active_schedules: Dict[str, ScheduleHandle] = {}
        # Lock for thread-safe schedule operations
        self._schedule_lock = Lock()

        logger.info("ScheduleRuntime initialized")

    @staticmethod
    def validate_cron_expression(cron_expr: str) -> Tuple[bool, Optional[str]]:
        """
        Validate a CRON expression.

        Args:
            cron_expr: The CRON expression to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            croniter(cron_expr)
            return True, None
        except Exception as e:
            return False, str(e)

    @staticmethod
    def get_cron_next_runs(cron_expr: str, count: int = 5) -> List[float]:
        """
        Get the next N run times for a CRON expression.

        Args:
            cron_expr: The CRON expression
            count: Number of future run times to return

        Returns:
            List of timestamps for the next runs
        """
        try:
            cron = croniter(cron_expr, datetime.now())
            return [cron.get_next(float) for _ in range(count)]
        except Exception as e:
            logger.error(f"Error calculating CRON next runs: {e}")
            return []

    @staticmethod
    def _calculate_cron_delay_to_next_run(cron_expr: str) -> int:
        """
        Calculate delay in seconds until the next CRON run.

        Args:
            cron_expr: The CRON expression

        Returns:
            Delay in seconds (minimum 1 second to avoid negative delays)
        """
        try:
            cron = croniter(cron_expr, datetime.now())
            next_run_timestamp = cron.get_next(float)
            delay_seconds = int(next_run_timestamp - time.time())
            return max(1, delay_seconds)  # Ensure at least 1 second delay
        except Exception as e:
            logger.error(f"Error calculating CRON delay: {e}")
            return 60  # Default to 60 seconds on error

    def start_schedule(
        self,
        script_name: str,
        script_path: Path,
        execution_callback: Callable,
        settings_manager=None,
        schedule_type: ScheduleType = ScheduleType.INTERVAL,
        interval_seconds: Optional[int] = None,
        cron_expression: Optional[str] = None
    ) -> ScheduleHandle:
        """
        Start a scheduled execution for a script.

        Args:
            script_name: Name of the script (used for tracking)
            script_path: Path to the script file
            execution_callback: Function to call when schedule fires
            settings_manager: SettingsManager for updating timestamps
            schedule_type: Type of schedule (INTERVAL or CRON)
            interval_seconds: Interval between executions in seconds (for INTERVAL type)
            cron_expression: CRON expression (for CRON type)

        Returns:
            ScheduleHandle for the scheduled script

        Raises:
            RuntimeError: If schedule already exists for this script
            ValueError: If parameters are invalid for the schedule type
        """
        # Validate based on schedule type
        if schedule_type == ScheduleType.INTERVAL:
            if interval_seconds is None:
                raise ValueError("interval_seconds is required for INTERVAL schedule type")
            if interval_seconds < MIN_INTERVAL_SECONDS:
                raise ValueError(
                    f"Interval must be at least {MIN_INTERVAL_SECONDS} seconds, got {interval_seconds}s"
                )
            if interval_seconds > MAX_TIMER_INTERVAL_SECONDS:
                raise ValueError(
                    f"Interval {interval_seconds}s exceeds maximum of {MAX_TIMER_INTERVAL_SECONDS}s (~24.8 days)"
                )
            logger.info(f"Starting INTERVAL schedule for '{script_name}' (interval: {interval_seconds}s)")
            timer_delay_ms = interval_seconds * 1000
            next_run = time.time() + interval_seconds

        elif schedule_type == ScheduleType.CRON:
            if not cron_expression:
                raise ValueError("cron_expression is required for CRON schedule type")
            # Validate CRON expression
            is_valid, error_msg = self.validate_cron_expression(cron_expression)
            if not is_valid:
                raise ValueError(f"Invalid CRON expression: {error_msg}")
            logger.info(f"Starting CRON schedule for '{script_name}' (expression: {cron_expression})")
            # Create croniter object to maintain state and prevent execution skips
            cron_iter = croniter(cron_expression, datetime.now())
            next_run_timestamp = cron_iter.get_next(float)
            delay_seconds = max(1, int(next_run_timestamp - time.time()))
            timer_delay_ms = delay_seconds * 1000
            next_run = next_run_timestamp

        else:
            raise ValueError(f"Unknown schedule type: {schedule_type}")

        # Create timer
        timer = QTimer()
        timer.setSingleShot(False)  # Repeating timer

        # Create schedule handle
        handle = ScheduleHandle(
            script_name=script_name,
            script_path=script_path,
            schedule_type=schedule_type,
            interval_seconds=interval_seconds,
            cron_expression=cron_expression,
            cron_iterator=cron_iter if schedule_type == ScheduleType.CRON else None,
            timer=timer,
            next_run=next_run,
            execution_callback=execution_callback,
            state=ScheduleState.SCHEDULED
        )

        # Atomic check and insertion to prevent race condition
        with self._schedule_lock:
            if script_name in self._active_schedules:
                raise RuntimeError(f"Schedule for '{script_name}' is already active")
            self._active_schedules[script_name] = handle

        # Connect timer timeout to execution handler
        # Use default argument to capture current values and avoid closure issues
        timer.timeout.connect(
            lambda name=script_name, mgr=settings_manager: self._execute_scheduled_task(name, mgr)
        )

        # Start timer and emit signal with cleanup on failure
        try:
            timer.start(int(timer_delay_ms))  # QTimer uses milliseconds
            logger.info(f"Schedule for '{script_name}' started ({schedule_type.value}, next run in {timer_delay_ms/1000:.0f}s)")
            self.schedule_started.emit(script_name)
        except Exception as e:
            # Clean up on failure: remove handle and disconnect signals
            logger.error(f"Failed to start schedule for '{script_name}': {e}")
            timer.stop()
            try:
                timer.timeout.disconnect()
            except (TypeError, RuntimeError):
                pass  # Signal was not connected
            # Ensure Qt properly destroys the timer to prevent resource leak
            timer.deleteLater()
            with self._schedule_lock:
                del self._active_schedules[script_name]
            raise

        return handle

    def stop_schedule(self, script_name: str) -> bool:
        """
        Stop a scheduled execution.

        Args:
            script_name: Name of the schedule to stop

        Returns:
            True if schedule was stopped, False if not found
        """
        if script_name not in self._active_schedules:
            logger.warning(f"Schedule for '{script_name}' is not running")
            return False

        handle = self._active_schedules[script_name]

        # Set stopping flag to prevent race condition with execution (protected by lock)
        with self._schedule_lock:
            handle.is_stopping = True
            handle.state = ScheduleState.STOPPED

        logger.info(f"Stopping schedule for '{script_name}'")

        # Stop timer
        handle.timer.stop()
        try:
            handle.timer.timeout.disconnect()
        except (TypeError, RuntimeError) as e:
            logger.debug(f"Timer signal already disconnected or not connected: {e}")

        # Remove from active schedules
        del self._active_schedules[script_name]

        logger.info(f"Schedule for '{script_name}' stopped")
        self.schedule_stopped.emit(script_name)

        return True

    def is_scheduled(self, script_name: str) -> bool:
        """
        Check if a script has an active schedule.

        Args:
            script_name: Name of the script

        Returns:
            True if schedule is active, False otherwise
        """
        return script_name in self._active_schedules and self._active_schedules[script_name].state != ScheduleState.STOPPED

    def get_schedule_handle(self, script_name: str) -> Optional[ScheduleHandle]:
        """Get schedule handle by script name."""
        return self._active_schedules.get(script_name)

    def get_all_schedules(self) -> Dict[str, ScheduleHandle]:
        """Get all active schedules."""
        return self._active_schedules.copy()

    def update_interval(self, script_name: str, new_interval_seconds: int) -> bool:
        """
        Update the interval for a scheduled script (INTERVAL type only).

        Args:
            script_name: Name of the script
            new_interval_seconds: New interval in seconds

        Returns:
            True if successful, False if schedule not found

        Raises:
            ValueError: If interval is outside valid range (10s to ~24.8 days)
        """
        if script_name not in self._active_schedules:
            logger.warning(f"Schedule for '{script_name}' not found")
            return False

        handle = self._active_schedules[script_name]
        if handle.schedule_type != ScheduleType.INTERVAL:
            raise ValueError(f"Schedule for '{script_name}' is not an INTERVAL schedule")

        # Validate interval bounds
        if new_interval_seconds < MIN_INTERVAL_SECONDS:
            raise ValueError(
                f"Interval must be at least {MIN_INTERVAL_SECONDS} seconds, got {new_interval_seconds}s"
            )

        if new_interval_seconds > MAX_TIMER_INTERVAL_SECONDS:
            raise ValueError(
                f"Interval {new_interval_seconds}s exceeds maximum of {MAX_TIMER_INTERVAL_SECONDS}s (~24.8 days)"
            )

        old_interval = handle.interval_seconds
        handle.interval_seconds = new_interval_seconds

        # Restart timer with new interval
        handle.timer.stop()
        handle.timer.start(new_interval_seconds * 1000)

        # Recalculate next run
        handle.next_run = time.time() + new_interval_seconds

        logger.info(f"Updated interval for '{script_name}': {old_interval}s -> {new_interval_seconds}s")

        return True

    def update_cron_expression(self, script_name: str, new_cron_expression: str) -> bool:
        """
        Update the CRON expression for a scheduled script (CRON type only).

        Args:
            script_name: Name of the script
            new_cron_expression: New CRON expression

        Returns:
            True if successful, False if schedule not found

        Raises:
            ValueError: If CRON expression is invalid
        """
        if script_name not in self._active_schedules:
            logger.warning(f"Schedule for '{script_name}' not found")
            return False

        handle = self._active_schedules[script_name]
        if handle.schedule_type != ScheduleType.CRON:
            raise ValueError(f"Schedule for '{script_name}' is not a CRON schedule")

        # Validate CRON expression
        is_valid, error_msg = self.validate_cron_expression(new_cron_expression)
        if not is_valid:
            raise ValueError(f"Invalid CRON expression: {error_msg}")

        old_cron = handle.cron_expression
        handle.cron_expression = new_cron_expression

        # Recreate croniter object with new expression
        handle.cron_iterator = croniter(new_cron_expression, datetime.now())
        next_run_timestamp = handle.cron_iterator.get_next(float)
        delay_seconds = max(1, int(next_run_timestamp - time.time()))

        # Restart timer with new delay
        handle.timer.stop()
        handle.timer.start(delay_seconds * 1000)

        # Update next run
        handle.next_run = next_run_timestamp

        logger.info(f"Updated CRON for '{script_name}': {old_cron} -> {new_cron_expression}")

        return True

    def stop_all_schedules(self) -> int:
        """
        Stop all active schedules.

        Returns:
            Number of schedules stopped
        """
        count = len(self._active_schedules)
        logger.info(f"Stopping all schedules ({count} active)")

        for script_name in list(self._active_schedules.keys()):
            try:
                self.stop_schedule(script_name)
            except Exception as e:
                logger.error(f"Error stopping schedule for '{script_name}': {e}")

        return count

    def _execute_scheduled_task(self, script_name: str, settings_manager=None):
        """
        Execute a scheduled task (called by QTimer).

        Implements overlap prevention: if previous execution still running,
        skip this execution.

        Args:
            script_name: Name of the script to execute
            settings_manager: SettingsManager for updating timestamps
        """
        if script_name not in self._active_schedules:
            logger.warning(f"Schedule for '{script_name}' not found")
            return

        handle = self._active_schedules[script_name]

        # Atomically check stopping/executing flags and set executing flag (race condition prevention)
        with self._schedule_lock:
            # Check if schedule is being stopped
            if handle.is_stopping:
                logger.debug(f"Skipping execution of '{script_name}' (schedule is stopping)")
                return

            # Check for overlap: if already executing, skip this run
            if handle.is_executing:
                logger.debug(f"Skipping execution of '{script_name}' (previous execution still running)")
                self.schedule_execution_blocked.emit(script_name)
                return

            # Mark as executing (while holding lock for atomicity)
            handle.is_executing = True
            handle.state = ScheduleState.RUNNING

        current_time = time.time()

        logger.info(f"Executing scheduled task: '{script_name}'")

        try:
            # Update timestamps
            handle.last_run = current_time

            # Calculate next run based on schedule type
            if handle.schedule_type == ScheduleType.INTERVAL:
                handle.next_run = current_time + handle.interval_seconds
            elif handle.schedule_type == ScheduleType.CRON:
                # Reuse croniter object to maintain state and prevent execution skips
                if handle.cron_iterator:
                    try:
                        next_run_timestamp = handle.cron_iterator.get_next(float)
                        # Handle edge case where croniter returns a past time (DST/NTP adjustments)
                        while next_run_timestamp <= current_time:
                            logger.warning(f"CRON next run {next_run_timestamp} is in the past, getting next")
                            next_run_timestamp = handle.cron_iterator.get_next(float)
                        handle.next_run = next_run_timestamp
                    except Exception as e:
                        logger.error(f"Error getting next CRON run: {e}, recreating iterator")
                        # Recreate iterator if it fails
                        handle.cron_iterator = croniter(handle.cron_expression, datetime.now())
                        handle.next_run = handle.cron_iterator.get_next(float)
                else:
                    # Fallback if no iterator (shouldn't happen, but defensive programming)
                    next_runs = self.get_cron_next_runs(handle.cron_expression, count=1)
                    if next_runs:
                        handle.next_run = next_runs[0]
                    else:
                        handle.next_run = current_time + 60

            # Update settings if available
            if settings_manager:
                try:
                    settings_manager.set_schedule_last_run(script_name, handle.last_run)
                    settings_manager.set_schedule_next_run(script_name, handle.next_run)
                except Exception as e:
                    logger.warning(f"Failed to update schedule timestamps in settings: {e}")

            # Call execution callback
            if handle.execution_callback:
                try:
                    handle.execution_callback(script_name)
                    self.schedule_executed.emit(script_name)
                except Exception as e:
                    logger.error(f"Error executing scheduled task '{script_name}': {e}")
                    handle.state = ScheduleState.ERROR
                    self.schedule_error.emit(script_name, str(e))
            else:
                logger.warning(f"No execution callback for schedule '{script_name}'")

        except Exception as e:
            logger.error(f"Error in schedule execution handler: {e}")
            handle.state = ScheduleState.ERROR
            self.schedule_error.emit(script_name, str(e))

        finally:
            # Mark as no longer executing
            handle.is_executing = False
            if handle.state != ScheduleState.ERROR:
                handle.state = ScheduleState.SCHEDULED

    def get_schedule_status(self, script_name: str) -> str:
        """Get human-readable status of a schedule."""
        if script_name not in self._active_schedules:
            return "Not scheduled"

        handle = self._active_schedules[script_name]
        return handle.state.value.capitalize()

    def get_schedule_info(self, script_name: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a schedule.

        Returns:
            Dictionary with schedule info, or None if not found
        """
        handle = self.get_schedule_handle(script_name)
        if not handle:
            return None

        info = {
            'script_name': handle.script_name,
            'schedule_type': handle.schedule_type.value,
            'last_run': handle.last_run,
            'next_run': handle.next_run,
            'is_executing': handle.is_executing,
            'state': handle.state.value
        }

        # Add type-specific info
        if handle.schedule_type == ScheduleType.INTERVAL:
            info['interval_seconds'] = handle.interval_seconds
        elif handle.schedule_type == ScheduleType.CRON:
            info['cron_expression'] = handle.cron_expression

        return info
