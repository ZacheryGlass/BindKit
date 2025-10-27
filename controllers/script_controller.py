"""
Script Controller - Manages script operations and coordination.

This controller handles script execution requests, manages script state,
and coordinates between script models and script-related views.
"""
import logging
from typing import Optional, Dict, Any, List
from PyQt6.QtCore import QObject, pyqtSignal

from models.script_models import ScriptCollectionModel, ScriptExecutionModel, HotkeyModel

logger = logging.getLogger('Controllers.Script')


class ScriptController(QObject):
    """
    Controller for managing script operations and state.
    
    This controller:
    - Handles script execution requests from views
    - Manages script configuration and presets
    - Coordinates hotkey assignments
    - Provides script data to views
    """
    
    # Signals for view updates
    script_list_updated = pyqtSignal(list)  # List[ScriptInfo]
    script_executed = pyqtSignal(str, dict)  # script_name, result
    script_status_updated = pyqtSignal(str, str)  # script_name, status
    hotkey_registration_failed = pyqtSignal(str, str, str)  # script_name, hotkey, error
    
    def __init__(self, script_collection: ScriptCollectionModel, 
                 script_execution: ScriptExecutionModel, 
                 hotkey_model: HotkeyModel):
        super().__init__()
        
        self._script_collection = script_collection
        self._script_execution = script_execution
        self._hotkey_model = hotkey_model
        
        # Connect model signals to controller logic
        self._setup_model_connections()
        
        logger.info("ScriptController initialized")
    
    # Script execution methods
    def execute_script(self, script_name: str, arguments: Optional[Dict[str, Any]] = None):
        """Execute a script with optional arguments"""
        logger.info(f"Script execution requested: {script_name}")
        
        script_info = self._script_collection.get_script_by_name(script_name)
        if not script_info:
            logger.error(f"Script not found: {script_name}")
            return
        
        # Handle different execution scenarios
        if arguments:
            # Execute with specific arguments
            self._script_execution.execute_script(script_name, arguments)
        elif script_info.arguments and self._has_preset_configuration(script_name):
            # Script has arguments and presets available - this should be handled by view
            # to show preset selection
            logger.warning(f"Script {script_name} has arguments but no specific arguments provided")
        else:
            # Simple execution
            self._script_execution.execute_script(script_name)
    
    def execute_script_with_preset(self, script_name: str, preset_name: str):
        """Execute a script with a specific preset"""
        logger.info(f"Script execution with preset requested: {script_name} -> {preset_name}")
        self._script_execution.execute_script_with_preset(script_name, preset_name)
    
    def execute_script_with_choice(self, script_name: str, arg_name: str, choice: str):
        """Execute a script with a specific choice for a choice-based argument"""
        logger.info(f"Script execution with choice: {script_name} -> {arg_name}={choice}")
        arguments = {arg_name: choice}
        self._script_execution.execute_script(script_name, arguments)
    
    def cancel_script_execution(self, script_name: str) -> bool:
        """Cancel a running script execution"""
        logger.info(f"Script cancellation requested: {script_name}")
        return self._script_execution.cancel_script_execution(script_name)
    
    # Script management methods
    def refresh_scripts(self):
        """Refresh the script collection"""
        logger.info("Script refresh requested")
        scripts = self._script_collection.refresh_scripts()
        self.script_list_updated.emit(scripts)
    
    def get_available_scripts(self):
        """Get currently available scripts"""
        return self._script_collection.get_available_scripts()
    
    def get_script_by_name(self, name: str):
        """Get script info by name"""
        return self._script_collection.get_script_by_name(name)
    
    def get_script_status(self, script_name: str) -> str:
        """Get current status of a script"""
        return self._script_execution.get_script_status(script_name)
    
    def is_script_disabled(self, script_name: str) -> bool:
        """Check if a script is disabled"""
        return self._script_collection.is_script_disabled(script_name)
    
    def is_external_script(self, script_name: str) -> bool:
        """Check if a script is external"""
        return self._script_collection.is_external_script(script_name)
    
    # Script configuration methods
    def enable_script(self, script_name: str):
        """Enable a disabled script"""
        logger.info(f"Script enable requested: {script_name}")
        self._script_collection.enable_script(script_name)
    
    def disable_script(self, script_name: str):
        """Disable a script"""
        logger.info(f"Script disable requested: {script_name}")
        self._script_collection.disable_script(script_name)
    
    def add_external_script(self, script_name: str, script_path: str) -> bool:
        """Add an external script"""
        logger.info(f"External script addition requested: {script_name} -> {script_path}")
        return self._script_collection.add_external_script(script_name, script_path)
    
    def remove_external_script(self, script_name: str):
        """Remove an external script"""
        logger.info(f"External script removal requested: {script_name}")
        self._script_collection.remove_external_script(script_name)
    
    # Hotkey management methods
    def get_script_hotkey(self, script_name: str) -> Optional[str]:
        """Get hotkey assigned to a script"""
        return self._hotkey_model.get_hotkey_for_script(script_name)
    
    def set_script_hotkey(self, script_name: str, hotkey: str):
        """Set hotkey for a script"""
        logger.info(f"Hotkey assignment requested: {script_name} -> {hotkey}")
        
        # Check if hotkey is available
        if not self._hotkey_model.is_hotkey_available(hotkey, script_name):
            existing_script = self._find_script_with_hotkey(hotkey)
            error_msg = f"Hotkey {hotkey} is already assigned to {existing_script}"
            self.hotkey_registration_failed.emit(script_name, hotkey, error_msg)
            return
        
        self._hotkey_model.set_hotkey_for_script(script_name, hotkey)
    
    def remove_script_hotkey(self, script_name: str):
        """Remove hotkey assignment from a script"""
        logger.info(f"Hotkey removal requested: {script_name}")
        self._hotkey_model.remove_hotkey_for_script(script_name)
    
    def get_all_hotkeys(self) -> Dict[str, str]:
        """Get all script-to-hotkey mappings"""
        return self._hotkey_model.get_all_hotkeys()
    
    def is_hotkey_available(self, hotkey: str, exclude_script: Optional[str] = None) -> bool:
        """Check if a hotkey is available"""
        return self._hotkey_model.is_hotkey_available(hotkey, exclude_script)
    
    # Hotkey execution (called by hotkey system)
    def execute_script_from_hotkey(self, script_name: str):
        """Execute a script triggered by hotkey"""
        logger.info(f"Script execution from hotkey: {script_name}")
        
        script_info = self._script_collection.get_script_by_name(script_name)
        if not script_info:
            logger.error(f"Hotkey script not found: {script_name}")
            return
        
        # For hotkey execution, use simple execution or default preset
        if script_info.arguments and self._has_preset_configuration(script_name):
            # Use first available preset for hotkey execution
            # TODO: Could be enhanced to allow hotkey-specific preset selection
            self._script_execution.execute_script(script_name)
        else:
            self._script_execution.execute_script(script_name)
    
    # Helper methods
    def _has_preset_configuration(self, script_name: str) -> bool:
        """Check if a script has preset configurations (by display name or stem)."""
        script_info = self._script_collection.get_script_by_name(script_name)
        if not script_info:
            return False
        try:
            stem = script_info.file_path.stem
            return self._script_collection._settings.has_script_presets(stem)
        except Exception:
            return False

    # Public helpers for presets (used by tray controller)
    def has_presets(self, script_name: str) -> bool:
        """Return True if the script has any saved presets."""
        return self._has_preset_configuration(script_name)

    def get_preset_names(self, script_name: str) -> List[str]:
        """Get saved preset names for a script (by display name or stem)."""
        script_info = self._script_collection.get_script_by_name(script_name)
        if not script_info:
            return []
        try:
            stem = script_info.file_path.stem
            return self._script_collection._settings.get_script_preset_names(stem)
        except Exception:
            return []

    # Schedule management methods
    def start_schedule(self, script_name: str, interval_seconds: int, arguments: Optional[Dict[str, Any]] = None) -> bool:
        """Start scheduled execution for a script.

        Args:
            script_name: Name of the script (display name or original name)
            interval_seconds: Interval between executions in seconds
            arguments: Optional script arguments

        Returns:
            True if schedule started successfully, False otherwise
        """
        logger.info(f"Schedule start requested: {script_name} (interval: {interval_seconds}s)")

        script_info = self._script_collection.get_script_by_name(script_name)
        if not script_info:
            logger.error(f"Script not found for scheduling: {script_name}")
            return False

        # Get the script executor from the script execution model
        executor = self._script_execution._script_loader.executor
        if not executor:
            logger.error("Script executor not available")
            return False

        # Start the schedule
        result = executor.start_scheduled_execution(script_info, interval_seconds, arguments)

        if result.success:
            logger.info(f"Schedule started for {script_name}")
            self.script_status_updated.emit(script_name, "Scheduled")
            return True
        else:
            logger.error(f"Failed to start schedule for {script_name}: {result.error}")
            return False

    def stop_schedule(self, script_name: str) -> bool:
        """Stop scheduled execution for a script.

        Args:
            script_name: Name of the script (file stem)

        Returns:
            True if schedule stopped successfully, False otherwise
        """
        logger.info(f"Schedule stop requested: {script_name}")

        script_info = self._script_collection.get_script_by_name(script_name)
        if not script_info:
            logger.error(f"Script not found for schedule stop: {script_name}")
            return False

        executor = self._script_execution._script_loader.executor
        if not executor:
            logger.error("Script executor not available")
            return False

        script_stem = script_info.file_path.stem
        result = executor.stop_scheduled_execution(script_stem)

        if result.success:
            logger.info(f"Schedule stopped for {script_name}")
            self.script_status_updated.emit(script_name, "Ready")
            return True
        else:
            logger.error(f"Failed to stop schedule for {script_name}: {result.error}")
            return False

    def start_cron_schedule(self, script_name: str, cron_expression: str, arguments: Optional[Dict[str, Any]] = None) -> bool:
        """Start CRON-based scheduled execution for a script.

        Args:
            script_name: Name of the script (display name or original name)
            cron_expression: CRON expression (5-field format)
            arguments: Optional script arguments

        Returns:
            True if schedule started successfully, False otherwise
        """
        logger.info(f"CRON schedule start requested: {script_name} (expression: {cron_expression})")

        script_info = self._script_collection.get_script_by_name(script_name)
        if not script_info:
            logger.error(f"Script not found for scheduling: {script_name}")
            return False

        # Get the script executor from the script execution model
        executor = self._script_execution._script_loader.executor
        if not executor:
            logger.error("Script executor not available")
            return False

        # Start the CRON schedule
        result = executor.start_cron_scheduled_execution(script_info, cron_expression, arguments)

        if result.success:
            logger.info(f"CRON schedule started for {script_name}")
            self.script_status_updated.emit(script_name, "Scheduled")
            return True
        else:
            logger.error(f"Failed to start CRON schedule for {script_name}: {result.error}")
            return False

    def is_schedule_running(self, script_name: str) -> bool:
        """Check if a script has an active schedule.

        Args:
            script_name: Name of the script (display name or original name)

        Returns:
            True if schedule is active, False otherwise
        """
        script_info = self._script_collection.get_script_by_name(script_name)
        if not script_info:
            return False

        executor = self._script_execution._script_loader.executor
        if not executor:
            return False

        script_stem = script_info.file_path.stem
        return executor.is_schedule_running(script_stem)

    def get_schedule_config(self, script_name: str) -> Optional[Dict[str, Any]]:
        """Get schedule configuration for a script.

        Args:
            script_name: Name of the script (file stem)

        Returns:
            Dictionary with schedule config, or None if not found
        """
        script_info = self._script_collection.get_script_by_name(script_name)
        if not script_info:
            return None

        script_stem = script_info.file_path.stem
        return self._script_collection._settings.get_schedule_config(script_stem)

    def set_schedule_config(self, script_name: str, config: Dict[str, Any]) -> bool:
        """Set schedule configuration for a script.

        Args:
            script_name: Name of the script (file stem)
            config: Configuration dictionary

        Returns:
            True if successful, False otherwise
        """
        script_info = self._script_collection.get_script_by_name(script_name)
        if not script_info:
            logger.error(f"Script not found for schedule config: {script_name}")
            return False

        script_stem = script_info.file_path.stem
        try:
            self._script_collection._settings.set_schedule_config(script_stem, config)
            logger.info(f"Schedule config for {script_name} updated: {config}")
            return True
        except Exception as e:
            logger.error(f"Failed to set schedule config for {script_name}: {e}")
            return False

    def set_schedule_enabled(self, script_name: str, enabled: bool) -> bool:
        """Enable or disable scheduling for a script.

        Args:
            script_name: Name of the script (file stem)
            enabled: Whether to enable scheduling

        Returns:
            True if successful, False otherwise
        """
        script_info = self._script_collection.get_script_by_name(script_name)
        if not script_info:
            logger.error(f"Script not found for schedule enable/disable: {script_name}")
            return False

        script_stem = script_info.file_path.stem
        try:
            self._script_collection._settings.set_schedule_enabled(script_stem, enabled)
            logger.info(f"Schedule for {script_name} set to enabled={enabled}")
            return True
        except Exception as e:
            logger.error(f"Failed to set schedule enabled for {script_name}: {e}")
            return False

    def get_all_scheduled_scripts(self) -> List[str]:
        """Get list of all scripts with active schedules.

        Returns:
            List of script stems with active schedules
        """
        try:
            return self._script_collection._settings.get_all_scheduled_scripts()
        except Exception as e:
            logger.error(f"Failed to get scheduled scripts: {e}")
            return []

    def _find_script_with_hotkey(self, hotkey: str) -> Optional[str]:
        """Find which script currently has the given hotkey assigned"""
        all_hotkeys = self._hotkey_model.get_all_hotkeys()
        for script_name, assigned_hotkey in all_hotkeys.items():
            if assigned_hotkey == hotkey:
                return script_name
        return None
    
    def _setup_model_connections(self):
        """Set up connections to model signals"""
        logger.debug("Setting up script controller model connections...")
        
        # Connect script collection changes
        self._script_collection.scripts_filtered.connect(self.script_list_updated.emit)
        
        # Connect script execution results
        self._script_execution.script_execution_completed.connect(self.script_executed.emit)
        
        # Connect hotkey registration failures
        self._hotkey_model.hotkey_registration_failed.connect(self.hotkey_registration_failed.emit)
        
        logger.debug("Script controller model connections setup complete")
