"""
Settings Controller - Manages settings operations and coordination.

This controller handles all settings-related business logic,
coordinating between settings models and the settings view.
"""
import logging
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QFileDialog, QMessageBox

logger = logging.getLogger('Controllers.Settings')


class SettingsController(QObject):
    """
    Controller for managing application settings.
    
    This controller:
    - Handles all settings-related business logic
    - Coordinates between settings view and models
    - Manages settings persistence and validation
    - Handles script configuration operations
    """
    
    # Signals for view updates
    settings_loaded = pyqtSignal(dict)  # All settings data
    startup_settings_updated = pyqtSignal(dict)
    behavior_settings_updated = pyqtSignal(dict)
    execution_settings_updated = pyqtSignal(dict)
    script_list_updated = pyqtSignal(list)  # List of script configurations
    hotkey_updated = pyqtSignal(str, str)  # script_name, hotkey
    preset_updated = pyqtSignal(str, dict)  # script_name, presets
    settings_saved = pyqtSignal()
    settings_reset = pyqtSignal(str)  # category that was reset
    error_occurred = pyqtSignal(str, str)  # title, message
    
    def __init__(self, app_model, script_controller, parent=None):
        super().__init__(parent)
        
        self._app_model = app_model
        self._script_controller = script_controller
        self._script_collection = script_controller._script_collection
        self._script_execution = script_controller._script_execution
        self._hotkey_model = script_controller._hotkey_model
        self._settings_manager = self._script_collection._settings
        
        # Track current settings state
        self._current_settings = {}
        
        logger.info("SettingsController initialized")
    
    # Loading methods
    def load_all_settings(self):
        """Load all current settings from models"""
        logger.info("Loading all settings...")
        
        try:
            settings_data = {
                'startup': self._app_model.get_startup_settings(),
                'behavior': self._app_model.get_behavior_settings(),
                'execution': self._app_model.get_execution_settings(),
                'scripts': self._load_script_configurations(),
                'hotkeys': self._hotkey_model.get_all_hotkeys(),
                'presets': self._load_all_presets()
            }
            
            self._current_settings = settings_data
            self.settings_loaded.emit(settings_data)
            
            # Also emit individual category updates
            self.startup_settings_updated.emit(settings_data['startup'])
            self.behavior_settings_updated.emit(settings_data['behavior'])
            self.execution_settings_updated.emit(settings_data['execution'])
            self.script_list_updated.emit(settings_data['scripts'])
            
            logger.info("Settings loaded successfully")
            
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
            self.error_occurred.emit("Load Error", f"Failed to load settings: {str(e)}")
    
    def _load_script_configurations(self) -> List[Dict[str, Any]]:
        """Load script configurations including enable/disable state"""
        configs = []
        
        # Get all scripts (including disabled ones)
        all_scripts = self._script_collection.get_all_scripts()
        
        for script_info in all_scripts:
            # Use the file stem as the script identifier for settings/hotkeys
            stem_name = script_info.file_path.stem
            # Effective name (custom applied) for display to users
            effective_display_name = self._script_collection.get_script_display_name(script_info)
            # Original base display name from analyzer (stable identifier for model APIs)
            original_display_name = script_info.display_name

            config = {
                'name': stem_name,  # file stem identifier for settings/hotkeys
                'display_name': effective_display_name,
                'original_display_name': original_display_name,
                'is_external': self._script_collection.is_external_script(original_display_name),
                'is_disabled': self._script_collection.is_script_disabled(original_display_name),
                'hotkey': self._hotkey_model.get_hotkey_for_script(stem_name),
                # Custom names are stored against the original display name
                'custom_name': self._settings_manager.get_custom_name(original_display_name),
                'has_arguments': bool(script_info.arguments),
                'arguments': script_info.arguments if script_info.arguments else [],
                'file_path': str(script_info.file_path)
            }
            
            configs.append(config)
        
        return configs
    
    def _load_all_presets(self) -> Dict[str, Dict[str, Any]]:
        """Load all script presets keyed by display name for the view."""
        presets: Dict[str, Dict[str, Any]] = {}

        all_scripts = self._script_collection.get_all_scripts()
        for script_info in all_scripts:
            # Settings are stored under the file stem, but the view uses display names
            stem_name = script_info.file_path.stem
            display_name = script_info.display_name
            script_presets = self._settings_manager.get_script_presets(stem_name)
            if script_presets:
                presets[display_name] = script_presets

        return presets

    def _update_script_list(self):
        """Update and emit the script list - called when script collection changes."""
        scripts = self._load_script_configurations()
        self.script_list_updated.emit(scripts)

    # Startup settings methods
    def set_run_on_startup(self, enabled: bool):
        """Enable or disable run on startup"""
        logger.info(f"Setting run on startup: {enabled}")
        self._app_model.set_run_on_startup(enabled)
    
    def set_start_minimized(self, minimized: bool):
        """Set whether to start minimized"""
        logger.info(f"Setting start minimized: {minimized}")
        self._app_model.set_start_minimized(minimized)
    
    def set_show_startup_notification(self, show: bool):
        """Set whether to show startup notification"""
        logger.info(f"Setting show startup notification: {show}")
        self._app_model.set_show_startup_notification(show)
    
    # Behavior settings methods
    def set_minimize_to_tray(self, enabled: bool):
        """Set minimize to tray behavior"""
        logger.info(f"Setting minimize to tray: {enabled}")
        self._app_model.set_minimize_to_tray(enabled)
    
    def set_close_to_tray(self, enabled: bool):
        """Set close to tray behavior"""
        logger.info(f"Setting close to tray: {enabled}")
        self._app_model.set_close_to_tray(enabled)
    
    def set_single_instance(self, enabled: bool):
        """Set single instance mode"""
        logger.info(f"Setting single instance: {enabled}")
        self._app_model.set_single_instance(enabled)
    
    def set_show_script_notifications(self, enabled: bool):
        """Set script notification preference"""
        logger.info(f"Setting show script notifications: {enabled}")
        self._app_model.set_show_script_notifications(enabled)
    
    # Execution settings methods
    def set_script_timeout(self, seconds: int):
        """Set script execution timeout"""
        logger.info(f"Setting script timeout: {seconds} seconds")
        self._app_model.set_script_timeout_seconds(seconds)
    
    # Removed status refresh interval configuration (now fixed at 5s)
    
    # Script management methods
    def toggle_script(self, script_name: str, enabled: bool):
        """Enable or disable a script"""
        logger.info(f"Toggling script {script_name}: {'enabled' if enabled else 'disabled'}")
        
        try:
            if enabled:
                self._script_controller.enable_script(script_name)
            else:
                self._script_controller.disable_script(script_name)
            
            # Refresh script list
            self.script_list_updated.emit(self._load_script_configurations())
            
        except Exception as e:
            logger.error(f"Error toggling script {script_name}: {e}")
            self.error_occurred.emit("Script Error", f"Failed to toggle script: {str(e)}")
    
    def set_script_hotkey(self, script_name: str, hotkey: str):
        """Set hotkey for a script"""
        logger.info(f"Setting hotkey for {script_name}: {hotkey}")
        
        try:
            if hotkey:
                # Check if hotkey is available
                if not self._script_controller.is_hotkey_available(hotkey, script_name):
                    existing_script = self._find_script_with_hotkey(hotkey)
                    self.error_occurred.emit(
                        "Hotkey Conflict",
                        f"Hotkey {hotkey} is already assigned to {existing_script}"
                    )
                    return
                
                self._script_controller.set_script_hotkey(script_name, hotkey)
            else:
                # Remove hotkey
                self._script_controller.remove_script_hotkey(script_name)
            
            # Notify views; granular update handled by settings view
            self.hotkey_updated.emit(script_name, hotkey)
            
        except Exception as e:
            logger.error(f"Error setting hotkey for {script_name}: {e}")
            self.error_occurred.emit("Hotkey Error", f"Failed to set hotkey: {str(e)}")
    
    def set_script_custom_name(self, script_name: str, custom_name: str):
        """Set custom display name for a script.

        script_name is the file stem identifier. Custom names are stored against the
        original display name, so we map stem -> display name before saving.
        """
        logger.info(f"Setting custom name for {script_name}: {custom_name}")

        try:
            # Map the file stem to the current display name
            display_name = self._get_display_name_for_stem(script_name) or script_name

            if custom_name and custom_name.strip() and custom_name != display_name:
                self._settings_manager.set_custom_name(display_name, custom_name)
            else:
                # Remove custom name mapping (revert to original)
                self._settings_manager.remove_custom_name(display_name)

            # Refresh script list so the view reflects updated display names
            self.script_list_updated.emit(self._load_script_configurations())

        except Exception as e:
            logger.error(f"Error setting custom name for {script_name}: {e}")
            self.error_occurred.emit("Name Error", f"Failed to set custom name: {str(e)}")
    
    def add_external_script(self, file_path: str) -> bool:
        """Add an external script"""
        logger.info(f"Adding external script: {file_path}")
        
        try:
            # Validate file
            path = Path(file_path)
            if not path.exists() or not path.suffix == '.py':
                self.error_occurred.emit(
                    "Invalid File",
                    "Please select a valid Python (.py) file"
                )
                return False
            
            # Generate script name from file
            script_name = path.stem.replace('_', ' ').title()
            
            # Check for duplicates
            existing_scripts = self._script_collection.get_all_scripts()
            for script in existing_scripts:
                if script.display_name == script_name:
                    self.error_occurred.emit(
                        "Duplicate Script",
                        f"A script named '{script_name}' already exists"
                    )
                    return False
            
            # Add the script
            success = self._script_controller.add_external_script(script_name, str(path))

            if success:
                # Update the script list to reflect the new external script
                # This will be properly forwarded to the view via script_list_updated signal
                self._update_script_list()
                logger.info(f"Successfully added external script: {script_name}")
            else:
                self.error_occurred.emit(
                    "Add Failed",
                    f"Failed to add external script: {script_name}"
                )

            return success
            
        except Exception as e:
            logger.error(f"Error adding external script: {e}")
            self.error_occurred.emit("Add Error", f"Failed to add script: {str(e)}")
            return False
    
    def remove_external_script(self, script_name: str):
        """Remove an external script"""
        logger.info(f"Removing external script: {script_name}")
        
        try:
            # Capture stem for hotkey removal before removal
            stem = None
            try:
                info = self._script_controller.get_script_by_name(script_name)
                if info and hasattr(info, 'file_path'):
                    stem = info.file_path.stem
            except Exception:
                pass

            self._script_controller.remove_external_script(script_name)

            # Clear hotkey if one was assigned to this script
            if stem:
                try:
                    if self._script_controller.get_script_hotkey(stem):
                        self._script_controller.remove_script_hotkey(stem)
                        logger.info(f"Cleared hotkey for removed external script: {stem}")
                except Exception as e:
                    logger.warning(f"Failed clearing hotkey for removed external script {stem}: {e}")

            # Update the script list to reflect the removal
            self._update_script_list()
            
        except Exception as e:
            logger.error(f"Error removing external script {script_name}: {e}")
            self.error_occurred.emit("Remove Error", f"Failed to remove script: {str(e)}")
    
    # Preset management methods
    def get_script_presets(self, script_name: str) -> Dict[str, Any]:
        """Get presets for a script"""
        return self._settings_manager.get_script_presets(script_name)
    
    def save_script_preset(self, script_name: str, preset_name: str, arguments: Dict[str, Any]):
        """Save a preset for a script"""
        logger.info(f"Saving preset '{preset_name}' for script {script_name}")
        
        try:
            self._settings_manager.save_script_preset(script_name, preset_name, arguments)
            
            # Emit update
            presets = self._settings_manager.get_script_presets(script_name)
            # Map stem to display name for the view
            display_name = self._get_display_name_for_stem(script_name) or script_name
            self.preset_updated.emit(display_name, presets)
            
        except Exception as e:
            logger.error(f"Error saving preset for {script_name}: {e}")
            self.error_occurred.emit("Preset Error", f"Failed to save preset: {str(e)}")
    
    def delete_script_preset(self, script_name: str, preset_name: str):
        """Delete a preset for a script"""
        logger.info(f"Deleting preset '{preset_name}' for script {script_name}")
        
        try:
            self._settings_manager.delete_script_preset(script_name, preset_name)
            
            # Emit update
            presets = self._settings_manager.get_script_presets(script_name)
            # Map stem to display name for the view
            display_name = self._get_display_name_for_stem(script_name) or script_name
            self.preset_updated.emit(display_name, presets)
            
        except Exception as e:
            logger.error(f"Error deleting preset for {script_name}: {e}")
            self.error_occurred.emit("Preset Error", f"Failed to delete preset: {str(e)}")
    
    def auto_generate_presets(self, script_name: str):
        """Auto-generate presets for a script based on its arguments"""
        logger.info(f"Auto-generating presets for script {script_name}")
        
        try:
            script_info = self._script_collection.get_script_by_name(script_name)
            if not script_info or not script_info.arguments:
                self.error_occurred.emit(
                    "Generate Error",
                    "Script has no arguments to generate presets for"
                )
                return
            
            # Generate presets based on argument choices
            for arg in script_info.arguments:
                if arg.choices:
                    for choice in arg.choices:
                        preset_name = choice.replace('_', ' ').title()
                        arguments = {arg.name: choice}
                        self._settings_manager.save_script_preset(
                            script_info.file_path.stem,
                            preset_name,
                            arguments
                        )
            
            # Emit update
            presets = self._settings_manager.get_script_presets(script_info.file_path.stem)
            self.preset_updated.emit(script_name, presets)
            
            logger.info(f"Generated {len(presets)} presets for {script_name}")
            
        except Exception as e:
            logger.error(f"Error generating presets for {script_name}: {e}")
            self.error_occurred.emit("Generate Error", f"Failed to generate presets: {str(e)}")
    
    # Reset methods
    def reset_settings(self, category: str):
        """Reset settings for a specific category"""
        logger.info(f"Resetting settings for category: {category}")
        
        try:
            if category == 'all':
                # Clear all hotkeys first so runtime and caches update
                all_hotkeys = self._hotkey_model.get_all_hotkeys()
                for script_name in list(all_hotkeys.keys()):
                    self._script_controller.remove_script_hotkey(script_name)
                logger.info("All hotkeys cleared prior to full reset")

                # Reset all settings
                self._settings_manager.reset_all_settings()
                logger.info("All settings reset to defaults")
            elif category == 'hotkeys':
                # Clear all hotkeys
                all_hotkeys = self._hotkey_model.get_all_hotkeys()
                for script_name in all_hotkeys:
                    self._script_controller.remove_script_hotkey(script_name)
                logger.info("All hotkeys cleared")
            elif category == 'presets':
                # Clear all presets
                self._settings_manager.clear_all_presets()
                logger.info("All presets cleared")
            elif category == 'custom_names':
                # Clear all custom names
                self._settings_manager.clear_all_custom_names()
                logger.info("All custom names cleared")
            else:
                logger.warning(f"Unknown reset category: {category}")
                return
            
            # Reload all settings
            self.load_all_settings()
            self.settings_reset.emit(category)
            
        except Exception as e:
            logger.error(f"Error resetting {category}: {e}")
            self.error_occurred.emit("Reset Error", f"Failed to reset {category}: {str(e)}")
    
    # Helper methods
    def _find_script_with_hotkey(self, hotkey: str) -> Optional[str]:
        """Find which script has a specific hotkey assigned"""
        all_hotkeys = self._hotkey_model.get_all_hotkeys()
        for script_name, assigned_hotkey in all_hotkeys.items():
            if assigned_hotkey == hotkey:
                return script_name
        return None
    
    def validate_settings(self) -> Tuple[bool, str]:
        """Validate current settings before saving"""
        # Add any validation logic here
        # For now, all settings are valid
        return True, ""

    def _get_display_name_for_stem(self, stem: str) -> Optional[str]:
        """Find the display name for a script given its file stem."""
        try:
            for s in self._script_collection.get_all_scripts():
                if s.file_path.stem == stem:
                    return s.display_name
        except Exception:
            pass
        return None
    
    def save_all_settings(self):
        """Save all current settings"""
        logger.info("Saving all settings...")

        try:
            # Settings are automatically persisted by models when changed
            # This method is mainly for confirmation

            valid, error_msg = self.validate_settings()
            if not valid:
                self.error_occurred.emit("Validation Error", error_msg)
                return

            # Force sync to ensure everything is written
            self._settings_manager.sync()

            self.settings_saved.emit()
            logger.info("All settings saved successfully")

        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            self.error_occurred.emit("Save Error", f"Failed to save settings: {str(e)}")

    # Schedule management methods
    def set_schedule_enabled(self, script_name: str, enabled: bool) -> bool:
        """Enable or disable scheduling for a script.

        Args:
            script_name: Name of the script (display name or original name)
            enabled: Whether to enable scheduling

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Setting schedule enabled for {script_name}: {enabled}")

        try:
            if enabled:
                # When enabling, start the schedule
                script_info = self._script_collection.get_script_by_name(script_name)
                if not script_info:
                    logger.error(f"Script not found: {script_name}")
                    return False

                script_stem = script_info.file_path.stem

                # Get current interval from settings
                interval_seconds = self._settings_manager.get_schedule_interval(script_stem)

                # Mark as enabled in settings
                self._script_controller.set_schedule_enabled(script_name, True)

                # Start the schedule
                success = self._script_controller.start_schedule(script_name, interval_seconds)

                if success:
                    logger.info(f"Schedule enabled for {script_name}")
                    return True
                else:
                    # Revert setting if start failed
                    self._script_controller.set_schedule_enabled(script_name, False)
                    return False
            else:
                # When disabling, stop the schedule
                script_info = self._script_collection.get_script_by_name(script_name)
                if not script_info:
                    logger.error(f"Script not found: {script_name}")
                    return False

                # Mark as disabled in settings
                self._script_controller.set_schedule_enabled(script_name, False)

                # Stop the schedule
                success = self._script_controller.stop_schedule(script_name)

                if success:
                    logger.info(f"Schedule disabled for {script_name}")
                    return True
                else:
                    logger.error(f"Failed to stop schedule for {script_name}")
                    return False

        except Exception as e:
            logger.error(f"Error setting schedule enabled for {script_name}: {e}")
            self.error_occurred.emit("Schedule Error", f"Failed to set schedule: {str(e)}")
            return False

    def set_schedule_interval(self, script_name: str, interval_seconds: int) -> bool:
        """Set the execution interval for a scheduled script.

        Args:
            script_name: Name of the script (display name or original name)
            interval_seconds: Interval in seconds

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Setting schedule interval for {script_name}: {interval_seconds}s")

        try:
            script_info = self._script_collection.get_script_by_name(script_name)
            if not script_info:
                logger.error(f"Script not found: {script_name}")
                return False

            script_stem = script_info.file_path.stem

            # Update interval in settings
            self._settings_manager.set_schedule_interval(script_stem, interval_seconds)

            # If schedule is currently running, update it
            executor = self._script_execution._executor
            if executor and executor.is_schedule_running(script_stem):
                # Stop and restart with new interval
                executor.schedule_runtime.update_interval(script_stem, interval_seconds)
                logger.info(f"Updated running schedule for {script_name} to {interval_seconds}s")

            return True

        except Exception as e:
            logger.error(f"Error setting schedule interval for {script_name}: {e}")
            self.error_occurred.emit("Schedule Error", f"Failed to set interval: {str(e)}")
            return False

    def run_scheduled_script_now(self, script_name: str) -> bool:
        """Manually trigger a scheduled script to run immediately.

        Args:
            script_name: Name of the script (display name or original name)

        Returns:
            True if execution started successfully, False otherwise
        """
        logger.info(f"Running scheduled script now: {script_name}")

        try:
            # Just execute the script normally
            self._script_controller.execute_script(script_name)
            return True

        except Exception as e:
            logger.error(f"Error running scheduled script: {e}")
            self.error_occurred.emit("Execution Error", f"Failed to run script: {str(e)}")
            return False

    def get_schedule_info_for_display(self, script_name: str) -> Optional[Dict[str, Any]]:
        """Get schedule information formatted for UI display.

        Args:
            script_name: Name of the script (display name or original name)

        Returns:
            Dictionary with formatted schedule info, or None if not found
        """
        try:
            script_info = self._script_collection.get_script_by_name(script_name)
            if not script_info:
                return None

            script_stem = script_info.file_path.stem
            config = self._settings_manager.get_schedule_config(script_stem)

            from datetime import datetime

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

        except Exception as e:
            logger.error(f"Error getting schedule info for {script_name}: {e}")
            return None
