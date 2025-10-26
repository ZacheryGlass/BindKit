"""
Settings View - UI component for application settings.

This view provides the settings dialog interface without business logic,
emitting signals for user interactions and updating display based on controller data.
"""
import logging
from typing import Dict, Any, List, Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QCheckBox,
    QLabel, QPushButton, QWidget, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QSpinBox, QComboBox, QListWidget, QListWidgetItem, QMessageBox,
    QFileDialog, QInputDialog, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QAction

logger = logging.getLogger('Views.Settings')


class SettingsView(QDialog):
    """
    View component for application settings dialog.
    
    This view:
    - Displays settings in a tabbed interface
    - Emits signals for user interactions
    - Updates display based on controller data
    - Contains no business logic
    """
    
    # Signals for user interactions
    # Startup settings
    run_on_startup_changed = pyqtSignal(bool)
    start_minimized_changed = pyqtSignal(bool)
    show_startup_notification_changed = pyqtSignal(bool)
    
    # Behavior settings
    minimize_to_tray_changed = pyqtSignal(bool)
    close_to_tray_changed = pyqtSignal(bool)
    single_instance_changed = pyqtSignal(bool)
    show_script_notifications_changed = pyqtSignal(bool)
    
    # Execution settings
    script_timeout_changed = pyqtSignal(int)
    
    # Script management
    script_toggled = pyqtSignal(str, bool)  # script_name, enabled
    hotkey_configuration_requested = pyqtSignal(str)  # script_name
    custom_name_changed = pyqtSignal(str, str)  # script_name, custom_name
    external_script_add_requested = pyqtSignal(str)  # file_path
    external_script_remove_requested = pyqtSignal(str)  # script_name
    
    # Preset management
    add_preset_requested = pyqtSignal(str)  # script_name
    edit_preset_requested = pyqtSignal(str, str)  # script_name, preset_name
    preset_deleted = pyqtSignal(str, str)  # script_name, preset_name
    auto_generate_presets_requested = pyqtSignal(str)  # script_name

    # Schedule management
    schedule_enabled_changed = pyqtSignal(str, bool)  # script_name, enabled
    schedule_interval_changed = pyqtSignal(str, int)  # script_name, interval_seconds
    run_now_requested = pyqtSignal(str)  # script_name

    # Reset operations
    reset_requested = pyqtSignal(str)  # category
    
    # Dialog actions (instant-apply mode: no OK/Cancel buttons)
    
    def __init__(self, parent=None):
        super().__init__(parent)

        # UI components
        self.tab_widget = None
        self.script_table = None
        self.preset_table = None
        self.schedule_view = None
        
        # Checkboxes for settings
        self.run_on_startup_checkbox = None
        self.start_minimized_checkbox = None
        self.show_notification_checkbox = None
        self.minimize_to_tray_checkbox = None
        self.close_to_tray_checkbox = None
        self.single_instance_checkbox = None
        self.show_script_notifications_checkbox = None
        
        # Spinboxes for numeric settings
        self.timeout_spinbox = None
        
        # Track current data
        self._script_data = []
        self._preset_data = {}
        
        self._init_ui()
        
        logger.info("SettingsView initialized")
    
    def _init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("Settings")
        self.setModal(True)
        # Ensure dialog is destroyed when closed to avoid accumulating hidden instances
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setMinimumSize(1100, 650)
        self.resize(1200, 700)  # Set a comfortable default size
        
        layout = QVBoxLayout(self)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # Create tabs
        self._create_general_tab()
        self._create_scripts_tab()
        self._create_schedule_tab()
        self._create_presets_tab()
        self._create_reset_tab()
        
        # Instant-apply: remove OK/Cancel; window can be closed via title bar
    
    def _create_general_tab(self):
        """Create the General settings tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Startup Settings Group
        startup_group = QGroupBox("Startup")
        startup_layout = QVBoxLayout()
        
        self.run_on_startup_checkbox = QCheckBox("Run on system startup")
        self.run_on_startup_checkbox.toggled.connect(self.run_on_startup_changed.emit)
        startup_layout.addWidget(self.run_on_startup_checkbox)
        
        self.start_minimized_checkbox = QCheckBox("Start minimized to tray")
        self.start_minimized_checkbox.toggled.connect(self.start_minimized_changed.emit)
        startup_layout.addWidget(self.start_minimized_checkbox)
        
        self.show_notification_checkbox = QCheckBox("Show notification on startup")
        self.show_notification_checkbox.toggled.connect(self.show_startup_notification_changed.emit)
        startup_layout.addWidget(self.show_notification_checkbox)
        
        startup_group.setLayout(startup_layout)
        layout.addWidget(startup_group)
        
        # Behavior Settings Group
        behavior_group = QGroupBox("Behavior")
        behavior_layout = QVBoxLayout()
        
        self.minimize_to_tray_checkbox = QCheckBox("Minimize to system tray")
        self.minimize_to_tray_checkbox.toggled.connect(self.minimize_to_tray_changed.emit)
        behavior_layout.addWidget(self.minimize_to_tray_checkbox)
        
        self.close_to_tray_checkbox = QCheckBox("Close to system tray instead of exiting")
        self.close_to_tray_checkbox.toggled.connect(self.close_to_tray_changed.emit)
        behavior_layout.addWidget(self.close_to_tray_checkbox)
        
        self.single_instance_checkbox = QCheckBox("Allow only one instance")
        self.single_instance_checkbox.toggled.connect(self.single_instance_changed.emit)
        behavior_layout.addWidget(self.single_instance_checkbox)
        
        self.show_script_notifications_checkbox = QCheckBox("Show script execution notifications")
        self.show_script_notifications_checkbox.toggled.connect(self.show_script_notifications_changed.emit)
        behavior_layout.addWidget(self.show_script_notifications_checkbox)
        
        behavior_group.setLayout(behavior_layout)
        layout.addWidget(behavior_group)
        
        # Execution Settings Group
        execution_group = QGroupBox("Execution")
        execution_layout = QVBoxLayout()
        
        # Script timeout
        timeout_layout = QHBoxLayout()
        timeout_layout.addWidget(QLabel("Script timeout (seconds):"))
        self.timeout_spinbox = QSpinBox()
        self.timeout_spinbox.setMinimum(5)
        self.timeout_spinbox.setMaximum(300)
        self.timeout_spinbox.valueChanged.connect(self.script_timeout_changed.emit)
        timeout_layout.addWidget(self.timeout_spinbox)
        timeout_layout.addStretch()
        execution_layout.addLayout(timeout_layout)
        
        execution_group.setLayout(execution_layout)
        layout.addWidget(execution_group)
        
        layout.addStretch()
        
        self.tab_widget.addTab(tab, "General")
    
    def _create_scripts_tab(self):
        """Create the Scripts management tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Instructions
        instructions = QLabel(
            "Manage scripts: Enable/disable, set hotkeys, customize names, and add external scripts."
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        
        # Scripts table
        self.script_table = QTableWidget()
        self.script_table.setColumnCount(4)
        self.script_table.setHorizontalHeaderLabels([
            "ACTION", "DISPLAY NAME", "FILENAME", "HOTKEY"
        ])
        
        # Configure table
        self.script_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.script_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.script_table.setAlternatingRowColors(True)
        self.script_table.verticalHeader().setVisible(False)  # Hide row numbers
        self.script_table.setShowGrid(True)  # Show grid lines for clarity
        self.script_table.setWordWrap(False)  # Prevent widgets/text from wrapping across columns
        # Ensure readable row height similar to item rows
        vh = self.script_table.verticalHeader()
        try:
            vh.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
            base = max(self.fontMetrics().height() + 8, 28)
            vh.setDefaultSectionSize(base)
            vh.setMinimumSectionSize(24)
        except Exception:
            pass
        
        # Set up proper column sizing
        header = self.script_table.horizontalHeader()
        header.setStretchLastSection(False)  # We control sizes explicitly
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)      # Action button column
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)    # Display name stretches
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)    # Filename stretches (balanced)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)      # Hotkey - fixed width
        
        # Set proper column widths to prevent truncation and overlapping
        self.script_table.setColumnWidth(0, 110)   # ACTION - button width
        self.script_table.setColumnWidth(3, 200)   # HOTKEY - show full hotkeys

        # Provide initial proportions for stretch columns
        try:
            header.resizeSection(1, 280)  # Display name
            header.resizeSection(2, 240)  # Filename
        except Exception:
            pass
        
        layout.addWidget(self.script_table)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        add_external_btn = QPushButton("Add External Script...")
        add_external_btn.clicked.connect(self._on_add_external_script)
        button_layout.addWidget(add_external_btn)
        
        button_layout.addStretch()
        
        # Instant-apply: remove explicit Refresh button; view updates via signals
        
        layout.addLayout(button_layout)
        
        self.tab_widget.addTab(tab, "Scripts")
    
    def _create_presets_tab(self):
        """Create the Script Presets/Arguments tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Instructions
        instructions = QLabel(
            "Configure preset arguments for scripts that accept parameters."
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        
        # Script selection
        script_layout = QHBoxLayout()
        script_layout.addWidget(QLabel("Script:"))
        
        self.preset_script_combo = QComboBox()
        self.preset_script_combo.currentTextChanged.connect(self._on_preset_script_changed)
        script_layout.addWidget(self.preset_script_combo)
        
        script_layout.addStretch()
        layout.addLayout(script_layout)
        
        # Presets table (styled like Scripts tab)
        self.preset_table = QTableWidget()
        self.preset_table.setColumnCount(3)
        self.preset_table.setHorizontalHeaderLabels([
            "ACTION", "PRESET NAME", "ARGUMENTS"
        ])

        # Configure table for consistent look
        self.preset_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.preset_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.preset_table.setAlternatingRowColors(True)
        self.preset_table.verticalHeader().setVisible(False)
        self.preset_table.setShowGrid(True)
        self.preset_table.setWordWrap(False)
        # Ensure readable row height similar to item rows
        p_vh = self.preset_table.verticalHeader()
        try:
            p_vh.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
            p_base = max(self.fontMetrics().height() + 8, 28)
            p_vh.setDefaultSectionSize(p_base)
            p_vh.setMinimumSectionSize(24)
        except Exception:
            pass

        # Column sizing similar to Scripts tab
        p_header = self.preset_table.horizontalHeader()
        p_header.setStretchLastSection(False)
        p_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)    # ACTION
        p_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # PRESET NAME
        p_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # ARGUMENTS
        self.preset_table.setColumnWidth(0, 160)  # Room for Edit/Delete buttons
        try:
            p_header.resizeSection(1, 240)
            p_header.resizeSection(2, 420)
        except Exception:
            pass

        # Double-click to edit preset
        self.preset_table.cellDoubleClicked.connect(lambda r, c: self._on_edit_preset())

        layout.addWidget(self.preset_table)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        add_preset_btn = QPushButton("Add Preset...")
        add_preset_btn.setToolTip("Create a new preset for this script")
        add_preset_btn.clicked.connect(self._on_add_preset)
        button_layout.addWidget(add_preset_btn)
        
        button_layout.addStretch()

        auto_generate_btn = QPushButton("Auto-Generate")
        auto_generate_btn.clicked.connect(self._on_auto_generate_presets)
        auto_generate_btn.setToolTip("Automatically generate presets from script arguments")
        button_layout.addWidget(auto_generate_btn)
        
        layout.addLayout(button_layout)
        
        self.tab_widget.addTab(tab, "Presets")

    def _create_schedule_tab(self):
        """Create the Schedule configuration tab"""
        from views.schedule_view import ScheduleView

        # Create ScheduleView instance
        self.schedule_view = ScheduleView()

        # Connect ScheduleView signals to SettingsView signals (passthrough)
        self.schedule_view.schedule_enabled_changed.connect(self.schedule_enabled_changed.emit)
        self.schedule_view.schedule_interval_changed.connect(self.schedule_interval_changed.emit)
        self.schedule_view.run_now_requested.connect(self.run_now_requested.emit)

        # Add tab
        self.tab_widget.addTab(self.schedule_view, "Schedule")

    def select_presets_tab(self):
        """Switch to the Presets tab."""
        try:
            for i in range(self.tab_widget.count()):
                if self.tab_widget.tabText(i) == "Presets":
                    self.tab_widget.setCurrentIndex(i)
                    break
        except Exception:
            pass
    
    def _create_reset_tab(self):
        """Create the Reset settings tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Warning
        warning = QLabel(
            "âš ï¸ Warning: Reset operations cannot be undone!\n\n"
            "Choose what you want to reset:"
        )
        warning.setStyleSheet("color: orange;")
        layout.addWidget(warning)
        # Ensure clean ASCII text in case of encoding glitches in literals
        warning.setText(
            "Warning: Reset operations cannot be undone!\n\n"
            "Choose what you want to reset:"
        )
        
        # Reset buttons
        reset_all_btn = QPushButton("Reset All Settings to Defaults")
        reset_all_btn.clicked.connect(lambda: self._on_reset('all'))
        layout.addWidget(reset_all_btn)
        
        reset_hotkeys_btn = QPushButton("Clear All Hotkeys")
        reset_hotkeys_btn.clicked.connect(lambda: self._on_reset('hotkeys'))
        layout.addWidget(reset_hotkeys_btn)
        
        reset_presets_btn = QPushButton("Clear All Presets")
        reset_presets_btn.clicked.connect(lambda: self._on_reset('presets'))
        layout.addWidget(reset_presets_btn)
        
        reset_names_btn = QPushButton("Clear All Custom Names")
        reset_names_btn.clicked.connect(lambda: self._on_reset('custom_names'))
        layout.addWidget(reset_names_btn)
        
        layout.addStretch()
        
        self.tab_widget.addTab(tab, "Reset")
    
    # Update slots (called by controller)
    def update_startup_settings(self, settings: Dict[str, Any]):
        """Update startup settings display"""
        self.run_on_startup_checkbox.setChecked(settings.get('run_on_startup', False))
        self.start_minimized_checkbox.setChecked(settings.get('start_minimized', True))
        self.show_notification_checkbox.setChecked(settings.get('show_notification', True))
    
    def update_behavior_settings(self, settings: Dict[str, Any]):
        """Update behavior settings display"""
        self.minimize_to_tray_checkbox.setChecked(settings.get('minimize_to_tray', True))
        self.close_to_tray_checkbox.setChecked(settings.get('close_to_tray', True))
        self.single_instance_checkbox.setChecked(settings.get('single_instance', True))
        self.show_script_notifications_checkbox.setChecked(
            settings.get('show_script_notifications', True)
        )
    
    def update_execution_settings(self, settings: Dict[str, Any]):
        """Update execution settings display"""
        self.timeout_spinbox.setValue(settings.get('script_timeout_seconds', 30))
    
    def update_script_list(self, scripts: List[Dict[str, Any]]):
        """Update the scripts table"""
        self._script_data = scripts
        self._refresh_script_table()
        self._update_preset_script_combo()
        self.set_schedule_scripts(scripts)  # Update Schedule tab with new script list

    def update_script_hotkey(self, script_name: str, hotkey: str):
        """Update only the hotkey UI for a specific script.

        script_name is the file stem identifier (matches script dict 'name').
        """
        # Find the script row
        row_index = -1
        for i, script in enumerate(self._script_data):
            if script.get('name') == script_name:
                row_index = i
                # update backing data
                script['hotkey'] = hotkey
                break

        if row_index < 0:
            # Script not found in current view; nothing to update
            return

        # Update the HOTKEY cell's button text and tooltip
        widget = self.script_table.cellWidget(row_index, 3)
        btn = None
        # Support either direct QPushButton or a container with a child button
        if isinstance(widget, QPushButton):
            btn = widget
        elif widget is not None:
            try:
                btn = widget.findChild(QPushButton)
            except Exception:
                btn = None
        if isinstance(btn, QPushButton):
            new_text = hotkey if hotkey else 'Click to set'
            btn.setText(new_text)
            if hotkey:
                btn.setToolTip(f"Current hotkey: {hotkey}\nClick to change")
            else:
                btn.setToolTip("No hotkey set. Click to change")

    def update_preset_list(self, script_name: str, presets: Dict[str, Any]):
        """Update the preset list for a script"""
        self._preset_data[script_name] = presets
        
        # If this is the currently selected script, update the list
        if self.preset_script_combo.currentText() == script_name:
            self._refresh_preset_table(presets)

    def set_all_presets(self, all_presets: Dict[str, Dict[str, Any]]):
        """Replace all preset data and refresh the presets tab."""
        self._preset_data = all_presets or {}
        self._update_preset_script_combo()
        current = self.preset_script_combo.currentText()
        if current and current in self._preset_data:
            self._refresh_preset_table(self._preset_data[current])
        else:
            # Clear table when nothing selected
            self._refresh_preset_table({})
    
    def show_error(self, title: str, message: str):
        """Show an error message"""
        QMessageBox.critical(self, title, message)
    
    def show_info(self, title: str, message: str):
        """Show an information message"""
        QMessageBox.information(self, title, message)
    
    # Internal UI update methods
    def _refresh_script_table(self):
        """Refresh the scripts table display"""
        # Reset table contents fully to avoid leftover widgets
        self.script_table.clearContents()
        self.script_table.setRowCount(len(self._script_data))
        
        for row, script in enumerate(self._script_data):
            # Action button (disable or remove) - column 0
            action_btn = QPushButton()
            action_btn.setStyleSheet(
                "QPushButton { background: transparent; border: none; border-radius: 0; padding: 2px 12px; margin: 0; text-align: left; }"
                "QPushButton:hover { background: transparent; }"
                "QPushButton:pressed { background: transparent; }"
                "QPushButton:disabled { background: transparent; color: #6E6F78; }"
            )
            try:
                from PyQt6.QtWidgets import QSizePolicy
                action_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            except Exception:
                pass
            try:
                # Constrain height to row size
                row_h = self.script_table.verticalHeader().defaultSectionSize()
                action_btn.setMaximumHeight(int(row_h))
                action_btn.setMinimumHeight(0)
                action_btn.setContentsMargins(0, 0, 0, 0)
            except Exception:
                pass
            action_btn.setCursor(Qt.CursorShape.PointingHandCursor)

            # Use defensive key access to prevent KeyError if display_name is missing
            name_key = script.get('original_display_name') or script.get('display_name', '')
            if script.get('is_external', False):
                # External: Remove script
                action_btn.setText("Remove")
                action_btn.setToolTip(f"Remove external script: {script.get('display_name', 'Unknown')}")
                action_btn.clicked.connect(
                    lambda checked, s=name_key: self._on_action_clicked(s, is_external=True)
                )
            else:
                # Built-in: Toggle disable/enable (determine current state at click time)
                is_disabled = script.get('is_disabled', False)
                action_btn.setText("Enable" if is_disabled else "Disable")
                action_btn.setToolTip("Enable this script" if is_disabled else "Disable this script")
                action_btn.clicked.connect(
                    lambda checked, s=name_key: self._on_action_clicked(s, is_external=False)
                )
            # Make the entire cell act as the button (fills cell, no rounded edges)
            self.script_table.setCellWidget(row, 0, action_btn)

            # Display Name (customizable) - column 1
            custom_name = script.get('custom_name', '')
            custom_btn_text = custom_name if custom_name else 'Click to set'
            custom_name_btn = QPushButton(custom_btn_text)
            custom_name_btn.setStyleSheet(
                "QPushButton { background: transparent; border: none; border-radius: 0; padding: 2px 12px; margin: 0; text-align: left; }"
                "QPushButton:hover { background: transparent; }"
                "QPushButton:pressed { background: transparent; }"
                "QPushButton:disabled { background: transparent; color: #6E6F78; }"
            )
            try:
                from PyQt6.QtWidgets import QSizePolicy
                custom_name_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            except Exception:
                pass
            try:
                row_h = self.script_table.verticalHeader().defaultSectionSize()
                custom_name_btn.setMaximumHeight(int(row_h))
                custom_name_btn.setMinimumHeight(0)
                custom_name_btn.setContentsMargins(0, 0, 0, 0)
            except Exception:
                pass
            custom_name_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            custom_name_btn.setToolTip(
                f"Custom name: {custom_name}" if custom_name else "Click to set a custom display name"
            )
            custom_name_btn.clicked.connect(
                lambda checked, s=script['name']: self._on_set_custom_name(s)
            )
            # Make the entire cell act as the button (fills cell, no rounded edges)
            self.script_table.setCellWidget(row, 1, custom_name_btn)

            # Filename (explicitly show the underlying file name) - column 2
            file_name = script.get('file_path')
            try:
                from pathlib import Path
                display_file = Path(file_name).name if file_name else script.get('name', '')
            except Exception:
                display_file = script.get('name', '')
            file_item = QTableWidgetItem(display_file)
            file_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            # Tooltip shows full path and current display name for clarity
            tooltip_parts = []
            if file_name:
                tooltip_parts.append(f"Path: {file_name}")
            if script.get('display_name'):
                tooltip_parts.append(f"Display: {script['display_name']}")
            if tooltip_parts:
                file_item.setToolTip("\n".join(tooltip_parts))
            self.script_table.setItem(row, 2, file_item)
            
            # Hotkey - show full hotkey text with proper sizing
            raw_hotkey = script.get('hotkey', '')
            hotkey_text = raw_hotkey if raw_hotkey else 'Click to set'
            hotkey_btn = QPushButton(hotkey_text)
            hotkey_btn.setStyleSheet(
                "QPushButton { background: transparent; border: none; border-radius: 0; padding: 2px 12px; margin: 0; text-align: left; }"
                "QPushButton:hover { background: transparent; }"
                "QPushButton:pressed { background: transparent; }"
                "QPushButton:disabled { background: transparent; color: #6E6F78; }"
            )
            try:
                from PyQt6.QtWidgets import QSizePolicy
                hotkey_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            except Exception:
                pass
            try:
                row_h = self.script_table.verticalHeader().defaultSectionSize()
                hotkey_btn.setMaximumHeight(int(row_h))
                hotkey_btn.setMinimumHeight(0)
                hotkey_btn.setContentsMargins(0, 0, 0, 0)
            except Exception:
                pass
            hotkey_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if raw_hotkey:
                hotkey_btn.setToolTip(f"Current hotkey: {raw_hotkey}\nClick to change")
            else:
                hotkey_btn.setToolTip("No hotkey set. Click to change")
            hotkey_btn.clicked.connect(
                lambda checked, s=script['name']: self.hotkey_configuration_requested.emit(s)
            )
            # Make the entire cell act as the button (fills cell, no rounded edges)
            self.script_table.setCellWidget(row, 3, hotkey_btn)
        
        # Normalize row heights based on header default
        try:
            vh = self.script_table.verticalHeader()
            desired = max(vh.minimumSectionSize(), int(vh.defaultSectionSize()))
            for r in range(self.script_table.rowCount()):
                self.script_table.setRowHeight(r, desired)
        except Exception:
            pass

        # Apply disabled styling for built-in scripts
        for row, script in enumerate(self._script_data):
            self._apply_row_disabled_style(row, script.get('is_disabled', False))

    def _apply_row_disabled_style(self, row: int, disabled: bool):
        """Gray out and disable interactive widgets for disabled scripts (built-in only)."""
        # Action button stays enabled (to allow re-enabling)
        # Display name button
        display_btn = self.script_table.cellWidget(row, 1)
        if isinstance(display_btn, QPushButton):
            display_btn.setEnabled(not disabled)
        # Filename item
        file_item = self.script_table.item(row, 2)
        if isinstance(file_item, QTableWidgetItem):
            file_item.setForeground(Qt.GlobalColor.gray if disabled else Qt.GlobalColor.black)
        # Hotkey button
        hotkey_btn = self.script_table.cellWidget(row, 3)
        if isinstance(hotkey_btn, QPushButton):
            hotkey_btn.setEnabled(not disabled)

    def _on_action_clicked(self, name_key: str, is_external: bool):
        """Handle the action button: remove external or toggle built-in enable/disable."""
        if is_external:
            self.external_script_remove_requested.emit(name_key)
            return
        # Built-in: look up current disabled state and toggle
        current = None
        for s in self._script_data:
            if s.get('original_display_name', s.get('display_name')) == name_key:
                current = s
                break
        current_disabled = bool(current.get('is_disabled', False)) if current else False
        # Clicking toggles disabled state; enabled value equals current disabled state
        # If currently disabled -> enable (True); if enabled -> disable (False)
        self.script_toggled.emit(name_key, current_disabled)
    
    def _update_preset_script_combo(self):
        """Update the script combo box in presets tab"""
        current = self.preset_script_combo.currentText()
        self.preset_script_combo.clear()
        
        # Add scripts that have arguments
        for script in self._script_data:
            if script.get('has_arguments'):
                self.preset_script_combo.addItem(script['display_name'])
        
        # Try to restore selection
        if current:
            index = self.preset_script_combo.findText(current)
            if index >= 0:
                self.preset_script_combo.setCurrentIndex(index)
    
    def _refresh_preset_table(self, presets: Dict[str, Any]):
        """Refresh the presets table display to mirror Scripts tab styling."""
        # Normalize None to empty dict
        presets = presets or {}

        # Reset contents
        self.preset_table.clearContents()
        rows = len(presets)
        self.preset_table.setRowCount(rows)

        # Stable ordering by preset name
        for row, preset_name in enumerate(sorted(presets.keys(), key=lambda s: s.lower())):
            args = presets.get(preset_name, {}) or {}

            # ACTIONS cell: Edit + Delete buttons
            actions_widget = QWidget()
            try:
                actions_widget.setStyleSheet("background: transparent; border: none; margin: 0; padding: 0;")
            except Exception:
                pass
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(0, 0, 0, 0)
            actions_layout.setSpacing(0)
            try:
                actions_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            except Exception:
                pass

            edit_btn = QPushButton("Edit")
            edit_btn.setFlat(True)
            edit_btn.setStyleSheet(
                "QPushButton { border: none; border-radius: 0; padding: 0px 12px; margin: 0; background: transparent; }"
                "QPushButton:hover { background-color: #5A5B64; }"
            )
            try:
                from PyQt6.QtWidgets import QSizePolicy
                edit_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            except Exception:
                pass
            try:
                row_h = self.preset_table.verticalHeader().defaultSectionSize()
                edit_btn.setMaximumHeight(int(row_h))
                edit_btn.setMinimumHeight(0)
                edit_btn.setContentsMargins(0, 0, 0, 0)
            except Exception:
                pass
            edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            edit_btn.setToolTip(f"Edit preset '{preset_name}'")
            edit_btn.clicked.connect(lambda checked=False, p=preset_name: self._on_edit_preset_named(p))
            actions_layout.addWidget(edit_btn)

            del_btn = QPushButton("Delete")
            del_btn.setFlat(True)
            del_btn.setStyleSheet(
                "QPushButton { border: none; border-radius: 0; padding: 0px 12px; margin: 0; background: transparent; }"
                "QPushButton:hover { background-color: #5A5B64; }"
            )
            try:
                from PyQt6.QtWidgets import QSizePolicy
                del_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            except Exception:
                pass
            try:
                row_h = self.preset_table.verticalHeader().defaultSectionSize()
                del_btn.setMaximumHeight(int(row_h))
                del_btn.setMinimumHeight(0)
                del_btn.setContentsMargins(0, 0, 0, 0)
            except Exception:
                pass
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_btn.setToolTip(f"Delete preset '{preset_name}'")
            del_btn.clicked.connect(lambda checked=False, p=preset_name: self._on_delete_preset_named(p))
            actions_layout.addWidget(del_btn)
            # No stretch; both buttons fill the entire cell horizontally and vertically
            self.preset_table.setCellWidget(row, 0, actions_widget)

            # PRESET NAME cell
            name_item = QTableWidgetItem(preset_name)
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            name_item.setToolTip(f"Preset: {preset_name}")
            # Store raw preset name for retrieval
            name_item.setData(Qt.ItemDataRole.UserRole, preset_name)
            self.preset_table.setItem(row, 1, name_item)

            # ARGUMENTS cell (compact, tooltip shows full list)
            args_pairs = [f"{k}={v}" for k, v in args.items()]
            args_str = ", ".join(args_pairs)
            args_item = QTableWidgetItem(args_str)
            args_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            if args_pairs:
                args_item.setToolTip("\n".join(args_pairs))
            self.preset_table.setItem(row, 2, args_item)

        # Normalize row heights based on header default
        try:
            p_vh = self.preset_table.verticalHeader()
            p_desired = max(p_vh.minimumSectionSize(), int(p_vh.defaultSectionSize()))
            for r in range(self.preset_table.rowCount()):
                self.preset_table.setRowHeight(r, p_desired)
        except Exception:
            pass
    
    # UI event handlers
    
    def _on_add_external_script(self):
        """Handle add external script button"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Python Script",
            "",
            "Python Scripts (*.py)"
        )
        
        if file_path:
            # Emit signal with file path
            self.external_script_add_requested.emit(file_path)
    
    def _on_set_custom_name(self, script_name: str):
        """Handle set custom name button"""
        current_name = next(
            (s.get('custom_name') for s in self._script_data if s['name'] == script_name),
            script_name
        )
        
        new_name, ok = QInputDialog.getText(
            self,
            "Custom Name",
            f"Enter custom name for {script_name}:",
            text=current_name
        )
        
        if ok:
            self.custom_name_changed.emit(script_name, new_name)
    
    def _on_preset_script_changed(self, script_name: str):
        """Handle preset script selection change"""
        if script_name and script_name in self._preset_data:
            self._refresh_preset_table(self._preset_data[script_name])
        else:
            self._refresh_preset_table({})
    
    def _on_add_preset(self):
        """Handle add preset button"""
        script_name = self.preset_script_combo.currentText()
        if script_name:
            self.add_preset_requested.emit(script_name)
    
    def _on_edit_preset(self):
        """Handle edit preset button"""
        # Prefer selected row; fallback to first row
        row = self.preset_table.currentRow()
        if row < 0 and self.preset_table.rowCount() > 0:
            row = 0
        if row >= 0:
            name_item = self.preset_table.item(row, 1)
            if isinstance(name_item, QTableWidgetItem):
                preset_name = name_item.data(Qt.ItemDataRole.UserRole) or name_item.text()
                script_name = self.preset_script_combo.currentText()
                self.edit_preset_requested.emit(script_name, preset_name)
    
    def _on_delete_preset(self):
        """Handle delete preset button"""
        # Delete the currently selected preset
        row = self.preset_table.currentRow()
        if row < 0 and self.preset_table.rowCount() > 0:
            row = 0
        if row >= 0:
            name_item = self.preset_table.item(row, 1)
            if isinstance(name_item, QTableWidgetItem):
                preset_name = name_item.data(Qt.ItemDataRole.UserRole) or name_item.text()
                script_name = self.preset_script_combo.currentText()
                
                reply = QMessageBox.question(
                    self,
                    "Delete Preset",
                    f"Delete preset '{preset_name}'?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    self.preset_deleted.emit(script_name, preset_name)

    # Named action helpers for per-row buttons
    def _on_edit_preset_named(self, preset_name: str):
        """Handle edit preset request with validation."""
        try:
            script_name = self.preset_script_combo.currentText()
            if not (script_name and preset_name):
                logger.warning(f"Edit preset called with invalid data: script='{script_name}', preset='{preset_name}'")
                return

            # Validate preset still exists
            if script_name not in self._preset_data or preset_name not in self._preset_data[script_name]:
                logger.warning(f"Preset '{preset_name}' not found in preset data for script '{script_name}'")
                return

            self.edit_preset_requested.emit(script_name, preset_name)
        except Exception as e:
            logger.error(f"Error handling edit preset request: {e}")

    def _on_delete_preset_named(self, preset_name: str):
        """Handle delete preset request with validation."""
        try:
            script_name = self.preset_script_combo.currentText()
            if not (script_name and preset_name):
                logger.warning(f"Delete preset called with invalid data: script='{script_name}', preset='{preset_name}'")
                return

            # Validate preset still exists
            if script_name not in self._preset_data or preset_name not in self._preset_data[script_name]:
                logger.warning(f"Preset '{preset_name}' not found in preset data for script '{script_name}'")
                return

            reply = QMessageBox.question(
                self,
                "Delete Preset",
                f"Delete preset '{preset_name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.preset_deleted.emit(script_name, preset_name)
        except Exception as e:
            logger.error(f"Error handling delete preset request: {e}")
    
    def _on_auto_generate_presets(self):
        """Handle auto-generate presets button"""
        script_name = self.preset_script_combo.currentText()
        if script_name:
            self.auto_generate_presets_requested.emit(script_name)
    
    def _on_reset(self, category: str):
        """Handle reset button"""
        message = {
            'all': "This will reset ALL settings to defaults.",
            'hotkeys': "This will clear all hotkey assignments.",
            'presets': "This will delete all script presets.",
            'custom_names': "This will clear all custom script names."
        }.get(category, "This operation cannot be undone.")
        
        reply = QMessageBox.warning(
            self,
            "Confirm Reset",
            f"{message}\n\nAre you sure you want to continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.reset_requested.emit(category)

    # Schedule tab helper methods
    def set_schedule_scripts(self, scripts: List[dict]):
        """Set the list of available scripts for scheduling.

        Args:
            scripts: List of dicts with keys: name, display_name
        """
        if self.schedule_view:
            self.schedule_view.set_available_scripts(scripts)

    def update_schedule_info(self, script_name: str, schedule_info: dict):
        """Update schedule information for a specific script.

        Called by controller when schedule state changes.

        Args:
            script_name: Name of the script (display name)
            schedule_info: Dictionary with keys: enabled, interval_seconds, last_run, next_run, status
        """
        if self.schedule_view:
            self.schedule_view.update_schedule_info(script_name, schedule_info)

    def select_schedule_tab(self):
        """Select the Schedule tab programmatically"""
        if self.schedule_view:
            for i in range(self.tab_widget.count()):
                if self.tab_widget.widget(i) == self.schedule_view:
                    self.tab_widget.setCurrentIndex(i)
                    break
