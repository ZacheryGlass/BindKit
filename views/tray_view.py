"""
Tray View - UI component for system tray interactions.

This view handles the visual representation and user interactions
for the system tray icon and menu, while remaining "dumb" about
business logic.
"""
import logging
import gc
import weakref
from typing import Optional, Dict, Any, List
from PyQt6.QtWidgets import (QSystemTrayIcon, QMenu, QWidget)
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, Qt, QEvent
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QBrush, QPen, QCursor, QAction, QKeyEvent, QColor

from views.script_launcher_view import ScriptLauncherWidget

logger = logging.getLogger('Views.Tray')


class MenuKeyEventFilter(QObject):
    """Event filter to handle ESC key presses in menus"""

    def eventFilter(self, obj, event):
        """Handle key press events"""
        if event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                # Close the menu when ESC is pressed
                if isinstance(obj, QMenu):
                    obj.close()
                return True
        return super().eventFilter(obj, event)


class TrayView(QObject):
    """
    View component for system tray interactions.
    
    This view:
    - Displays the system tray icon and menu
    - Handles user interactions with tray elements
    - Emits signals for user actions
    - Updates display based on controller requests
    """
    
    # Signals for user interactions
    menu_action_triggered = pyqtSignal(dict)  # action data
    title_clicked = pyqtSignal()
    exit_requested = pyqtSignal()
    settings_requested = pyqtSignal()

    # Cleanup configuration
    _CLEANUP_FREQUENCY = 5  # Perform aggressive cleanup every N menu updates

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__()
        self.parent = parent
        
        # Track menu objects for proper cleanup
        self._menu_actions = []  # List to track QAction objects for context menu
        self._submenus = []  # List to track QMenu objects for context menu
        self._menu_update_count = 0  # Track updates for periodic cleanup

        # Create tray icon
        self.tray_icon = QSystemTrayIcon(parent)
        self.tray_icon.setToolTip("Desktop Utilities")

        # Create context menu (for tray icon clicks)
        self.context_menu = QMenu(parent)
        self.context_menu.setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
        )

        # Install event filter for ESC key handling
        self._key_event_filter = MenuKeyEventFilter()
        self.context_menu.installEventFilter(self._key_event_filter)

        # Create script launcher widget (replaces old hotkey menu)
        self.script_launcher = ScriptLauncherWidget(parent)
        self.script_launcher.script_execute_requested.connect(self.menu_action_triggered.emit)

        # Create and set icon
        self._create_tray_icon()

        # Connect signals
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.setContextMenu(self.context_menu)

        logger.info("TrayView initialized")

    def refresh_theme(self):
        """Reapply theme-sensitive styling for launcher."""
        try:
            self.script_launcher.refresh_theme()
        except Exception as exc:
            logger.debug(f"Failed to refresh launcher theme styling: {exc}")

    def show_icon(self):
        """Show the tray icon"""
        self.tray_icon.show()
        logger.debug("Tray icon shown")
    
    def hide_icon(self):
        """Hide the tray icon"""
        self.tray_icon.hide()
        logger.debug("Tray icon hidden")
    
    def set_tooltip(self, tooltip: str):
        """Set the tray icon tooltip"""
        self.tray_icon.setToolTip(tooltip)
        logger.debug(f"Tray tooltip set: {tooltip}")
    
    def show_notification(self, title: str, message: str, 
                         icon_type: QSystemTrayIcon.MessageIcon = QSystemTrayIcon.MessageIcon.Information):
        """Show a system tray notification"""
        if self.tray_icon.supportsMessages():
            self.tray_icon.showMessage(title, message, icon_type, 3000)
            logger.debug(f"Notification shown: {title}")
        else:
            logger.debug("Notification requested but not supported")
    
    def supports_notifications(self) -> bool:
        """Check if system supports tray notifications"""
        return self.tray_icon.supportsMessages()

    def show_menu_at_center(self):
        """Show the script launcher at the center of the screen"""
        # Show the launcher widget instead of the old menu
        self.script_launcher.show_at_center()
        logger.debug("Script launcher shown at center")

    def update_launcher_scripts(self, scripts: List[Dict[str, Any]], show_hotkeys: bool = True):
        """Update the script launcher with current script data"""
        self.script_launcher.update_scripts(scripts, show_hotkeys)
        logger.debug(f"Launcher updated with {len(scripts)} scripts, show_hotkeys={show_hotkeys}")

    def update_menu_structure(self, menu_structure: Dict[str, Any]):
        """Update the menu structure based on provided data"""
        logger.debug("Updating menu structure...")

        try:
            # Perform deep cleanup of existing menu objects
            self._cleanup_menu_objects()

            # Force immediate cleanup to prevent accumulation
            self._force_immediate_cleanup()

            # Clear context menu
            self.context_menu.clear()

            # Reset tracking lists for context menu
            self._menu_actions = []
            self._submenus = []

            # Build context menu with the structure
            self._build_menu(self.context_menu, self._menu_actions, self._submenus, menu_structure)

            menu_items = menu_structure.get('items', [])
            logger.debug(f"Context menu updated with {len(menu_items)} items")

            # Perform aggressive cleanup periodically for better memory management
            self._menu_update_count += 1
            if self._menu_update_count % self._CLEANUP_FREQUENCY == 0:
                self._perform_aggressive_cleanup()
            
        except Exception as e:
            logger.error(f"Error updating menu structure: {e}")
    
    def _build_menu(self, menu: QMenu, actions_list: list, submenus_list: list, menu_structure: Dict[str, Any]):
        """Build a menu with the given structure and tracking lists"""
        # Add title (clickable)
        title_text = menu_structure.get('title', 'Desktop Utilities')
        title_action = QAction(title_text, menu)
        title_action.triggered.connect(self.title_clicked.emit)
        menu.addAction(title_action)
        actions_list.append(title_action)

        # Add separator
        menu.addSeparator()

        # Add menu items
        menu_items = menu_structure.get('items', [])
        for item_data in menu_items:
            self._add_menu_item(menu, item_data, actions_list, submenus_list)

        # Add bottom separator and exit
        menu.addSeparator()
        exit_action = QAction("Exit", menu)
        exit_action.triggered.connect(self.exit_requested.emit)
        menu.addAction(exit_action)
        actions_list.append(exit_action)

    def _add_menu_item(self, parent_menu: QMenu, item_data: Dict[str, Any], actions_list: list = None, submenus_list: list = None):
        """Add a menu item based on item data"""
        # Use provided tracking lists or fall back to context menu tracking lists
        if actions_list is None:
            actions_list = self._menu_actions
        if submenus_list is None:
            submenus_list = self._submenus

        item_type = item_data.get('type', 'action')
        text = item_data.get('text', '')
        enabled = item_data.get('enabled', True)

        if item_type == 'action':
            # Check if this is a running script (show with special indicator)
            is_running = item_data.get('is_running', False)
            if is_running:
                text = f"⏳ {text}"

            action = QAction(text, parent_menu)
            action.setEnabled(enabled)

            # Icons removed in favor of text labels

            # Connect action if data is provided
            action_data = item_data.get('data')
            if action_data and enabled:
                action.triggered.connect(
                    lambda checked, data=action_data: self.menu_action_triggered.emit(data)
                )

            parent_menu.addAction(action)
            actions_list.append(action)

        elif item_type == 'submenu':
            submenu = QMenu(text, parent_menu)
            submenu.setWindowFlags(
                Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
            )
            submenus_list.append(submenu)

            # Add submenu items (recursively with same tracking lists)
            submenu_items = item_data.get('items', [])
            for subitem_data in submenu_items:
                self._add_menu_item(submenu, subitem_data, actions_list, submenus_list)

            # Add submenu to parent
            parent_menu.addMenu(submenu)

        elif item_type == 'separator':
            parent_menu.addSeparator()
    
    def _create_tray_icon(self):
        """Create the tray icon programmatically"""
        try:
            # Create a simple icon programmatically
            pixmap = QPixmap(64, 64)
            pixmap.fill(Qt.GlobalColor.transparent)
            
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # Draw a rounded rectangle background
            painter.setBrush(QBrush(Qt.GlobalColor.lightGray))
            painter.setPen(QPen(Qt.GlobalColor.darkCyan, 2))
            painter.drawRoundedRect(4, 4, 56, 56, 10, 10)
            
            # Draw "DU" text
            painter.setPen(QPen(Qt.GlobalColor.black, 2))
            font = painter.font()
            font.setPointSize(20)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "DU")
            
            painter.end()
            
            icon = QIcon(pixmap)
            self.tray_icon.setIcon(icon)
            
        except Exception as e:
            logger.error(f"Error creating tray icon: {e}")
            # Fallback to system icon
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                self.tray_icon.setIcon(app.style().standardIcon(
                    app.style().StandardPixmap.SP_ComputerIcon))

    def _on_tray_activated(self, reason):
        """Handle tray icon activation"""
        # Show context menu on right-click (Context) and single left-click (Trigger)
        if reason == QSystemTrayIcon.ActivationReason.Context:
            self.context_menu.popup(QCursor.pos())
        elif reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.context_menu.popup(QCursor.pos())
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            # Double-click: open settings (via title click signal)
            self.title_clicked.emit()
    
    def _cleanup_menu_objects(self):
        """Explicitly clean up menu objects to prevent accumulation."""
        try:
            # Clean up context menu actions
            for action in self._menu_actions:
                if action is None:
                    continue

                try:
                    # Check if action is still valid before disconnecting
                    # Try to access a property to verify object validity
                    _ = action.text()

                    # Disconnect all signals
                    try:
                        action.triggered.disconnect()
                    except (TypeError, RuntimeError):
                        # Signal not connected or already disconnected
                        pass

                    # Schedule for deletion
                    action.deleteLater()
                except RuntimeError:
                    # C++ object already deleted, skip it
                    logger.debug(f"Action object already deleted, skipping cleanup")
                    pass

            # Clean up context menu submenus
            for submenu in self._submenus:
                submenu.clear()
                submenu.deleteLater()

            # Clear all tracking lists
            self._menu_actions.clear()
            self._submenus.clear()

            logger.debug("Menu objects cleaned up")

        except Exception as e:
            logger.error(f"Error during menu cleanup: {e}")
    
    def _force_immediate_cleanup(self):
        """Force immediate cleanup of Qt objects to prevent memory accumulation."""
        try:
            # Force Qt to process all pending deleteLater events immediately
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                # Process events multiple times to ensure all deleteLater objects are cleaned up
                for _ in range(3):
                    app.processEvents()
                    
            logger.debug("Immediate cleanup forced")
            
        except Exception as e:
            logger.error(f"Error during immediate cleanup: {e}")

    def _perform_aggressive_cleanup(self):
        """Perform aggressive memory cleanup periodically."""
        try:
            # Force Qt to process deleteLater events
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                app.processEvents()
            
            # Force Python garbage collection
            collected = gc.collect()
            
            logger.debug(f"Aggressive cleanup performed, collected {collected} objects")
            
        except Exception as e:
            logger.error(f"Error during aggressive cleanup: {e}")
    
    def cleanup(self):
        """Clean up resources"""
        # Block signals to prevent issues during cleanup
        try:
            self.blockSignals(True)
            if self.tray_icon:
                self.tray_icon.blockSignals(True)
        except Exception:
            pass
        
        # Clean up menu objects
        self._cleanup_menu_objects()

        # Clear context menu
        self.context_menu.clear()

        # Clean up script launcher
        if self.script_launcher:
            try:
                self.script_launcher.script_execute_requested.disconnect()
            except (TypeError, RuntimeError):
                pass
            self.script_launcher.close()
            self.script_launcher.deleteLater()

        # Disconnect tray icon signals
        try:
            self.tray_icon.activated.disconnect()
        except Exception:
            pass

        # Hide tray icon
        self.tray_icon.hide()

        # Force final cleanup
        self._perform_aggressive_cleanup()

        logger.info("TrayView cleaned up")
