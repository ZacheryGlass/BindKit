"""
Schedule Model - MVC model for schedule configuration state.

This model manages the state of scheduled script executions and emits signals
when configuration changes, allowing the UI and controllers to stay synchronized.
"""

import logging
from typing import Dict, List, Any, Optional
from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger('Models.ScheduleModel')


class ScheduleModel(QObject):
    """
    MVC Model for schedule configuration state.

    Signals:
    - schedule_enabled_changed: Emitted when a script's schedule is enabled/disabled
    - schedule_config_changed: Emitted when a script's schedule configuration changes
    - schedule_started: Emitted when a schedule is started at runtime
    - schedule_stopped: Emitted when a schedule is stopped at runtime
    - schedule_executed: Emitted when a scheduled task executes
    """

    # Signals for schedule state changes
    schedule_enabled_changed = pyqtSignal(str, bool)  # script_name, enabled
    schedule_config_changed = pyqtSignal(str, dict)  # script_name, config
    schedule_started = pyqtSignal(str)  # script_name
    schedule_stopped = pyqtSignal(str)  # script_name
    schedule_executed = pyqtSignal(str)  # script_name
    schedule_error = pyqtSignal(str, str)  # script_name, error_message
    schedule_execution_blocked = pyqtSignal(str)  # script_name (overlap prevention)

    def __init__(self, settings_manager):
        """
        Initialize the schedule model.

        Args:
            settings_manager: SettingsManager instance for persistence
        """
        super().__init__()
        self.settings_manager = settings_manager
        logger.info("ScheduleModel initialized")

    def is_script_scheduled(self, script_name: str) -> bool:
        """Check if a script has scheduling enabled."""
        return self.settings_manager.is_script_scheduled(script_name)

    def set_schedule_enabled(self, script_name: str, enabled: bool) -> None:
        """Enable or disable scheduling for a script."""
        old_value = self.is_script_scheduled(script_name)
        self.settings_manager.set_schedule_enabled(script_name, enabled)

        if old_value != enabled:
            logger.info(f"Schedule for '{script_name}' changed to {enabled}")
            self.schedule_enabled_changed.emit(script_name, enabled)

    def get_schedule_config(self, script_name: str) -> Dict[str, Any]:
        """Get complete schedule configuration for a script."""
        return self.settings_manager.get_schedule_config(script_name)

    def set_schedule_config(self, script_name: str, config: Dict[str, Any]) -> None:
        """Set schedule configuration for a script."""
        self.settings_manager.set_schedule_config(script_name, config)
        logger.info(f"Schedule config for '{script_name}' updated: {config}")
        self.schedule_config_changed.emit(script_name, config)

    def get_schedule_interval(self, script_name: str) -> int:
        """Get the interval (in seconds) for a script's schedule."""
        return self.settings_manager.get_schedule_interval(script_name)

    def set_schedule_interval(self, script_name: str, interval_seconds: int) -> None:
        """Set the interval for a script's schedule."""
        self.settings_manager.set_schedule_interval(script_name, interval_seconds)
        logger.info(f"Schedule interval for '{script_name}' set to {interval_seconds}s")

        config = self.get_schedule_config(script_name)
        self.schedule_config_changed.emit(script_name, config)

    def get_schedule_last_run(self, script_name: str) -> Optional[float]:
        """Get the last run timestamp for a scheduled script."""
        return self.settings_manager.get_schedule_last_run(script_name)

    def set_schedule_last_run(self, script_name: str, timestamp: Optional[float]) -> None:
        """Update the last run timestamp for a scheduled script."""
        self.settings_manager.set_schedule_last_run(script_name, timestamp)

    def get_schedule_next_run(self, script_name: str) -> Optional[float]:
        """Get the next run timestamp for a scheduled script."""
        return self.settings_manager.get_schedule_next_run(script_name)

    def set_schedule_next_run(self, script_name: str, timestamp: Optional[float]) -> None:
        """Update the next run timestamp for a scheduled script."""
        self.settings_manager.set_schedule_next_run(script_name, timestamp)

    def get_all_scheduled_scripts(self) -> List[str]:
        """Get list of all scripts that have scheduling enabled."""
        return self.settings_manager.get_all_scheduled_scripts()

    def remove_schedule_config(self, script_name: str) -> None:
        """Remove all schedule configuration for a script."""
        self.settings_manager.remove_schedule_config(script_name)
        logger.info(f"Removed schedule config for '{script_name}'")

    def emit_schedule_started(self, script_name: str) -> None:
        """Emit signal that a schedule has started."""
        self.schedule_started.emit(script_name)

    def emit_schedule_stopped(self, script_name: str) -> None:
        """Emit signal that a schedule has stopped."""
        self.schedule_stopped.emit(script_name)

    def emit_schedule_executed(self, script_name: str) -> None:
        """Emit signal that a scheduled task has executed."""
        self.schedule_executed.emit(script_name)

    def emit_schedule_error(self, script_name: str, error_message: str) -> None:
        """Emit signal for a schedule error."""
        self.schedule_error.emit(script_name, error_message)

    def emit_schedule_execution_blocked(self, script_name: str) -> None:
        """Emit signal that a scheduled execution was blocked (overlap prevention)."""
        self.schedule_execution_blocked.emit(script_name)

    def get_schedule_info_for_display(self, script_name: str) -> Dict[str, Any]:
        """
        Get schedule information formatted for display in UI.

        Returns:
            Dictionary with display-formatted schedule info
        """
        from datetime import datetime

        config = self.get_schedule_config(script_name)
        interval_seconds = config.get('interval_seconds', 3600)
        last_run = config.get('last_run')
        next_run = config.get('next_run')

        # Format interval for display
        if interval_seconds < 60:
            interval_display = f"{interval_seconds} seconds"
        elif interval_seconds < 3600:
            minutes = interval_seconds // 60
            interval_display = f"{minutes} minute{'s' if minutes != 1 else ''}"
        elif interval_seconds < 86400:
            hours = interval_seconds // 3600
            interval_display = f"{hours} hour{'s' if hours != 1 else ''}"
        else:
            days = interval_seconds // 86400
            interval_display = f"{days} day{'s' if days != 1 else ''}"

        # Format timestamps for display
        last_run_display = "Never" if not last_run else datetime.fromtimestamp(last_run).strftime("%Y-%m-%d %H:%M:%S")
        next_run_display = "Not scheduled" if not next_run else datetime.fromtimestamp(next_run).strftime("%Y-%m-%d %H:%M:%S")

        return {
            'enabled': config.get('enabled', False),
            'interval_seconds': interval_seconds,
            'interval_display': interval_display,
            'last_run': last_run,
            'last_run_display': last_run_display,
            'next_run': next_run,
            'next_run_display': next_run_display
        }
