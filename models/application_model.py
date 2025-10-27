"""
Application Model - Core application state and business logic.

This model manages the overall application state and coordinates
between different subsystems while remaining UI-agnostic.
"""
import logging
from typing import Dict, Any, Optional
from PyQt6.QtCore import QObject, pyqtSignal

from core.settings import SettingsManager
from core.startup_manager import StartupManager

logger = logging.getLogger('Models.Application')


class ApplicationStateModel(QObject):
    """
    Core application state model that manages application-wide settings
    and coordinates between different subsystems.
    
    This model is the single source of truth for application state.
    """
    
    # Signals emitted when state changes
    application_starting = pyqtSignal()
    application_ready = pyqtSignal()
    application_shutting_down = pyqtSignal()
    startup_settings_changed = pyqtSignal(dict)  # Emits startup configuration
    behavior_settings_changed = pyqtSignal(dict)  # Emits behavior configuration
    execution_settings_changed = pyqtSignal(dict)  # Emits execution configuration
    
    def __init__(self):
        super().__init__()
        self._settings = SettingsManager()
        self._startup_manager = StartupManager()
        self._application_state = 'initializing'  # initializing -> ready -> shutting_down
        
        # Connect to settings changes
        self._settings.settings_changed.connect(self._on_setting_changed)
        
        logger.info("ApplicationStateModel initialized")
    
    # Application lifecycle
    def start_application(self):
        """Initialize application and emit ready signal"""
        self._application_state = 'starting'
        self.application_starting.emit()
        
        # Perform any application startup logic here
        logger.info("Application starting...")
        
        self._application_state = 'ready'
        self.application_ready.emit()
        logger.info("Application ready")
    
    def shutdown_application(self):
        """Prepare for application shutdown"""
        if self._application_state == 'shutting_down':
            return
            
        self._application_state = 'shutting_down'
        self.application_shutting_down.emit()
        logger.info("Application shutting down")
    
    def get_application_state(self) -> str:
        """Get current application state"""
        return self._application_state
    
    def is_ready(self) -> bool:
        """Check if application is ready for operations"""
        return self._application_state == 'ready'
    
    # Startup settings
    def get_startup_settings(self) -> dict:
        """Get all startup-related settings"""
        return {
            'run_on_startup': self._settings.get('startup/run_on_startup', False),
            'start_minimized': self._settings.get('startup/start_minimized', True),
            'show_notification': self._settings.get('startup/show_notification', True)
        }
    
    def set_run_on_startup(self, enabled: bool):
        """Enable or disable running on system startup"""
        self._settings.set('startup/run_on_startup', enabled)
        
        # Update system startup registration
        try:
            # Use StartupManager API (register/unregister)
            success = self._startup_manager.set_startup(enabled)
            if success and enabled:
                # Ensure path is up-to-date (e.g., after moves)
                try:
                    self._startup_manager.update_path_if_needed()
                except Exception:
                    pass
            
            logger.info(f"Startup registration {'enabled' if enabled else 'disabled'} (success={success})")
        except Exception as e:
            logger.error(f"Failed to update startup registration: {e}")
    
    def set_start_minimized(self, minimized: bool):
        """Set whether to start minimized to tray"""
        self._settings.set('startup/start_minimized', minimized)
    
    def set_show_startup_notification(self, show: bool):
        """Set whether to show notification on startup"""
        self._settings.set('startup/show_notification', show)
    
    def is_start_minimized(self) -> bool:
        """Check if application should start minimized"""
        return self._settings.get('startup/start_minimized', True)
    
    def should_show_startup_notification(self) -> bool:
        """Check if startup notification should be shown"""
        return self._settings.get('startup/show_notification', True)
    
    # Behavior settings
    def get_behavior_settings(self) -> dict:
        """Get all behavior-related settings"""
        return {
            'minimize_to_tray': self._settings.get('behavior/minimize_to_tray', True),
            'close_to_tray': self._settings.get('behavior/close_to_tray', True),
            'single_instance': self._settings.get('behavior/single_instance', True),
            'show_script_notifications': self._settings.get('behavior/show_script_notifications', True),
            'check_for_updates': self._settings.get('behavior/check_for_updates', True)
        }
    
    def set_minimize_to_tray(self, enabled: bool):
        """Set whether to minimize to tray instead of taskbar"""
        self._settings.set('behavior/minimize_to_tray', enabled)
    
    def set_close_to_tray(self, enabled: bool):
        """Set whether closing window minimizes to tray"""
        self._settings.set('behavior/close_to_tray', enabled)
    
    def set_single_instance(self, enabled: bool):
        """Set whether only one application instance is allowed"""
        self._settings.set('behavior/single_instance', enabled)
    
    def set_show_script_notifications(self, enabled: bool):
        """Set whether to show script execution notifications"""
        self._settings.set('behavior/show_script_notifications', enabled)
    
    def should_minimize_to_tray(self) -> bool:
        """Check if application should minimize to tray"""
        return self._settings.get('behavior/minimize_to_tray', True)
    
    def should_close_to_tray(self) -> bool:
        """Check if closing should minimize to tray"""
        return self._settings.get('behavior/close_to_tray', True)
    
    def is_single_instance_enabled(self) -> bool:
        """Check if single instance mode is enabled"""
        return self._settings.get('behavior/single_instance', True)
    
    def should_show_script_notifications(self) -> bool:
        """Check if script notifications should be shown"""
        return self._settings.get('behavior/show_script_notifications', True)

    def set_check_for_updates(self, enabled: bool):
        """Set whether to automatically check for updates"""
        self._settings.set('behavior/check_for_updates', enabled)

    def should_check_for_updates(self) -> bool:
        """Check if automatic update checking is enabled"""
        return self._settings.get('behavior/check_for_updates', True)

    # Execution settings
    def get_execution_settings(self) -> dict:
        """Get all execution-related settings"""
        return {
            'script_timeout_seconds': self._settings.get('execution/script_timeout_seconds', 30)
        }
    
    def set_script_timeout_seconds(self, timeout: int):
        """Set script execution timeout in seconds"""
        self._settings.set('execution/script_timeout_seconds', timeout)
    
    # Removed status refresh setting (refresh is fixed at 5s in execution model)
    
    def get_script_timeout_seconds(self) -> int:
        """Get script execution timeout"""
        return self._settings.get('execution/script_timeout_seconds', 30)
    
    # Removed getter for status refresh (not configurable)
    
    # Window settings
    def save_window_geometry(self, geometry: bytes):
        """Save window geometry"""
        self._settings.set('window/geometry', geometry)
    
    def get_window_geometry(self) -> Optional[bytes]:
        """Get saved window geometry"""
        return self._settings.get('window/geometry')
    
    def save_window_position(self, position: tuple):
        """Save window position"""
        self._settings.set('window/last_position', position)
    
    def get_window_position(self) -> Optional[tuple]:
        """Get saved window position"""
        return self._settings.get('window/last_position')
    
    # Internal signal handlers
    def _on_setting_changed(self, key: str, value: Any):
        """Handle settings changes and emit appropriate signals"""
        if key.startswith('startup/'):
            self.startup_settings_changed.emit(self.get_startup_settings())
        elif key.startswith('behavior/'):
            self.behavior_settings_changed.emit(self.get_behavior_settings())
        elif key.startswith('execution/'):
            self.execution_settings_changed.emit(self.get_execution_settings())
        
        logger.debug(f"Application setting changed: {key} = {value}")
