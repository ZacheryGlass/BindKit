"""
Schedule View - UI component for configuring scheduled script execution.

Provides interface for:
- Enabling/disabling schedules per-script
- Setting execution intervals
- Viewing last run and next scheduled run times
- Manual execution trigger for testing
"""

import logging
from typing import List, Optional
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QPushButton,
    QSpinBox, QComboBox, QListWidget, QListWidgetItem, QGroupBox,
    QSplitter, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer

logger = logging.getLogger('Views.ScheduleView')


class ScheduleView(QWidget):
    """
    UI for configuring scheduled script execution.

    Signals:
    - schedule_enabled_changed: Emitted when enabling/disabling a schedule
    - schedule_interval_changed: Emitted when interval is changed
    - run_now_requested: Emitted when "Run Now" button is clicked
    """

    schedule_enabled_changed = pyqtSignal(str, bool)  # script_name, enabled
    schedule_interval_changed = pyqtSignal(str, int)  # script_name, interval_seconds
    run_now_requested = pyqtSignal(str)  # script_name

    def __init__(self, parent=None):
        """Initialize the schedule view."""
        super().__init__(parent)
        self.selected_script = None
        self.script_list = []
        self._setup_ui()

    def _setup_ui(self):
        """Set up the UI layout."""
        layout = QHBoxLayout()

        # Left side: Script list
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("Scripts:"))

        self.script_list_widget = QListWidget()
        self.script_list_widget.itemSelectionChanged.connect(self._on_script_selected)
        left_layout.addWidget(self.script_list_widget)

        left_group = QGroupBox("Available Scripts")
        left_group.setLayout(left_layout)

        # Right side: Schedule configuration
        right_layout = QVBoxLayout()

        # Enable/Disable checkbox
        self.schedule_enabled_checkbox = QCheckBox("Enable Schedule")
        self.schedule_enabled_checkbox.stateChanged.connect(self._on_schedule_enabled_changed)
        right_layout.addWidget(self.schedule_enabled_checkbox)

        # Interval configuration
        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("Interval:"))

        self.interval_spinbox = QSpinBox()
        self.interval_spinbox.setMinimum(1)
        self.interval_spinbox.setMaximum(999999)
        self.interval_spinbox.setSingleStep(1)
        self.interval_spinbox.setValue(60)
        self.interval_spinbox.valueChanged.connect(self._on_interval_changed)
        interval_layout.addWidget(self.interval_spinbox)

        self.interval_unit_combo = QComboBox()
        self.interval_unit_combo.addItems(["seconds", "minutes", "hours", "days"])
        self.interval_unit_combo.setCurrentText("minutes")
        self.interval_unit_combo.currentTextChanged.connect(self._on_interval_unit_changed)
        interval_layout.addWidget(self.interval_unit_combo)

        interval_layout.addStretch()
        right_layout.addLayout(interval_layout)

        # Status information
        status_group = QGroupBox("Status")
        status_layout = QVBoxLayout()

        self.last_run_label = QLabel("Last run: Never")
        status_layout.addWidget(self.last_run_label)

        self.next_run_label = QLabel("Next run: Not scheduled")
        status_layout.addWidget(self.next_run_label)

        self.status_label = QLabel("Status: Idle")
        status_layout.addWidget(self.status_label)

        status_group.setLayout(status_layout)
        right_layout.addWidget(status_group)

        # Action buttons
        button_layout = QHBoxLayout()

        self.run_now_button = QPushButton("Run Now")
        self.run_now_button.clicked.connect(self._on_run_now_clicked)
        self.run_now_button.setEnabled(False)
        button_layout.addWidget(self.run_now_button)

        button_layout.addStretch()
        right_layout.addLayout(button_layout)

        right_layout.addStretch()

        right_group = QGroupBox("Configuration")
        right_group.setLayout(right_layout)

        # Use splitter for resizable sections
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_group)
        splitter.addWidget(right_group)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        layout.addWidget(splitter)
        self.setLayout(layout)

    def set_available_scripts(self, scripts: List[dict]):
        """
        Set the list of available scripts.

        Args:
            scripts: List of script info dicts with keys: name, display_name
        """
        self.script_list = scripts
        self.script_list_widget.clear()

        for script in scripts:
            display_name = script.get('display_name', script.get('name', ''))
            item = QListWidgetItem(display_name)
            item.setData(Qt.ItemDataRole.UserRole, script.get('name'))  # Store original name
            self.script_list_widget.addItem(item)

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

    def set_last_run(self, timestamp: Optional[float]):
        """Set the last run time display."""
        if timestamp is None:
            self.last_run_label.setText("Last run: Never")
        else:
            dt = datetime.fromtimestamp(timestamp)
            self.last_run_label.setText(f"Last run: {dt.strftime('%Y-%m-%d %H:%M:%S')}")

    def set_next_run(self, timestamp: Optional[float]):
        """Set the next run time display."""
        if timestamp is None:
            self.next_run_label.setText("Next run: Not scheduled")
        else:
            dt = datetime.fromtimestamp(timestamp)
            self.next_run_label.setText(f"Next run: {dt.strftime('%Y-%m-%d %H:%M:%S')}")

    def set_status(self, status: str):
        """Set the status display."""
        self.status_label.setText(f"Status: {status}")

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

    def _on_script_selected(self):
        """Handle script selection."""
        items = self.script_list_widget.selectedItems()
        if not items:
            self.selected_script = None
            self._update_config_panel(None)
            return

        item = items[0]
        self.selected_script = item.data(Qt.ItemDataRole.UserRole)
        logger.debug(f"Selected script: {self.selected_script}")

        # This should be updated by the controller
        self._update_config_panel(self.selected_script)

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

    def update_schedule_info(self, script_name: str, schedule_info: dict):
        """
        Update schedule information for display.

        Called by controller when schedule state changes.

        Args:
            script_name: Name of the script
            schedule_info: Dictionary with schedule information
        """
        if script_name != self.selected_script:
            return

        self.set_schedule_enabled(schedule_info.get('enabled', False))
        self.set_interval(schedule_info.get('interval_seconds', 3600))
        self.set_last_run(schedule_info.get('last_run'))
        self.set_next_run(schedule_info.get('next_run'))
        self.set_status(schedule_info.get('status', 'Idle'))
