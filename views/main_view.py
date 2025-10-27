"""
Main View - Minimal main window for dialog parent and window management.

This view serves as a parent window for dialogs and handles basic
window state management without business logic.
"""
import logging
from typing import Optional
from PyQt6.QtWidgets import QMainWindow
from PyQt6.QtCore import pyqtSignal

logger = logging.getLogger('Views.Main')


class MainView(QMainWindow):
    """
    Minimal main window view that serves as a parent for dialogs.
    
    This view:
    - Provides a parent window for modal dialogs
    - Handles basic window state events
    - Remains hidden during normal operation
    - Emits signals for window state changes
    """
    
    # Signals for window events
    window_closing = pyqtSignal()
    window_minimized = pyqtSignal()
    window_restored = pyqtSignal()
    geometry_changed = pyqtSignal(bytes)  # window geometry data
    position_changed = pyqtSignal(int, int)  # x, y coordinates
    
    def __init__(self):
        super().__init__()
        
        # Set basic window properties
        self.setWindowTitle("BindKit Main Window")
        
        # Keep window hidden by default (tray-only operation)
        self.hide()
        
        logger.info("MainView initialized (hidden)")
    
    def show_window(self):
        """Show the main window"""
        self.show()
        self.raise_()
        self.activateWindow()
        logger.debug("Main window shown")
    
    def hide_window(self):
        """Hide the main window"""
        self.hide()
        logger.debug("Main window hidden")
    
    def minimize_window(self):
        """Minimize the main window"""
        self.showMinimized()
        self.window_minimized.emit()
        logger.debug("Main window minimized")
    
    def restore_window(self):
        """Restore the main window from minimized state"""
        self.showNormal()
        self.window_restored.emit()
        logger.debug("Main window restored")
    
    def save_window_geometry(self):
        """Save current window geometry and emit signal"""
        geometry = self.saveGeometry()
        self.geometry_changed.emit(geometry)
        logger.debug("Window geometry saved")
    
    def restore_window_geometry(self, geometry: bytes) -> bool:
        """Restore window geometry from saved data"""
        try:
            success = self.restoreGeometry(geometry)
            if success:
                logger.debug("Window geometry restored")
            else:
                logger.warning("Failed to restore window geometry")
            return success
        except Exception as e:
            logger.error(f"Error restoring window geometry: {e}")
            return False
    
    def save_window_position(self):
        """Save current window position and emit signal"""
        pos = self.pos()
        self.position_changed.emit(pos.x(), pos.y())
        logger.debug(f"Window position saved: ({pos.x()}, {pos.y()})")
    
    def set_window_position(self, x: int, y: int):
        """Set window position"""
        self.move(x, y)
        logger.debug(f"Window position set: ({x}, {y})")
    
    def is_window_minimized(self) -> bool:
        """Check if window is minimized"""
        return self.isMinimized()
    
    def is_window_visible(self) -> bool:
        """Check if window is visible"""
        return self.isVisible()
    
    # Qt event handlers
    def closeEvent(self, event):
        """Handle window close event"""
        # In MVC pattern, the view just reports the event
        # The controller will decide what to do (minimize to tray vs exit)
        self.window_closing.emit()
        
        # Don't actually close yet - let controller decide
        event.ignore()
        logger.debug("Window close event emitted")
    
    def changeEvent(self, event):
        """Handle window state change events"""
        super().changeEvent(event)
        
        # Emit appropriate signals for state changes
        if event.type() == event.Type.WindowStateChange:
            if self.isMinimized():
                self.window_minimized.emit()
            elif self.windowState() == self.windowState().WindowNoState:
                self.window_restored.emit()
    
    def moveEvent(self, event):
        """Handle window move events"""
        super().moveEvent(event)
        # Emit position change (could be used to auto-save position)
        pos = event.pos()
        self.position_changed.emit(pos.x(), pos.y())
    
    def resizeEvent(self, event):
        """Handle window resize events"""
        super().resizeEvent(event)
        # Could emit geometry change here if needed for auto-save
        # For now, geometry is saved explicitly when needed