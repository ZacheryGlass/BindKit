"""
Schedule View - UI component for configuring scheduled script execution.

Provides interface for:
- Enabling/disabling schedules per-script
- Setting execution intervals
- Viewing last run and next scheduled run times
- Manual execution trigger for testing
"""

import logging
from typing import List, Optional, Dict
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QPushButton,
    QSpinBox, QComboBox, QGroupBox, QMessageBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QBrush

logger = logging.getLogger('Views.ScheduleView')


class ScheduleView(QWidget):
    """
    UI for configuring scheduled script execution.

    Signals:
    - schedule_enabled_changed: Emitted when enabling/disabling a schedule
    - schedule_interval_changed: Emitted when interval is changed
    - run_now_requested: Emitted when "Run Now" button is clicked
    - schedule_info_requested: Emitted when schedule info should be fetched for a script
    """

    schedule_enabled_changed = pyqtSignal(str, bool)  # script_name, enabled
    schedule_interval_changed = pyqtSignal(str, int)  # script_name, interval_seconds
    run_now_requested = pyqtSignal(str)  # script_name
    schedule_info_requested = pyqtSignal(str)  # script_name

    def __init__(self, parent=None):
        """Initialize the schedule view."""
        super().__init__(parent)
        self.selected_script = None
        self.script_list = []
        self._display_name_map: Dict[str, str] = {}
        self._schedule_data: Dict[str, dict] = {}
        self._row_lookup: Dict[str, int] = {}
        self._next_run_timestamp: Optional[float] = None

        # Timer for periodic refresh of "Next run" display
        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self._refresh_next_run_display)

        self._setup_ui()

    def _setup_ui(self):
        """Set up the UI layout."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Schedule Controls at top
        controls_group = QGroupBox("Schedule Controls")
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(8, 8, 8, 8)

        # Enable checkbox
        self.schedule_enabled_checkbox = QCheckBox("Enable schedule")
        self.schedule_enabled_checkbox.stateChanged.connect(self._on_schedule_enabled_changed)
        self.schedule_enabled_checkbox.setEnabled(False)
        controls_layout.addWidget(self.schedule_enabled_checkbox)

        # Interval controls
        controls_layout.addWidget(QLabel("Interval:"))
        self.interval_spinbox = QSpinBox()
        self.interval_spinbox.setMinimum(1)
        self.interval_spinbox.setMaximum(999999)
        self.interval_spinbox.setValue(60)
        self.interval_spinbox.valueChanged.connect(self._on_interval_changed)
        self.interval_spinbox.setEnabled(False)
        controls_layout.addWidget(self.interval_spinbox)

        self.interval_unit_combo = QComboBox()
        self.interval_unit_combo.addItems(["seconds", "minutes", "hours", "days"])
        self.interval_unit_combo.setCurrentText("minutes")
        self.interval_unit_combo.currentTextChanged.connect(self._on_interval_unit_changed)
        self.interval_unit_combo.setEnabled(False)
        controls_layout.addWidget(self.interval_unit_combo)

        controls_layout.addStretch()

        # Run Now button
        self.run_now_button = QPushButton("Run Now")
        self.run_now_button.clicked.connect(self._on_run_now_clicked)
        self.run_now_button.setEnabled(False)
        controls_layout.addWidget(self.run_now_button)

        controls_group.setLayout(controls_layout)
        layout.addWidget(controls_group)

        # Scheduled Scripts Table (full width)
        table_label = QLabel("Scheduled Scripts")
        table_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(table_label)

        self.schedule_table = QTableWidget(0, 5)
        self.schedule_table.setHorizontalHeaderLabels([
            "Script", "Schedule", "Interval", "Last run", "Next run"
        ])
        self.schedule_table.verticalHeader().setVisible(False)
        self.schedule_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.schedule_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.schedule_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.schedule_table.setAlternatingRowColors(True)
        self.schedule_table.itemSelectionChanged.connect(self._on_table_selection_changed)
        self.schedule_table.cellClicked.connect(self._on_table_cell_clicked)

        header = self.schedule_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 5):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(self.schedule_table)

    def set_available_scripts(self, scripts: List[dict]):
        """
        Set the list of available scripts.

        Args:
            scripts: List of script info dicts with keys: name, display_name
        """
        scripts = scripts or []
        scripts = sorted(scripts, key=lambda s: (s.get('display_name') or s.get('name') or '').lower())
        self.script_list = scripts
        self._display_name_map = {
            script.get('name'): script.get('display_name')
            or script.get('original_display_name')
            or script.get('name', '')
            for script in self.script_list
        }

        valid_names = {script.get('name') for script in self.script_list}
        self._schedule_data = {
            name: data for name, data in self._schedule_data.items() if name in valid_names
        }

        self.schedule_table.blockSignals(True)
        self.schedule_table.clearContents()
        self.schedule_table.setRowCount(len(self.script_list))
        self._row_lookup.clear()

        for row, script in enumerate(self.script_list):
            script_name = script.get('name', '')
            self._row_lookup[script_name] = row
            self._populate_row_base(row, script)
            self._update_table_row(script_name)

        self.schedule_table.blockSignals(False)
        self.schedule_table.clearSelection()
        self.selected_script = None
        self._update_config_panel(None)

    def _populate_row_base(self, row: int, script: dict):
        """Populate a table row with basic script information."""
        script_name = script.get('name', '')
        display_name = self._display_name_map.get(script_name, script_name)
        script_item = self._create_table_item(
            display_name,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )
        script_item.setData(Qt.ItemDataRole.UserRole, script_name)
        tooltip_parts = [f"Identifier: {script_name}"]
        file_path = script.get('file_path')
        if file_path:
            tooltip_parts.append(file_path)
        script_item.setToolTip("\n".join(tooltip_parts))
        self.schedule_table.setItem(row, 0, script_item)

        for column, alignment in [
            (1, Qt.AlignmentFlag.AlignCenter),
            (2, Qt.AlignmentFlag.AlignCenter),
            (3, Qt.AlignmentFlag.AlignLeft),
            (4, Qt.AlignmentFlag.AlignLeft)
        ]:
            item = self._create_table_item("-", alignment)
            self.schedule_table.setItem(row, column, item)

    def _create_table_item(self, text: str, alignment: Qt.AlignmentFlag) -> QTableWidgetItem:
        """Create a table item with the specified text and alignment."""
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        item.setTextAlignment(alignment | Qt.AlignmentFlag.AlignVCenter)
        return item

    def _ensure_table_item(self, row: int, column: int, alignment: Qt.AlignmentFlag) -> QTableWidgetItem:
        """Ensure a table item exists at the specified row and column."""
        item = self.schedule_table.item(row, column)
        if not item:
            item = self._create_table_item('', alignment)
            self.schedule_table.setItem(row, column, item)
        item.setTextAlignment(alignment | Qt.AlignmentFlag.AlignVCenter)
        return item

    def _update_table_row(self, script_name: str):
        """Update a table row with current schedule data."""
        row = self._row_lookup.get(script_name)
        if row is None:
            return
        data = self._schedule_data.get(script_name, {})

        schedule_item = self._ensure_table_item(row, 1, Qt.AlignmentFlag.AlignCenter)
        enabled = data.get('enabled', False)
        schedule_item.setText('On' if enabled else 'Off')
        schedule_item.setForeground(QBrush(QColor('#1f7a4a' if enabled else '#6e6f78')))
        schedule_item.setToolTip('Click to toggle schedule on/off')

        interval_item = self._ensure_table_item(row, 2, Qt.AlignmentFlag.AlignCenter)
        if enabled:
            interval_item.setText(
                data.get('interval_display') or self._format_interval_display(data.get('interval_seconds'))
            )
        else:
            interval_item.setText('-')

        last_run_item = self._ensure_table_item(row, 3, Qt.AlignmentFlag.AlignLeft)
        if data.get('last_run'):
            last_run_item.setText(self._format_timestamp(data['last_run']))
        else:
            last_run_item.setText('Never')

        next_run_item = self._ensure_table_item(row, 4, Qt.AlignmentFlag.AlignLeft)
        if data.get('next_run'):
            next_run_item.setText(self._format_timestamp(data['next_run']))
        else:
            next_run_item.setText('Not scheduled')

    @staticmethod
    def _format_interval_display(interval_seconds: Optional[int]) -> str:
        """Format interval in seconds to human-readable string."""
        if not interval_seconds:
            return "-"
        if interval_seconds < 60:
            return f"{interval_seconds} sec"
        if interval_seconds < 3600:
            minutes = interval_seconds // 60
            return f"{minutes} min"
        if interval_seconds < 86400:
            hours = interval_seconds // 3600
            return f"{hours} hr"
        days = interval_seconds // 86400
        return f"{days} day" + ("s" if days != 1 else "")

    def _format_timestamp(self, timestamp: float) -> str:
        """Format timestamp to readable string."""
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime('%Y-%m-%d %H:%M:%S')

    def _get_display_name(self, script_name: str) -> str:
        """Get display name for a script."""
        return self._display_name_map.get(script_name, script_name)

    def set_schedule_enabled(self, enabled: bool):
        """Set the schedule enabled checkbox state."""
        self.schedule_enabled_checkbox.blockSignals(True)
        self.schedule_enabled_checkbox.setChecked(enabled)
        self.schedule_enabled_checkbox.blockSignals(False)

    def set_interval(self, interval_seconds: int):
        """
        Set the interval display.

        Args:
            interval_seconds: Interval in seconds
        """
        self.interval_spinbox.blockSignals(True)
        self.interval_unit_combo.blockSignals(True)

        # Convert seconds to appropriate unit
        if interval_seconds < 60:
            self.interval_unit_combo.setCurrentText("seconds")
            self.interval_spinbox.setValue(interval_seconds)
        elif interval_seconds < 3600:
            self.interval_unit_combo.setCurrentText("minutes")
            self.interval_spinbox.setValue(interval_seconds // 60)
        elif interval_seconds < 86400:
            self.interval_unit_combo.setCurrentText("hours")
            self.interval_spinbox.setValue(interval_seconds // 3600)
        else:
            self.interval_unit_combo.setCurrentText("days")
            self.interval_spinbox.setValue(interval_seconds // 86400)

        self.interval_spinbox.blockSignals(False)
        self.interval_unit_combo.blockSignals(False)


    def _get_interval_seconds(self) -> int:
        """Calculate interval in seconds from current UI state."""
        value = self.interval_spinbox.value()
        unit = self.interval_unit_combo.currentText()

        if unit == "seconds":
            return value
        elif unit == "minutes":
            return value * 60
        elif unit == "hours":
            return value * 3600
        elif unit == "days":
            return value * 86400
        else:
            return 3600  # Default 1 hour

    def _on_table_cell_clicked(self, row: int, column: int):
        """Handle table cell click."""
        # Column 1 is the Schedule column (On/Off)
        if column == 1:
            # Get script name from the first column
            script_item = self.schedule_table.item(row, 0)
            if not script_item:
                return
            script_name = script_item.data(Qt.ItemDataRole.UserRole)
            if not script_name:
                return

            # Toggle the schedule state
            current_state = self._schedule_data.get(script_name, {}).get('enabled', False)
            new_state = not current_state
            logger.debug(f"Toggling schedule for {script_name}: {current_state} -> {new_state}")

            # Update checkbox immediately if this script is selected
            if script_name == self.selected_script:
                self.set_schedule_enabled(new_state)

            # Emit signal for controller to persist the change
            self.schedule_enabled_changed.emit(script_name, new_state)

    def _on_table_selection_changed(self):
        """Handle table row selection."""
        row = self.schedule_table.currentRow()
        if row < 0:
            self.selected_script = None
            self._update_config_panel(None)
            self._refresh_timer.stop()
            return
        item = self.schedule_table.item(row, 0)
        if not item:
            return
        script_name = item.data(Qt.ItemDataRole.UserRole)
        if not script_name:
            return
        self.selected_script = script_name
        logger.debug(f"Selected script: {self.selected_script}")
        self.schedule_info_requested.emit(self.selected_script)
        self._update_config_panel(self.selected_script)
        self._refresh_timer.start(1000)

    def _on_schedule_enabled_changed(self, state):
        """Handle schedule enabled checkbox change."""
        if not self.selected_script:
            return

        enabled = self.schedule_enabled_checkbox.isChecked()
        logger.debug(f"Schedule enabled changed for {self.selected_script}: {enabled}")
        self.schedule_enabled_changed.emit(self.selected_script, enabled)

    def _on_interval_changed(self):
        """Handle interval spinbox change."""
        if not self.selected_script:
            return

        interval_seconds = self._get_interval_seconds()
        logger.debug(f"Interval changed for {self.selected_script}: {interval_seconds}s")
        self.schedule_interval_changed.emit(self.selected_script, interval_seconds)

    def _on_interval_unit_changed(self):
        """Handle interval unit combo change."""
        if not self.selected_script:
            return

        interval_seconds = self._get_interval_seconds()
        logger.debug(f"Interval unit changed for {self.selected_script}: {interval_seconds}s")
        self.schedule_interval_changed.emit(self.selected_script, interval_seconds)

    def _on_run_now_clicked(self):
        """Handle Run Now button click."""
        if not self.selected_script:
            QMessageBox.warning(self, "No Script", "Please select a script first.")
            return

        logger.debug(f"Run Now requested for {self.selected_script}")
        self.run_now_requested.emit(self.selected_script)

    def _update_config_panel(self, script_name: Optional[str]):
        """
        Update configuration panel for selected script.

        This is called by the controller to update the panel state.
        Block signals to prevent signal loops during programmatic updates.
        """
        # Block signals to prevent cascading signal emissions
        widgets = [
            self.schedule_enabled_checkbox,
            self.interval_spinbox,
            self.interval_unit_combo,
            self.run_now_button
        ]

        for widget in widgets:
            widget.blockSignals(True)

        try:
            if not script_name:
                self.schedule_enabled_checkbox.setEnabled(False)
                self.interval_spinbox.setEnabled(False)
                self.interval_unit_combo.setEnabled(False)
                self.run_now_button.setEnabled(False)
            else:
                self.schedule_enabled_checkbox.setEnabled(True)
                self.interval_spinbox.setEnabled(True)
                self.interval_unit_combo.setEnabled(True)
                self.run_now_button.setEnabled(True)
        finally:
            # Always unblock signals
            for widget in widgets:
                widget.blockSignals(False)

    def _refresh_next_run_display(self):
        """Periodically refresh the next run time display (countdown)."""
        if not self.selected_script or self._next_run_timestamp is None:
            return

        import time
        current_time = time.time()
        if current_time >= self._next_run_timestamp:
            return

        # Update the table row with the stored timestamp
        self._update_table_row(self.selected_script)

    def update_schedule_info(self, script_name: str, schedule_info: dict):
        """
        Update schedule information for display.

        Called by controller when schedule state changes.

        Args:
            script_name: Name of the script
            schedule_info: Dictionary with schedule information
        """
        if not script_name:
            return
        if schedule_info is None:
            self._schedule_data.pop(script_name, None)
        else:
            self._schedule_data[script_name] = schedule_info
        self._update_table_row(script_name)

        if script_name == self.selected_script:
            self.set_schedule_enabled(schedule_info.get('enabled', False))
            self.set_interval(schedule_info.get('interval_seconds', 3600))
            self._next_run_timestamp = schedule_info.get('next_run')

    def clear_data(self):
        """Clear all schedule data and UI state to prevent memory leaks."""
        try:
            # Stop refresh timer
            if self._refresh_timer:
                self._refresh_timer.stop()

            # Clear table
            if self.schedule_table:
                self.schedule_table.clearContents()
                self.schedule_table.setRowCount(0)

            # Clear data structures
            self.script_list.clear()
            self._display_name_map.clear()
            self._schedule_data.clear()
            self._row_lookup.clear()
            self.selected_script = None
            self._next_run_timestamp = None

            logger.debug("ScheduleView data cleared")
        except Exception as e:
            logger.error(f"Error clearing ScheduleView data: {e}")
