"""
Script Launcher View - Searchable popup widget for quick script execution.

This view provides a centered popup window with search/filter capabilities
for quickly finding and executing scripts.
"""
import logging
from typing import Dict, Any, List, Optional
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLineEdit, QListWidget,
                              QListWidgetItem, QApplication, QFrame)
from PyQt6.QtCore import Qt, pyqtSignal, QEvent
from PyQt6.QtGui import QKeyEvent

logger = logging.getLogger('Views.ScriptLauncher')


class ScriptLauncherWidget(QWidget):
    """
    Popup widget for searching and launching scripts.

    Features:
    - Search field at top (auto-focused)
    - Filtered list of scripts below
    - Keyboard navigation (arrows, Enter, Esc)
    - Transparent, themed appearance
    """

    # Signals for user actions
    script_execute_requested = pyqtSignal(dict)  # script data
    launcher_closed = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        # Data storage
        self._all_scripts: List[Dict[str, Any]] = []
        self._filtered_scripts: List[Dict[str, Any]] = []
        self._show_hotkeys = True

        # Setup UI
        self._setup_ui()
        self._apply_styling()

        logger.info("ScriptLauncherWidget initialized")

    def _setup_ui(self):
        """Setup the widget UI components"""
        # Configure window
        self.setWindowFlags(
            Qt.WindowType.Popup |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Main widget layout (contains only the container frame)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Container frame for background styling
        self.container_frame = QFrame(self)
        self.container_frame.setObjectName("launcher_container")
        main_layout.addWidget(self.container_frame)

        # Container layout (holds search field and list)
        container_layout = QVBoxLayout(self.container_frame)
        container_layout.setContentsMargins(12, 12, 12, 12)
        container_layout.setSpacing(8)

        # Search field
        self.search_field = QLineEdit(self.container_frame)
        self.search_field.setPlaceholderText("Type to filter scripts...")
        self.search_field.textChanged.connect(self._on_search_changed)
        self.search_field.installEventFilter(self)
        container_layout.addWidget(self.search_field)

        # Script list
        self.script_list = QListWidget(self.container_frame)
        self.script_list.setMinimumWidth(400)
        self.script_list.setMinimumHeight(300)
        self.script_list.itemActivated.connect(self._on_item_activated)
        self.script_list.installEventFilter(self)
        container_layout.addWidget(self.script_list)

        self.setLayout(main_layout)

    def _apply_styling(self):
        """Apply theme-aware styling to the widget"""
        try:
            # Get current theme colors from global stylesheet
            app = QApplication.instance()
            if not app:
                logger.warning("No QApplication instance; cannot apply launcher theme")
                return

            stylesheet = app.styleSheet()
            if not stylesheet:
                logger.warning("No stylesheet available; using default launcher colors")
                self._apply_fallback_styling()
                return

            # Parse colors from stylesheet (similar to tray_view.py)
            import re
            menu_bg_color = None
            menu_border_color = None
            menu_text_color = None
            widget_text_color = None

            # Parse QWidget base text color
            widget_match = re.search(r'QWidget[^{]*\{([^}]+)\}', stylesheet, re.DOTALL)
            if widget_match:
                widget_section = widget_match.group(1)
                # Use negative lookbehind to match 'color:' but not 'background-color:' or 'border-color:'
                widget_color_match = re.search(r'(?<!background-)(?<!border-)color:\s*([#\w]+)', widget_section)
                if widget_color_match:
                    widget_text_color = widget_color_match.group(1)
                    logger.debug(f"Parsed QWidget text color: {widget_text_color}")
                else:
                    logger.debug("No color property found in QWidget section")
            else:
                logger.warning("Could not find QWidget section in stylesheet")

            # Parse QMenu colors
            menu_match = re.search(r'QMenu[^{]*\{([^}]+)\}', stylesheet, re.DOTALL)
            if menu_match:
                menu_section = menu_match.group(1)
                bg_match = re.search(r'background-color:\s*([#\w]+)', menu_section)
                if bg_match:
                    menu_bg_color = bg_match.group(1)
                    logger.debug(f"Parsed QMenu background-color: {menu_bg_color}")
                border_match = re.search(r'border:\s*[^;]*\s+([#\w]+)', menu_section)
                if border_match:
                    menu_border_color = border_match.group(1)
                    logger.debug(f"Parsed QMenu border color: {menu_border_color}")
                # Use negative lookbehind to match 'color:' but not 'background-color:' or 'border-color:'
                color_match = re.search(r'(?<!background-)(?<!border-)color:\s*([#\w]+)', menu_section)
                if color_match:
                    menu_text_color = color_match.group(1)
                    logger.debug(f"Parsed QMenu text color: {menu_text_color}")
                else:
                    logger.debug("No color property in QMenu section (expected, inherits from QWidget)")
            else:
                logger.warning("Could not find QMenu section in stylesheet")

            # Convert hex colors to RGBA with transparency
            def hex_to_rgba(hex_color: str, alpha: float = 0.95) -> str:
                if not hex_color or not hex_color.startswith('#'):
                    logger.debug(f"hex_to_rgba fallback for: {hex_color}")
                    return f"rgba(45, 45, 45, {alpha})"
                hex_color = hex_color.lstrip('#')
                if len(hex_color) == 6:
                    r = int(hex_color[0:2], 16)
                    g = int(hex_color[2:4], 16)
                    b = int(hex_color[4:6], 16)
                    return f"rgba({r}, {g}, {b}, {alpha})"
                logger.debug(f"hex_to_rgba invalid hex length: {hex_color}")
                return f"rgba(45, 45, 45, {alpha})"

            bg_rgba = hex_to_rgba(menu_bg_color, 0.95)
            border_rgba = hex_to_rgba(menu_border_color, 0.3) if menu_border_color else "rgba(255, 255, 255, 0.2)"
            # Use QMenu color if specified, otherwise fall back to QWidget color
            text_color = menu_text_color or widget_text_color or "#E5F5EF"

            logger.info(f"Launcher theme colors - bg: {bg_rgba}, border: {border_rgba}, text: {text_color}")

            # Apply the stylesheet (QFrame#launcher_container gets the background, children get styled with high specificity)
            self.setStyleSheet(f"""
                QFrame#launcher_container {{
                    background-color: {bg_rgba};
                    border: 1px solid {border_rgba};
                    border-radius: 12px;
                }}
                QFrame#launcher_container QLineEdit {{
                    background-color: rgba(255, 255, 255, 0.1);
                    border: 1px solid rgba(255, 255, 255, 0.2);
                    border-radius: 6px;
                    padding: 8px 12px;
                    font-size: 14px;
                    color: {text_color} !important;
                }}
                QFrame#launcher_container QLineEdit:focus {{
                    border: 1px solid rgba(255, 255, 255, 0.4);
                }}
                QFrame#launcher_container QListWidget {{
                    background-color: transparent;
                    border: none;
                    outline: none;
                    color: {text_color} !important;
                }}
                QFrame#launcher_container QListWidget::item {{
                    padding: 10px 12px;
                    border-radius: 6px;
                    margin: 2px 0px;
                    color: {text_color} !important;
                }}
                QFrame#launcher_container QListWidget::item:hover {{
                    background-color: rgba(255, 255, 255, 0.1);
                }}
                QFrame#launcher_container QListWidget::item:selected {{
                    background-color: rgba(255, 255, 255, 0.2);
                }}
            """)
            logger.debug("Launcher stylesheet applied successfully")

        except Exception as exc:
            logger.error(f"Error applying launcher theme: {exc}", exc_info=True)
            self._apply_fallback_styling()

    def _apply_fallback_styling(self):
        """Apply fallback styling when theme parsing fails"""
        logger.info("Applying fallback launcher styling")
        fallback_bg = "rgba(30, 30, 30, 0.95)"  # Dark gray
        fallback_border = "rgba(100, 100, 100, 0.5)"  # Medium gray
        fallback_text = "#E5F5EF"  # Light color guaranteed to be visible

        self.setStyleSheet(f"""
            QFrame#launcher_container {{
                background-color: {fallback_bg};
                border: 1px solid {fallback_border};
                border-radius: 12px;
            }}
            QFrame#launcher_container QLineEdit {{
                background-color: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 14px;
                color: {fallback_text} !important;
            }}
            QFrame#launcher_container QLineEdit:focus {{
                border: 1px solid rgba(255, 255, 255, 0.4);
            }}
            QFrame#launcher_container QListWidget {{
                background-color: transparent;
                border: none;
                outline: none;
                color: {fallback_text} !important;
            }}
            QFrame#launcher_container QListWidget::item {{
                padding: 10px 12px;
                border-radius: 6px;
                margin: 2px 0px;
                color: {fallback_text} !important;
            }}
            QFrame#launcher_container QListWidget::item:hover {{
                background-color: rgba(255, 255, 255, 0.1);
            }}
            QFrame#launcher_container QListWidget::item:selected {{
                background-color: rgba(255, 255, 255, 0.2);
            }}
        """)

    def refresh_theme(self):
        """Reapply theme-sensitive styling"""
        try:
            logger.debug("Refreshing launcher theme...")
            self._apply_styling()
        except Exception as exc:
            logger.error(f"Failed to refresh launcher theme: {exc}", exc_info=True)

    def update_scripts(self, scripts: List[Dict[str, Any]], show_hotkeys: bool = True):
        """
        Update the available scripts and display settings.

        Args:
            scripts: List of script data dictionaries
            show_hotkeys: Whether to display hotkeys next to script names
        """
        self._all_scripts = scripts
        self._show_hotkeys = show_hotkeys
        self._filter_and_display()
        logger.debug(f"Launcher updated with {len(scripts)} scripts")

    def _filter_and_display(self):
        """Filter scripts based on search text and update the display"""
        search_text = self.search_field.text().lower()

        # Filter scripts (case-insensitive, anywhere match)
        if search_text:
            self._filtered_scripts = [
                s for s in self._all_scripts
                if search_text in s.get('name', '').lower()
            ]
        else:
            self._filtered_scripts = self._all_scripts.copy()

        # Update list widget
        self.script_list.clear()
        for script_data in self._filtered_scripts:
            display_text = self._format_script_display(script_data)
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, script_data)
            self.script_list.addItem(item)

        # Auto-select first item if available
        if self.script_list.count() > 0:
            self.script_list.setCurrentRow(0)

    def _format_script_display(self, script_data: Dict[str, Any]) -> str:
        """Format script display text with optional hotkey"""
        name = script_data.get('name', 'Unknown')
        status = script_data.get('status', '')
        is_running = script_data.get('is_running', False)
        hotkey = script_data.get('hotkey', '')

        # Build display text
        if is_running:
            text = f"⏳ {name}"
        elif status and status != "Ready":
            text = f"{name} [{status}]"
        else:
            text = name

        # Add hotkey if enabled and available
        if self._show_hotkeys and hotkey:
            # Calculate padding for alignment (approximate)
            # Use a fixed width for consistency
            padding = max(0, 40 - len(text))
            text = f"{text}{' ' * padding} | {hotkey}"

        return text

    def _on_search_changed(self, text: str):
        """Handle search text changes"""
        self._filter_and_display()

    def _on_item_activated(self, item: QListWidgetItem):
        """Handle item double-click or Enter key"""
        script_data = item.data(Qt.ItemDataRole.UserRole)
        if script_data:
            self._execute_script(script_data)

    def _execute_script(self, script_data: Dict[str, Any]):
        """Execute the selected script and close the launcher"""
        logger.info(f"Executing script from launcher: {script_data.get('name')}")
        self.script_execute_requested.emit(script_data)
        self.close()

    def eventFilter(self, obj, event):
        """Handle keyboard events for navigation"""
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()

            # Esc closes the launcher
            if key == Qt.Key.Key_Escape:
                self.close()
                return True

            # Enter executes selected or first script
            if key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter:
                current_item = self.script_list.currentItem()
                if current_item:
                    self._on_item_activated(current_item)
                elif self.script_list.count() > 0:
                    # Execute first item if none selected
                    self._on_item_activated(self.script_list.item(0))
                return True

            # Arrow keys navigate the list
            if obj == self.search_field and key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                # Transfer focus to list for arrow key navigation
                self.script_list.setFocus()
                # Manually trigger the navigation
                if key == Qt.Key.Key_Down:
                    self.script_list.setCurrentRow(0)
                elif key == Qt.Key.Key_Up:
                    self.script_list.setCurrentRow(self.script_list.count() - 1)
                return True

            # Any other key in the list: return focus to search field
            if obj == self.script_list and event.text().isprintable():
                self.search_field.setFocus()
                self.search_field.insert(event.text())
                return True

        return super().eventFilter(obj, event)

    def showEvent(self, event):
        """Handle show event - focus search field"""
        super().showEvent(event)
        self.search_field.clear()
        self.search_field.setFocus()
        self._filter_and_display()

    def closeEvent(self, event):
        """Handle close event"""
        super().closeEvent(event)
        self.launcher_closed.emit()
        logger.debug("Launcher closed")

    def cleanup(self):
        """Clean up resources"""
        try:
            # Clear data
            self._all_scripts.clear()
            self._filtered_scripts.clear()

            # Clear list widget
            self.script_list.clear()

            # Disconnect signals
            try:
                self.search_field.textChanged.disconnect()
            except (TypeError, RuntimeError):
                pass

            try:
                self.script_list.itemActivated.disconnect()
            except (TypeError, RuntimeError):
                pass

            # Remove event filters
            self.search_field.removeEventFilter(self)
            self.script_list.removeEventFilter(self)

            logger.debug("ScriptLauncherWidget cleaned up")
        except Exception as e:
            logger.error(f"Error during launcher cleanup: {e}")

    def show_at_center(self):
        """Show the launcher centered on the screen"""
        # Get screen geometry
        screen = QApplication.primaryScreen()
        if screen:
            screen_geometry = screen.geometry()

            # Calculate center position
            self.adjustSize()
            widget_size = self.sizeHint()
            x = screen_geometry.x() + (screen_geometry.width() - widget_size.width()) // 2
            y = screen_geometry.y() + (screen_geometry.height() - widget_size.height()) // 2

            self.move(x, y)
            logger.debug(f"Showing launcher at center: ({x}, {y})")

        self.show()
        self.activateWindow()
        self.raise_()
