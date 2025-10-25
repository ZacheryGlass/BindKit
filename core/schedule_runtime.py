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
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum
from PyQt6.QtCore import QTimer, QObject, pyqtSignal

logger = logging.getLogger('Core.ScheduleRuntime')

# Constants for interval validation
# QTimer uses 32-bit signed integer for milliseconds
# Maximum safe value: 2^31-1 = 2,147,483,647 ms ≈ 24.8 days
MAX_TIMER_INTERVAL_SECONDS = 2147483  # ~24.8 days


class ScheduleState(Enum):
    """Schedule states"""
    STOPPED = "stopped"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    ERROR = "error"


@dataclass
class ScheduleHandle:
    """Tracks a scheduled script execution"""
    script_name: str
    script_path: Path
    interval_seconds: int
    timer: QTimer
    last_run: Optional[float] = None
    next_run: Optional[float] = None
    is_executing: bool = False
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

        logger.info("ScheduleRuntime initialized")

    def start_schedule(
        self,
        script_name: str,
        script_path: Path,
        interval_seconds: int,
        execution_callback: Callable,
        settings_manager=None
    ) -> ScheduleHandle:
        """
        Start a scheduled execution for a script.

        Args:
            script_name: Name of the script (used for tracking)
            script_path: Path to the script file
            interval_seconds: Interval between executions in seconds
            execution_callback: Function to call when schedule fires
            settings_manager: SettingsManager for updating timestamps

        Returns:
            ScheduleHandle for the scheduled script

        Raises:
            RuntimeError: If schedule already exists for this script
        """
        if script_name in self._active_schedules:
            raise RuntimeError(f"Schedule for '{script_name}' is already active")

        # Validate interval to prevent timer overflow
        if interval_seconds > MAX_TIMER_INTERVAL_SECONDS:
            raise ValueError(
                f"Interval {interval_seconds}s exceeds maximum of {MAX_TIMER_INTERVAL_SECONDS}s (~24.8 days)"
            )

        logger.info(f"Starting schedule for '{script_name}' (interval: {interval_seconds}s)")

        # Create timer
        timer = QTimer()
        timer.setSingleShot(False)  # Repeating timer

        # Calculate next run time
        next_run = time.time() + interval_seconds

        # Create schedule handle
        handle = ScheduleHandle(
            script_name=script_name,
            script_path=script_path,
            interval_seconds=interval_seconds,
            timer=timer,
            next_run=next_run,
            execution_callback=execution_callback,
            state=ScheduleState.SCHEDULED
        )

        self._active_schedules[script_name] = handle

        # Connect timer timeout to execution handler
        # Use default argument to capture current values and avoid closure issues
        timer.timeout.connect(
            lambda name=script_name, mgr=settings_manager: self._execute_scheduled_task(name, mgr)
        )

        # Start timer
        timer.start(interval_seconds * 1000)  # QTimer uses milliseconds

        logger.info(f"Schedule for '{script_name}' started (next run in {interval_seconds}s)")
        self.schedule_started.emit(script_name)

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
        Update the interval for a scheduled script.

        Args:
            script_name: Name of the script
            new_interval_seconds: New interval in seconds

        Returns:
            True if successful, False if schedule not found
        """
        if script_name not in self._active_schedules:
            logger.warning(f"Schedule for '{script_name}' not found")
            return False

        # Validate interval to prevent timer overflow
        if new_interval_seconds > MAX_TIMER_INTERVAL_SECONDS:
            raise ValueError(
                f"Interval {new_interval_seconds}s exceeds maximum of {MAX_TIMER_INTERVAL_SECONDS}s (~24.8 days)"
            )

        handle = self._active_schedules[script_name]
        old_interval = handle.interval_seconds
        handle.interval_seconds = new_interval_seconds

        # Restart timer with new interval
        handle.timer.stop()
        handle.timer.start(new_interval_seconds * 1000)

        # Recalculate next run
        handle.next_run = time.time() + new_interval_seconds

        logger.info(f"Updated interval for '{script_name}': {old_interval}s -> {new_interval_seconds}s")

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

        # Check for overlap: if already executing, skip this run
        if handle.is_executing:
            logger.debug(f"Skipping execution of '{script_name}' (previous execution still running)")
            self.schedule_execution_blocked.emit(script_name)
            return

        # Mark as executing
        handle.is_executing = True
        handle.state = ScheduleState.RUNNING
        current_time = time.time()

        logger.info(f"Executing scheduled task: '{script_name}'")

        try:
            # Update timestamps
            handle.last_run = current_time
            handle.next_run = current_time + handle.interval_seconds

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

        return {
            'script_name': handle.script_name,
            'interval_seconds': handle.interval_seconds,
            'last_run': handle.last_run,
            'next_run': handle.next_run,
            'is_executing': handle.is_executing,
            'state': handle.state.value
        }
