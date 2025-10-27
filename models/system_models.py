"""
System Models - Handle system integration and UI state.

These models manage system tray state, notifications, and other
system-level interactions while remaining UI-agnostic.
"""
import logging
from typing import Optional, Dict, Any
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QSystemTrayIcon

logger = logging.getLogger('Models.System')


class TrayIconModel(QObject):
    """
    Model for managing system tray icon state and behavior.
    
    Handles tray icon visibility, tooltip, and notification management
    without direct UI dependencies.
    """
    
    # Signals for tray icon state changes
    icon_visibility_changed = pyqtSignal(bool)  # visible
    tooltip_changed = pyqtSignal(str)  # tooltip text
    notification_requested = pyqtSignal(str, str, object)  # title, message, icon_type
    menu_update_requested = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self._visible = False
        self._tooltip = "BindKit"
        self._supports_notifications = False
        
        logger.info("TrayIconModel initialized")
    
    def show_icon(self):
        """Show the tray icon"""
        if not self._visible:
            self._visible = True
            self.icon_visibility_changed.emit(True)
            logger.debug("Tray icon shown")
    
    def hide_icon(self):
        """Hide the tray icon"""
        if self._visible:
            self._visible = False
            self.icon_visibility_changed.emit(False)
            logger.debug("Tray icon hidden")
    
    def is_visible(self) -> bool:
        """Check if tray icon is visible"""
        return self._visible
    
    def set_tooltip(self, tooltip: str):
        """Set tray icon tooltip"""
        if self._tooltip != tooltip:
            self._tooltip = tooltip
            self.tooltip_changed.emit(tooltip)
            logger.debug(f"Tray tooltip changed: {tooltip}")
    
    def get_tooltip(self) -> str:
        """Get current tooltip"""
        return self._tooltip
    
    def set_supports_notifications(self, supported: bool):
        """Set whether the system supports tray notifications"""
        self._supports_notifications = supported
        logger.debug(f"Tray notifications supported: {supported}")
    
    def supports_notifications(self) -> bool:
        """Check if system supports tray notifications"""
        return self._supports_notifications
    
    def show_notification(self, title: str, message: str, 
                         icon_type: QSystemTrayIcon.MessageIcon = QSystemTrayIcon.MessageIcon.Information):
        """Request a tray notification to be shown"""
        if self._supports_notifications:
            self.notification_requested.emit(title, message, icon_type)
            logger.debug(f"Notification requested: {title}")
        else:
            logger.debug("Notification requested but not supported")
    
    def request_menu_update(self):
        """Request that the tray menu be updated"""
        self.menu_update_requested.emit()


class NotificationModel(QObject):
    """
    Model for managing application notifications and their settings.
    
    Centralizes notification logic and preferences while remaining
    independent of the actual notification display mechanism.
    """
    
    # Signals for notification events
    notification_shown = pyqtSignal(str, str, object)  # title, message, icon_type
    notification_settings_changed = pyqtSignal(dict)  # notification preferences
    
    def __init__(self, application_model):
        super().__init__()
        self._app_model = application_model
        self._notification_history = []
        self._max_history_size = 100
        
        # Connect to application behavior changes
        self._app_model.behavior_settings_changed.connect(self._on_behavior_settings_changed)
        
        logger.info("NotificationModel initialized")
    
    def should_show_notification(self, notification_type: str = "general") -> bool:
        """Check if notifications should be shown based on settings"""
        if notification_type == "script":
            return self._app_model.should_show_script_notifications()
        elif notification_type == "startup":
            return self._app_model.should_show_startup_notification()
        else:
            return True  # General notifications are always shown
    
    def show_notification(self, title: str, message: str, 
                         icon_type: QSystemTrayIcon.MessageIcon = QSystemTrayIcon.MessageIcon.Information,
                         notification_type: str = "general"):
        """Show a notification if allowed by settings"""
        if self.should_show_notification(notification_type):
            self._add_to_history(title, message, icon_type)
            self.notification_shown.emit(title, message, icon_type)
            logger.debug(f"Notification shown: {title}")
        else:
            logger.debug(f"Notification suppressed by settings: {title}")
    
    def show_script_notification(self, script_name: str, message: str, success: bool = True):
        """Show a script execution notification"""
        if success:
            title = f"Script Completed: {script_name}"
            icon_type = QSystemTrayIcon.MessageIcon.Information
        else:
            title = f"Script Failed: {script_name}"
            icon_type = QSystemTrayIcon.MessageIcon.Warning
        
        self.show_notification(title, message, icon_type, "script")
    
    def show_startup_notification(self):
        """Show the application startup notification"""
        if self._app_model.should_show_startup_notification():
            self.show_notification(
                "BindKit Started",
                "Application started in system tray. Click the tray icon to access scripts.",
                QSystemTrayIcon.MessageIcon.Information,
                "startup"
            )
    
    def show_error_notification(self, title: str, message: str):
        """Show an error notification (always shown regardless of settings)"""
        self._add_to_history(title, message, QSystemTrayIcon.MessageIcon.Critical)
        self.notification_shown.emit(title, message, QSystemTrayIcon.MessageIcon.Critical)
        logger.warning(f"Error notification: {title} - {message}")
    
    def show_warning_notification(self, title: str, message: str):
        """Show a warning notification"""
        self.show_notification(title, message, QSystemTrayIcon.MessageIcon.Warning)
    
    def get_notification_history(self) -> list:
        """Get recent notification history"""
        return self._notification_history.copy()
    
    def clear_notification_history(self):
        """Clear notification history"""
        self._notification_history.clear()
        logger.debug("Notification history cleared")
    
    def _add_to_history(self, title: str, message: str, icon_type: QSystemTrayIcon.MessageIcon):
        """Add notification to history"""
        import datetime
        
        notification = {
            'title': title,
            'message': message,
            'icon_type': icon_type,
            'timestamp': datetime.datetime.now()
        }
        
        self._notification_history.append(notification)
        
        # Keep history size manageable
        if len(self._notification_history) > self._max_history_size:
            self._notification_history = self._notification_history[-self._max_history_size:]
    
    def _on_behavior_settings_changed(self, settings: dict):
        """Handle behavior settings changes"""
        self.notification_settings_changed.emit(settings)


class WindowStateModel(QObject):
    """
    Model for managing window state and geometry.
    
    Tracks window positions, sizes, and states while remaining
    independent of actual window implementations.
    """
    
    # Signals for window state changes
    geometry_save_requested = pyqtSignal(bytes)  # geometry data
    position_save_requested = pyqtSignal(tuple)  # x, y position
    window_restore_requested = pyqtSignal()
    window_minimize_requested = pyqtSignal()
    
    def __init__(self, application_model):
        super().__init__()
        self._app_model = application_model
        self._current_geometry = None
        self._current_position = None
        self._is_minimized = False
        
        logger.info("WindowStateModel initialized")
    
    def save_geometry(self, geometry: bytes):
        """Save current window geometry"""
        self._current_geometry = geometry
        self._app_model.save_window_geometry(geometry)
        self.geometry_save_requested.emit(geometry)
        logger.debug("Window geometry saved")
    
    def restore_geometry(self) -> Optional[bytes]:
        """Get saved geometry for restoration"""
        saved_geometry = self._app_model.get_window_geometry()
        if saved_geometry:
            self._current_geometry = saved_geometry
            return saved_geometry
        return None
    
    def save_position(self, x: int, y: int):
        """Save current window position"""
        position = (x, y)
        self._current_position = position
        self._app_model.save_window_position(position)
        self.position_save_requested.emit(position)
        logger.debug(f"Window position saved: {position}")
    
    def restore_position(self) -> Optional[tuple]:
        """Get saved position for restoration"""
        saved_position = self._app_model.get_window_position()
        if saved_position:
            self._current_position = saved_position
            return saved_position
        return None
    
    def set_minimized(self, minimized: bool):
        """Set window minimized state"""
        if self._is_minimized != minimized:
            self._is_minimized = minimized
            if minimized:
                self.window_minimize_requested.emit()
            else:
                self.window_restore_requested.emit()
            logger.debug(f"Window minimized state: {minimized}")
    
    def is_minimized(self) -> bool:
        """Check if window is minimized"""
        return self._is_minimized
    
    def should_minimize_to_tray(self) -> bool:
        """Check if window should minimize to tray"""
        return self._app_model.should_minimize_to_tray()
    
    def should_close_to_tray(self) -> bool:
        """Check if window should minimize to tray on close"""
        return self._app_model.should_close_to_tray()