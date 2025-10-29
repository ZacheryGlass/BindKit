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
        self._hotkey_menu_actions = []  # List to track QAction objects for hotkey menu
        self._hotkey_submenus = []  # List to track QMenu objects for hotkey menu
        self._menu_update_count = 0  # Track updates for periodic cleanup

        # Create tray icon
        self.tray_icon = QSystemTrayIcon(parent)
        self.tray_icon.setToolTip("Desktop Utilities")

        # Create context menu (for tray icon clicks)
        self.context_menu = QMenu(parent)
        self.context_menu.setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
        )

        # Create hotkey menu (for hotkey activation)
        self.hotkey_menu = QMenu(parent)
        self.hotkey_menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.hotkey_menu.setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
        )
        self._apply_hotkey_menu_transparency()

        # Install event filter for ESC key handling on both menus
        self._key_event_filter = MenuKeyEventFilter()
        self.context_menu.installEventFilter(self._key_event_filter)
        self.hotkey_menu.installEventFilter(self._key_event_filter)

        # Create and set icon
        self._create_tray_icon()

        # Connect signals
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.setContextMenu(self.context_menu)
        
        logger.info("TrayView initialized")

    def _apply_hotkey_menu_transparency(self):
        """Apply semi-transparent background to hotkey menu using current theme colors"""
        from PyQt6.QtWidgets import QApplication
        import re

        # Get current theme colors from global stylesheet
        app = QApplication.instance()
        if not app:
            return

        stylesheet = app.styleSheet()

        # Parse QMenu background color from stylesheet
        # Look for patterns like: QMenu { ... background-color: #171A21; ... }
        menu_bg_color = None
        menu_border_color = None

        # Find QMenu section in stylesheet
        menu_match = re.search(r'QMenu[^{]*\{([^}]+)\}', stylesheet, re.DOTALL)
        if menu_match:
            menu_section = menu_match.group(1)

            # Extract background-color
            bg_match = re.search(r'background-color:\s*([#\w]+)', menu_section)
            if bg_match:
                menu_bg_color = bg_match.group(1)

            # Extract border color
            border_match = re.search(r'border:\s*[^;]*\s+([#\w]+)', menu_section)
            if border_match:
                menu_border_color = border_match.group(1)

        # Convert hex colors to RGBA with transparency
        def hex_to_rgba(hex_color: str, alpha: float = 0.85) -> str:
            """Convert hex color to rgba string with specified alpha"""
            if not hex_color or not hex_color.startswith('#'):
                return f"rgba(45, 45, 45, {alpha})"  # fallback

            hex_color = hex_color.lstrip('#')
            if len(hex_color) == 6:
                r = int(hex_color[0:2], 16)
                g = int(hex_color[2:4], 16)
                b = int(hex_color[4:6], 16)
                return f"rgba({r}, {g}, {b}, {alpha})"
            return f"rgba(45, 45, 45, {alpha})"  # fallback

        # Apply theme-aware transparent style
        bg_rgba = hex_to_rgba(menu_bg_color, 0.85)
        border_rgba = hex_to_rgba(menu_border_color, 0.3) if menu_border_color else "rgba(255, 255, 255, 0.2)"

        self.hotkey_menu.setStyleSheet(f"""
            QMenu {{
                background-color: {bg_rgba};
                border: 1px solid {border_rgba};
                border-radius: 12px;
                padding: 8px;
            }}
            QMenu::item {{
                padding: 12px 20px;
                border-radius: 8px;
            }}
            QMenu::separator {{
                height: 1px;
                background: rgba(255, 255, 255, 0.15);
                margin: 8px 16px;
            }}
        """)

    def refresh_theme(self):
        """Reapply theme-sensitive styling for tray menus."""
        try:
            self._apply_hotkey_menu_transparency()
        except Exception as exc:
            logger.debug(f"Failed to refresh tray theme styling: {exc}")

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
        """Show the hotkey menu at the center of the screen"""
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QPoint

        # Get the screen geometry
        screen = QApplication.primaryScreen()
        if screen:
            screen_geometry = screen.geometry()

            # Get menu size hint to calculate proper centering
            menu_size = self.hotkey_menu.sizeHint()

            # Calculate position so menu's center is at screen center
            menu_x = screen_geometry.x() + (screen_geometry.width() - menu_size.width()) // 2
            menu_y = screen_geometry.y() + (screen_geometry.height() - menu_size.height()) // 2
            menu_point = QPoint(menu_x, menu_y)

            # Show hotkey menu centered
            self.hotkey_menu.popup(menu_point)
            logger.debug(f"Hotkey menu centered on screen at: ({menu_x}, {menu_y})")
        else:
            # Fallback to cursor position if screen not available
            self.hotkey_menu.popup(QCursor.pos())
            logger.debug("Hotkey menu shown at cursor position (fallback)")

    def update_menu_structure(self, menu_structure: Dict[str, Any]):
        """Update the menu structure based on provided data"""
        logger.debug("Updating menu structure...")

        try:
            # Perform deep cleanup of existing menu objects
            self._cleanup_menu_objects()

            # Force immediate cleanup to prevent accumulation
            self._force_immediate_cleanup()

            # Clear both menus
            self.context_menu.clear()
            self.hotkey_menu.clear()

            # Reset tracking lists for both menus
            self._menu_actions = []
            self._submenus = []
            self._hotkey_menu_actions = []
            self._hotkey_submenus = []

            # Build both menus with the same structure
            self._build_menu(self.context_menu, self._menu_actions, self._submenus, menu_structure)
            self._build_menu(self.hotkey_menu, self._hotkey_menu_actions, self._hotkey_submenus, menu_structure)

            menu_items = menu_structure.get('items', [])
            logger.debug(f"Both menus updated with {len(menu_items)} items")

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

            # Clean up hotkey menu actions
            for action in self._hotkey_menu_actions:
                if action is None:
                    continue

                try:
                    _ = action.text()
                    try:
                        action.triggered.disconnect()
                    except (TypeError, RuntimeError):
                        pass
                    action.deleteLater()
                except RuntimeError:
                    logger.debug(f"Hotkey menu action already deleted, skipping cleanup")
                    pass

            # Clean up hotkey menu submenus
            for submenu in self._hotkey_submenus:
                submenu.clear()
                submenu.deleteLater()

            # Clear all tracking lists
            self._menu_actions.clear()
            self._submenus.clear()
            self._hotkey_menu_actions.clear()
            self._hotkey_submenus.clear()

            logger.debug("Both menu objects cleaned up")

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

        # Clear both menus
        self.context_menu.clear()
        self.hotkey_menu.clear()
        
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
