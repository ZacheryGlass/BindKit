"""
Application Controller - Main controller that orchestrates the MVC architecture.

This controller manages the application lifecycle, coordinates between models,
and sets up the primary signal/slot connections for the MVC pattern.
"""
import logging
from typing import Optional
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication

from models.application_model import ApplicationStateModel
from models.script_models import ScriptCollectionModel, ScriptExecutionModel, HotkeyModel
from models.system_models import TrayIconModel, NotificationModel, WindowStateModel

logger = logging.getLogger('Controllers.App')


class AppController(QObject):
    """
    Main application controller that orchestrates the MVC architecture.
    
    This controller:
    - Manages the lifecycle of all models
    - Coordinates high-level application operations
    - Sets up the foundational MVC connections
    - Handles application startup and shutdown
    """
    
    # High-level application signals
    application_initialized = pyqtSignal()
    application_ready = pyqtSignal()
    application_shutting_down = pyqtSignal()
    
    def __init__(self, scripts_directory: str = "scripts"):
        super().__init__()
        
        # Initialize all models
        self._app_model = ApplicationStateModel()
        self._script_collection = ScriptCollectionModel(scripts_directory)
        self._script_execution = ScriptExecutionModel(self._script_collection)
        self._hotkey_model = HotkeyModel()
        self._tray_model = TrayIconModel()
        self._notification_model = NotificationModel(self._app_model)
        self._window_model = WindowStateModel(self._app_model)
        
        # Store references for other controllers
        self._script_controller = None
        self._settings_controller = None
        self._tray_controller = None
        
        # Connect model signals for coordination
        self._setup_model_coordination()
        
        logger.info("AppController initialized")
    
    def initialize_application(self):
        """Initialize the application and all subsystems"""
        logger.info("Initializing application...")
        
        try:
            # Start application model
            self._app_model.start_application()
            
            # Initialize tray icon
            self._tray_model.show_icon()
            
            # Discover scripts
            self._script_collection.discover_scripts()
            
            # Set up tray system availability
            from PyQt6.QtWidgets import QSystemTrayIcon
            self._tray_model.set_supports_notifications(QSystemTrayIcon.supportsMessages())
            
            self.application_initialized.emit()
            logger.info("Application initialization complete")
            
        except Exception as e:
            logger.error(f"Error during application initialization: {e}")
            raise
    
    def finalize_startup(self):
        """Complete application startup and emit ready signal"""
        logger.info("Finalizing application startup...")

        try:
            # Start all scheduled scripts
            self._start_scheduled_scripts()

            # Show startup notification if appropriate
            if self._app_model.is_start_minimized():
                self._notification_model.show_startup_notification()

            self.application_ready.emit()
            logger.info("Application startup complete")

        except Exception as e:
            logger.error(f"Error during startup finalization: {e}")
    
    def shutdown_application(self):
        """Gracefully shut down the application"""
        logger.info("Shutting down application...")

        # Stop all scheduled scripts
        try:
            self._stop_scheduled_scripts()
        except Exception as e:
            logger.error(f"Error stopping scheduled scripts: {e}")

        self.application_shutting_down.emit()
        self._app_model.shutdown_application()

        # Clean up models
        try:
            self._tray_model.hide_icon()
            logger.info("Application shutdown complete")
        except Exception as e:
            logger.error(f"Error during application shutdown: {e}")
    
    def set_script_controller(self, controller):
        """Set the script controller reference"""
        self._script_controller = controller
    
    def set_settings_controller(self, controller):
        """Set the settings controller reference"""
        self._settings_controller = controller
    
    def set_tray_controller(self, controller):
        """Set the tray controller reference"""
        self._tray_controller = controller
    
    # Model accessors for other controllers
    def get_application_model(self) -> ApplicationStateModel:
        """Get the application state model"""
        return self._app_model
    
    def get_script_collection_model(self) -> ScriptCollectionModel:
        """Get the script collection model"""
        return self._script_collection
    
    def get_script_execution_model(self) -> ScriptExecutionModel:
        """Get the script execution model"""
        return self._script_execution
    
    def get_hotkey_model(self) -> HotkeyModel:
        """Get the hotkey model"""
        return self._hotkey_model
    
    def get_tray_model(self) -> TrayIconModel:
        """Get the tray icon model"""
        return self._tray_model
    
    def get_notification_model(self) -> NotificationModel:
        """Get the notification model"""
        return self._notification_model
    
    def get_window_model(self) -> WindowStateModel:
        """Get the window state model"""
        return self._window_model
    
    def _setup_model_coordination(self):
        """Set up signal connections between models for coordination"""
        logger.debug("Setting up model coordination...")
        
        # Connect script execution to notifications
        self._script_execution.script_execution_completed.connect(
            self._on_script_execution_completed
        )
        self._script_execution.script_execution_failed.connect(
            self._on_script_execution_failed
        )
        
        # Connect notification model to tray model
        self._notification_model.notification_shown.connect(
            self._tray_model.show_notification
        )
        
        # Connect script collection changes to tray menu updates
        self._script_collection.scripts_filtered.connect(
            lambda scripts: self._tray_model.request_menu_update()
        )
        
        # Connect hotkey changes to tray menu updates
        self._hotkey_model.hotkeys_changed.connect(
            lambda: self._tray_model.request_menu_update()
        )
        
        # Connect application settings changes to relevant updates
        self._app_model.behavior_settings_changed.connect(
            self._on_behavior_settings_changed
        )
        
        logger.debug("Model coordination setup complete")
    
    def _on_script_execution_completed(self, script_name: str, result: dict):
        """Handle successful script execution"""
        if self._script_execution.should_show_notifications_for_script(script_name):
            message = result.get('message', 'Completed successfully')
            self._notification_model.show_script_notification(
                script_name, message, success=True
            )
    
    def _on_script_execution_failed(self, script_name: str, error: str):
        """Handle failed script execution"""
        if self._script_execution.should_show_notifications_for_script(script_name):
            self._notification_model.show_script_notification(
                script_name, error, success=False
            )
    
    def _on_behavior_settings_changed(self, settings: dict):
        """Handle behavior settings changes"""
        logger.debug(f"Behavior settings changed: {settings}")
        # This can trigger various UI updates through other controllers

    def _start_scheduled_scripts(self):
        """Start all scheduled scripts at application startup"""
        logger.info("Starting scheduled scripts...")

        try:
            if not self._script_controller:
                logger.warning("ScriptController not available for scheduling")
                return

            # Get all scripts that have scheduling enabled
            scheduled_scripts = self._script_execution._executor.settings_manager.get_all_scheduled_scripts()

            if not scheduled_scripts:
                logger.info("No scheduled scripts configured")
                return

            logger.info(f"Found {len(scheduled_scripts)} scheduled script(s)")

            for script_stem in scheduled_scripts:
                try:
                    # Get the script info by stem
                    script_info = None
                    for script in self._script_collection.get_all_scripts():
                        if script.file_path.stem == script_stem:
                            script_info = script
                            break

                    if not script_info:
                        logger.warning(f"Scheduled script not found: {script_stem}")
                        continue

                    # Get interval from settings
                    interval_seconds = self._script_execution._executor.settings_manager.get_schedule_interval(script_stem)

                    # Start the schedule via ScriptController
                    display_name = self._script_collection.get_script_display_name(script_info)
                    success = self._script_controller.start_schedule(display_name, interval_seconds)

                    if success:
                        logger.info(f"Started schedule for '{display_name}' (interval: {interval_seconds}s)")
                    else:
                        logger.error(f"Failed to start schedule for '{display_name}'")

                except Exception as e:
                    logger.error(f"Error starting schedule for '{script_stem}': {e}")

            logger.info("Scheduled scripts startup complete")

        except Exception as e:
            logger.error(f"Error starting scheduled scripts: {e}")

    def _stop_scheduled_scripts(self):
        """Stop all active scheduled scripts before application shutdown"""
        logger.info("Stopping scheduled scripts...")

        try:
            if not self._script_controller:
                logger.warning("ScriptController not available for shutdown")
                return

            executor = self._script_execution._executor
            if not executor:
                logger.warning("ScriptExecutor not available")
                return

            # Get all active schedules
            active_schedules = executor.get_all_schedules()

            if not active_schedules:
                logger.info("No active schedules to stop")
                return

            logger.info(f"Stopping {len(active_schedules)} active schedule(s)")

            for script_stem in list(active_schedules.keys()):
                try:
                    # Stop the schedule via ScriptController
                    success = self._script_controller.stop_schedule(script_stem)

                    if success:
                        logger.info(f"Stopped schedule for '{script_stem}'")
                    else:
                        logger.error(f"Failed to stop schedule for '{script_stem}'")

                except Exception as e:
                    logger.error(f"Error stopping schedule for '{script_stem}': {e}")

            logger.info("Scheduled scripts shutdown complete")

        except Exception as e:
            logger.error(f"Error stopping scheduled scripts: {e}")