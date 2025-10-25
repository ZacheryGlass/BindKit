"""
Schedule View - UI component for configuring scheduled script execution.

This view now focuses on surfacing schedule status at a glance with:
- Summary banner counts
- Search + filter controls
- A table that lists every script with its schedule state
- A detail panel for editing the selected schedule
"""

import logging
import time
from datetime import datetime
from typing import Dict, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QBrush
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QPushButton,
    QSpinBox, QComboBox, QGroupBox, QSplitter, QMessageBox, QLineEdit,
    QToolButton, QButtonGroup, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QSizePolicy, QFrame
)

logger = logging.getLogger('Views.ScheduleView')


class ScheduleView(QWidget):
    """UI for configuring and monitoring scheduled script execution."""

    schedule_enabled_changed = pyqtSignal(str, bool)  # script_name, enabled
    schedule_interval_changed = pyqtSignal(str, int)  # script_name, interval_seconds
    run_now_requested = pyqtSignal(str)  # script_name
    schedule_info_requested = pyqtSignal(str)  # script_name

    def __init__(self, parent=None):
        super().__init__(parent)

        self.selected_script: Optional[str] = None
        self.script_list: List[dict] = []
        self._display_name_map: Dict[str, str] = {}
        self._schedule_data: Dict[str, dict] = {}
        self._row_lookup: Dict[str, int] = {}
        self._active_filter = 'all'
        self._next_run_timestamp: Optional[float] = None

        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self._refresh_next_run_display)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        header_frame = QFrame()
        header_frame.setObjectName("overviewFrame")
        header_frame.setSizePolicy(
            QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        )
        header_frame.setFrameShape(QFrame.Shape.StyledPanel)
        header_frame.setFrameShadow(QFrame.Shadow.Plain)
        header_frame.setStyleSheet(
            "#overviewFrame {"
            " border: 1px solid rgba(255, 255, 255, 0.08);"
            " border-radius: 8px;"
            " }"
        )

        overview_layout = QVBoxLayout(header_frame)
        overview_layout.setContentsMargins(12, 8, 12, 8)
        overview_layout.setSpacing(8)

        overview_row = QHBoxLayout()
        overview_row.setContentsMargins(0, 0, 0, 0)
        title_label = QLabel("Schedule Overview")
        title_label.setStyleSheet("font-weight: bold;")
        overview_row.addWidget(title_label)
        self.summary_label = QLabel("Load scripts to view schedules.")
        self.summary_label.setObjectName("summaryLabel")
        self.summary_label.setStyleSheet("color: #aeb4c2;")
        overview_row.addWidget(self.summary_label, 1)
        overview_row.addStretch()
        overview_layout.addLayout(overview_row)

        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(0, 0, 0, 0)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search scripts...")
        self.search_input.textChanged.connect(self._on_search_changed)
        controls_layout.addWidget(self.search_input, 1)

        filter_layout = QHBoxLayout()
        self.filter_group = QButtonGroup(self)
        self.filter_buttons: Dict[str, QToolButton] = {}
        for key, label in [
            ('all', 'All'),
            ('enabled', 'Enabled'),
            ('disabled', 'Disabled'),
            ('errors', 'Errors')
        ]:
            btn = QToolButton()
            btn.setText(label)
            btn.setCheckable(True)
            btn.setAutoExclusive(True)
            if key == 'all':
                btn.setChecked(True)
            btn.clicked.connect(lambda checked, k=key: self._on_filter_changed(k))
            self.filter_group.addButton(btn)
            self.filter_buttons[key] = btn
            filter_layout.addWidget(btn)
        filter_layout.addStretch()
        controls_layout.addLayout(filter_layout, 2)
        overview_layout.addLayout(controls_layout)
        layout.addWidget(header_frame)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        table_container = QWidget()
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_header = QLabel("Scheduled Scripts")
        table_header.setStyleSheet("font-weight: bold;")
        table_layout.addWidget(table_header)

        self.schedule_table = QTableWidget(0, 7)
        self.schedule_table.setHorizontalHeaderLabels([
            "Script", "Schedule", "Interval", "Last run", "Next run", "Status", "Actions"
        ])
        self.schedule_table.verticalHeader().setVisible(False)
        self.schedule_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.schedule_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.schedule_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.schedule_table.setAlternatingRowColors(True)
        self.schedule_table.itemSelectionChanged.connect(self._on_table_selection_changed)

        header = self.schedule_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 7):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)

        table_layout.addWidget(self.schedule_table)
        splitter.addWidget(table_container)

        detail_container = QWidget()
        detail_layout = QVBoxLayout(detail_container)
        detail_layout.setContentsMargins(16, 0, 0, 0)

        header_layout = QHBoxLayout()
        self.detail_title_label = QLabel("Select a script to view details")
        self.detail_title_label.setStyleSheet("font-size: 15px; font-weight: bold;")
        header_layout.addWidget(self.detail_title_label)
        header_layout.addStretch()
        self.status_chip = QLabel("Idle")
        self.status_chip.setObjectName("statusChip")
        header_layout.addWidget(self.status_chip)
        detail_layout.addLayout(header_layout)

        self.detail_hint_label = QLabel("Pick a script from the table to inspect or edit its schedule.")
        self.detail_hint_label.setWordWrap(True)
        detail_layout.addWidget(self.detail_hint_label)

        self.schedule_enabled_checkbox = QCheckBox("Enable schedule")
        self.schedule_enabled_checkbox.stateChanged.connect(self._on_schedule_enabled_changed)

        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("Interval:"))
        self.interval_spinbox = QSpinBox()
        self.interval_spinbox.setMinimum(1)
        self.interval_spinbox.setMaximum(999999)
        self.interval_spinbox.setValue(60)
        self.interval_spinbox.valueChanged.connect(self._on_interval_changed)
        interval_layout.addWidget(self.interval_spinbox)

        self.interval_unit_combo = QComboBox()
        self.interval_unit_combo.addItems(["seconds", "minutes", "hours", "days"])
        self.interval_unit_combo.setCurrentText("minutes")
        self.interval_unit_combo.currentTextChanged.connect(self._on_interval_unit_changed)
        interval_layout.addWidget(self.interval_unit_combo)
        interval_layout.addStretch()

        controls_group = QGroupBox("Schedule Controls")
        controls_inner = QVBoxLayout()
        controls_inner.addWidget(self.schedule_enabled_checkbox)
        controls_inner.addLayout(interval_layout)
        controls_group.setLayout(controls_inner)
        detail_layout.addWidget(controls_group)

        status_group = QGroupBox("Status")
        status_layout = QVBoxLayout()
        self.last_run_label = QLabel("Last run: Never")
        status_layout.addWidget(self.last_run_label)
        self.next_run_label = QLabel("Next run: Not scheduled")
        status_layout.addWidget(self.next_run_label)
        self.status_label = QLabel("Status: Idle")
        status_layout.addWidget(self.status_label)
        status_group.setLayout(status_layout)
        detail_layout.addWidget(status_group)

        action_layout = QHBoxLayout()
        self.run_now_button = QPushButton("Run Now")
        self.run_now_button.clicked.connect(self._on_run_now_clicked)
        self.run_now_button.setEnabled(False)
        action_layout.addWidget(self.run_now_button)
        action_layout.addStretch()
        detail_layout.addLayout(action_layout)

        detail_layout.addStretch()
        splitter.addWidget(detail_container)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        layout.addWidget(splitter)

        self._update_config_panel(None)
        self._set_status_chip("Idle", 'disabled')

    def set_available_scripts(self, scripts: List[dict]):
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
        self._update_detail_panel(None)
        self._apply_filters()
        self._update_summary_banner()

    def _populate_row_base(self, row: int, script: dict):
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
            (4, Qt.AlignmentFlag.AlignLeft),
            (5, Qt.AlignmentFlag.AlignLeft)
        ]:
            item = self._create_table_item("-", alignment)
            self.schedule_table.setItem(row, column, item)

        action_btn = QPushButton("Run")
        action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        action_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        action_btn.clicked.connect(lambda checked=False, s=script_name: self._on_row_run_clicked(s))
        self.schedule_table.setCellWidget(row, 6, action_btn)

    def _create_table_item(self, text: str, alignment: Qt.AlignmentFlag) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        item.setTextAlignment(alignment | Qt.AlignmentFlag.AlignVCenter)
        return item

    def _ensure_table_item(self, row: int, column: int, alignment: Qt.AlignmentFlag) -> QTableWidgetItem:
        item = self.schedule_table.item(row, column)
        if not item:
            item = self._create_table_item('', alignment)
            self.schedule_table.setItem(row, column, item)
        item.setTextAlignment(alignment | Qt.AlignmentFlag.AlignVCenter)
        return item

    def _on_search_changed(self, text: str):
        self._apply_filters()

    def _on_filter_changed(self, filter_key: str):
        self._active_filter = filter_key
        self._apply_filters()

    def _apply_filters(self):
        search_term = self.search_input.text().strip().lower()
        for row in range(self.schedule_table.rowCount()):
            item = self.schedule_table.item(row, 0)
            if not item:
                continue
            script_name = item.data(Qt.ItemDataRole.UserRole) or ''
            display_name = item.text().lower()
            matches_search = True
            if search_term:
                matches_search = search_term in display_name or search_term in script_name.lower()

            matches_filter = self._row_matches_filter(script_name)
            should_show = matches_search and matches_filter
            self.schedule_table.setRowHidden(row, not should_show)

            if not should_show and script_name == self.selected_script:
                self.schedule_table.clearSelection()
                self.selected_script = None
                self._update_detail_panel(None)

    def _row_matches_filter(self, script_name: str) -> bool:
        data = self._schedule_data.get(script_name)
        if self._active_filter == 'all' or not data:
            return True
        if self._active_filter == 'enabled':
            return bool(data.get('enabled'))
        if self._active_filter == 'disabled':
            return not data.get('enabled')
        if self._active_filter == 'errors':
            return self._row_has_error(data)
        return True

    @staticmethod
    def _row_has_error(data: Optional[dict]) -> bool:
        if not data:
            return False
        status = (data.get('status') or '').lower()
        return 'error' in status or 'fail' in status

    def _update_summary_banner(self):
        total = len(self.script_list)
        enabled = sum(1 for data in self._schedule_data.values() if data.get('enabled'))
        errors = sum(1 for data in self._schedule_data.values() if self._row_has_error(data))
        disabled = max(total - enabled, 0)
        self.summary_label.setText(
            f"Scripts: {total} - Scheduled: {enabled} - Idle: {disabled} - Issues: {errors}"
        )

    def _get_display_name(self, script_name: str) -> str:
        return self._display_name_map.get(script_name, script_name)

    def set_schedule_enabled(self, enabled: bool):
        self.schedule_enabled_checkbox.blockSignals(True)
        self.schedule_enabled_checkbox.setChecked(enabled)
        self.schedule_enabled_checkbox.blockSignals(False)

    def set_interval(self, interval_seconds: int):
        interval_seconds = max(interval_seconds, 1)
        self.interval_spinbox.blockSignals(True)
        self.interval_unit_combo.blockSignals(True)

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
        if timestamp is None:
            self.last_run_label.setText("Last run: Never")
        else:
            formatted = self._format_timestamp(timestamp)
            self.last_run_label.setText(f"Last run: {formatted}")

    def set_next_run(self, timestamp: Optional[float]):
        if timestamp is None:
            self.next_run_label.setText("Next run: Not scheduled")
        else:
            formatted = self._format_timestamp(timestamp)
            self.next_run_label.setText(f"Next run: {formatted}")

    def set_status(self, status: str):
        self.status_label.setText(f"Status: {status}")

    @staticmethod
    def _format_interval_display(interval_seconds: Optional[int]) -> str:
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
        dt = datetime.fromtimestamp(timestamp)
        relative = self._format_relative_time(timestamp)
        if relative:
            return f"{dt.strftime('%Y-%m-%d %H:%M:%S')} ({relative})"
        return dt.strftime('%Y-%m-%d %H:%M:%S')

    @staticmethod
    def _format_relative_time(timestamp: float) -> str:
        now = time.time()
        delta = int(timestamp - now)
        if delta == 0:
            return "now"
        ahead = delta > 0
        delta = abs(delta)
        if delta < 60:
            value, unit = delta, 's'
        elif delta < 3600:
            value, unit = delta // 60, 'm'
        elif delta < 86400:
            value, unit = delta // 3600, 'h'
        else:
            value, unit = delta // 86400, 'd'
        return f"in {value}{unit}" if ahead else f"{value}{unit} ago"

    def _get_interval_seconds(self) -> int:
        value = self.interval_spinbox.value()
        unit = self.interval_unit_combo.currentText()
        if unit == "seconds":
            return value
        if unit == "minutes":
            return value * 60
        if unit == "hours":
            return value * 3600
        if unit == "days":
            return value * 86400
        return 3600

    def _on_table_selection_changed(self):
        row = self.schedule_table.currentRow()
        if row < 0:
            self.selected_script = None
            self._update_detail_panel(None)
            self._refresh_timer.stop()
            return
        item = self.schedule_table.item(row, 0)
        if not item:
            return
        script_name = item.data(Qt.ItemDataRole.UserRole)
        if not script_name:
            return
        self.selected_script = script_name
        self.schedule_info_requested.emit(script_name)
        self._update_detail_panel(script_name)
        self._refresh_timer.start(1000)

    def _on_schedule_enabled_changed(self, state):
        if not self.selected_script:
            return
        enabled = self.schedule_enabled_checkbox.isChecked()
        self.schedule_enabled_changed.emit(self.selected_script, enabled)

    def _on_interval_changed(self):
        if not self.selected_script:
            return
        interval_seconds = self._get_interval_seconds()
        self.schedule_interval_changed.emit(self.selected_script, interval_seconds)

    def _on_interval_unit_changed(self):
        if not self.selected_script:
            return
        interval_seconds = self._get_interval_seconds()
        self.schedule_interval_changed.emit(self.selected_script, interval_seconds)

    def _on_run_now_clicked(self):
        if not self.selected_script:
            QMessageBox.warning(self, "No Script", "Please select a script first.")
            return
        self.run_now_requested.emit(self.selected_script)

    def _on_row_run_clicked(self, script_name: str):
        if not script_name:
            return
        row = self._row_lookup.get(script_name)
        if row is not None:
            self.schedule_table.setCurrentCell(row, 0)
            self.schedule_table.selectRow(row)
        self.run_now_requested.emit(script_name)

    def _update_config_panel(self, script_name: Optional[str]):
        has_selection = bool(script_name)
        widgets = [
            self.schedule_enabled_checkbox,
            self.interval_spinbox,
            self.interval_unit_combo,
            self.run_now_button
        ]
        for widget in widgets:
            widget.setEnabled(has_selection)

        if not has_selection:
            self.detail_title_label.setText("Select a script to view details")
            self.detail_hint_label.setVisible(True)
            self._set_status_chip("Idle", 'disabled')
            self.schedule_enabled_checkbox.setChecked(False)
            self.interval_spinbox.setValue(60)
            self.interval_unit_combo.setCurrentText("minutes")
            self.last_run_label.setText("Last run: Never")
            self.next_run_label.setText("Next run: Not scheduled")
            self.status_label.setText("Status: Idle")
            self.run_now_button.setEnabled(False)
            self._next_run_timestamp = None
        else:
            self.detail_hint_label.setVisible(False)

    def _update_detail_panel(self, script_name: Optional[str]):
        self._update_config_panel(script_name)
        if not script_name:
            return

        display_name = self._get_display_name(script_name)
        self.detail_title_label.setText(display_name)

        data = self._schedule_data.get(script_name)
        if not data:
            self.set_schedule_enabled(False)
            self.set_interval(3600)
            self.set_last_run(None)
            self.set_next_run(None)
            self.set_status("Waiting for schedule data...")
            self._set_status_chip("Pending", 'pending')
            self.run_now_button.setEnabled(True)
            return

        self.set_schedule_enabled(data.get('enabled', False))
        self.set_interval(data.get('interval_seconds', 3600))
        self.set_last_run(data.get('last_run'))
        self.set_next_run(data.get('next_run'))
        status_text = data.get('status', 'Idle')
        self.set_status(status_text)

        chip_state = 'enabled' if data.get('enabled') else 'disabled'
        if self._row_has_error(data):
            chip_state = 'error'
        elif not data.get('enabled') and data.get('configured_enabled'):
            chip_state = 'pending'
        self._set_status_chip(status_text, chip_state)

        self.run_now_button.setEnabled(True)
        self._next_run_timestamp = data.get('next_run')

    def _set_status_chip(self, text: str, state: str):
        palette = {
            'enabled': '#1f7a4a',
            'disabled': '#6e6f78',
            'pending': '#b26a00',
            'error': '#b71c1c'
        }
        color = palette.get(state, '#6e6f78')
        self.status_chip.setText(text or '-')
        self.status_chip.setStyleSheet(
            "QLabel#statusChip {"
            " border-radius: 10px;"
            " padding: 2px 10px;"
            " color: white;"
            f" background-color: {color};"
            " font-weight: bold;"
            " }"
        )

    def _refresh_next_run_display(self):
        if not self.selected_script or self._next_run_timestamp is None:
            return
        current_time = time.time()
        if current_time >= self._next_run_timestamp:
            return
        self.set_next_run(self._next_run_timestamp)

    def _update_table_row(self, script_name: str):
        row = self._row_lookup.get(script_name)
        if row is None:
            return
        data = self._schedule_data.get(script_name, {})

        schedule_item = self._ensure_table_item(row, 1, Qt.AlignmentFlag.AlignCenter)
        enabled = data.get('enabled', False)
        schedule_item.setText('On' if enabled else 'Off')
        schedule_item.setForeground(QBrush(QColor('#1f7a4a' if enabled else '#6e6f78')))

        interval_item = self._ensure_table_item(row, 2, Qt.AlignmentFlag.AlignCenter)
        interval_item.setText(
            data.get('interval_display') or self._format_interval_display(data.get('interval_seconds'))
        )

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

        status_item = self._ensure_table_item(row, 5, Qt.AlignmentFlag.AlignLeft)
        status_text = data.get('status', 'Idle')
        status_item.setText(status_text)
        if self._row_has_error(data):
            status_item.setForeground(QBrush(QColor('#b71c1c')))
        else:
            status_item.setForeground(QBrush(QColor('#222222')))

    def update_schedule_info(self, script_name: str, schedule_info: dict):
        if not script_name:
            return
        if schedule_info is None:
            self._schedule_data.pop(script_name, None)
        else:
            self._schedule_data[script_name] = schedule_info
        self._update_table_row(script_name)
        if script_name == self.selected_script:
            self._update_detail_panel(script_name)
        self._update_summary_banner()
        self._apply_filters()

