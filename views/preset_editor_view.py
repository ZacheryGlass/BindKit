"""
Preset Editor View - Pure UI component for script preset configuration.

This view provides a dialog for creating and editing script argument presets,
with no business logic - only UI display and user input handling.
"""
import logging
from typing import Dict, Any, List, Optional
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QLineEdit, QDialogButtonBox,
                             QComboBox, QCheckBox, QSpinBox, QDoubleSpinBox,
                             QFormLayout, QWidget, QScrollArea, QMessageBox)
from PyQt6.QtCore import Qt, pyqtSignal

logger = logging.getLogger('Views.PresetEditor')


class ArgumentWidget(QWidget):
    """Widget for editing a single argument value"""
    
    value_changed = pyqtSignal(str, object)  # arg_name, value
    
    def __init__(self, arg_info: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.arg_name = arg_info['name']
        self.arg_type = arg_info.get('type', 'str')
        self.arg_info = arg_info
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize the UI based on argument type"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Label
        label = QLabel(self.arg_info.get('help', self.arg_name) + ":")
        label.setMinimumWidth(150)
        layout.addWidget(label)
        
        # Create appropriate widget based on type and choices
        if self.arg_info.get('choices'):
            # Use combo box for choices
            self.value_widget = QComboBox()
            self.value_widget.addItems([str(c) for c in self.arg_info['choices']])
            self.value_widget.currentTextChanged.connect(
                lambda text: self.value_changed.emit(self.arg_name, text)
            )
        elif self.arg_type == 'bool':
            # Use checkbox for boolean
            self.value_widget = QCheckBox()
            self.value_widget.stateChanged.connect(
                lambda state: self.value_changed.emit(
                    self.arg_name, 
                    state == Qt.CheckState.Checked.value
                )
            )
        elif self.arg_type == 'int':
            # Use spinbox for integer
            self.value_widget = QSpinBox()
            self.value_widget.setMinimum(-999999)
            self.value_widget.setMaximum(999999)
            self.value_widget.valueChanged.connect(
                lambda value: self.value_changed.emit(self.arg_name, value)
            )
        elif self.arg_type == 'float':
            # Use double spinbox for float
            self.value_widget = QDoubleSpinBox()
            self.value_widget.setMinimum(-999999.0)
            self.value_widget.setMaximum(999999.0)
            self.value_widget.setDecimals(4)
            self.value_widget.valueChanged.connect(
                lambda value: self.value_changed.emit(self.arg_name, value)
            )
        else:
            # Use line edit for string and unknown types
            self.value_widget = QLineEdit()
            self.value_widget.textChanged.connect(
                lambda text: self.value_changed.emit(self.arg_name, text)
            )
        
        layout.addWidget(self.value_widget)
        layout.addStretch()
    
    def set_value(self, value: Any):
        """Set the widget value"""
        if isinstance(self.value_widget, QComboBox):
            index = self.value_widget.findText(str(value))
            if index >= 0:
                self.value_widget.setCurrentIndex(index)
        elif isinstance(self.value_widget, QCheckBox):
            self.value_widget.setChecked(bool(value))
        elif isinstance(self.value_widget, (QSpinBox, QDoubleSpinBox)):
            self.value_widget.setValue(value)
        elif isinstance(self.value_widget, QLineEdit):
            self.value_widget.setText(str(value) if value is not None else "")
    
    def get_value(self) -> Any:
        """Get the widget value"""
        if isinstance(self.value_widget, QComboBox):
            return self.value_widget.currentText()
        elif isinstance(self.value_widget, QCheckBox):
            return self.value_widget.isChecked()
        elif isinstance(self.value_widget, (QSpinBox, QDoubleSpinBox)):
            return self.value_widget.value()
        elif isinstance(self.value_widget, QLineEdit):
            text = self.value_widget.text()
            # Try to convert to appropriate type
            if self.arg_type == 'int':
                try:
                    return int(text) if text else None
                except ValueError:
                    return None
            elif self.arg_type == 'float':
                try:
                    return float(text) if text else None
                except ValueError:
                    return None
            return text if text else None


class PresetEditorView(QDialog):
    """
    Editor for a single preset. Preset selection lives in Settings -> Script Args.
    """

    # Signals for controller
    preset_saved = pyqtSignal(str, dict)  # preset_name, arguments

    def __init__(self, script_name: str, script_args: List[Dict[str, Any]], parent=None,
                 initial_name: Optional[str] = None, initial_args: Optional[Dict[str, Any]] = None):
        super().__init__(parent)
        self.script_name = script_name
        self.script_args = script_args
        self.argument_widgets = {}
        self.initial_name = initial_name
        self.initial_args = initial_args or {}

        self.setWindowTitle(f"Preset Editor - {script_name}")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setModal(True)
        self.setMinimumSize(500, 360)

        self.init_ui()

        logger.info(f"PresetEditorView initialized for script: {script_name}")
    
    def init_ui(self):
        """Initialize the UI components"""
        layout = QVBoxLayout(self)
        
        # Header
        header_label = QLabel(f"<b>Configure preset for:</b> {self.script_name}")
        layout.addWidget(header_label)

        # Single-preset editor
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # Preset name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Preset Name:"))
        self.preset_name_edit = QLineEdit()
        self.preset_name_edit.setPlaceholderText("Enter preset name...")
        name_layout.addWidget(self.preset_name_edit)
        right_layout.addLayout(name_layout)
        
        # Arguments area
        right_layout.addWidget(QLabel("<b>Arguments:</b>"))
        
        # Scroll area for arguments
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        self.args_layout = QVBoxLayout(scroll_widget)
        
        # Create widgets for each argument
        if self.script_args:
            for arg_info in self.script_args:
                arg_widget = ArgumentWidget(arg_info)
                arg_widget.value_changed.connect(self.on_argument_changed)
                self.argument_widgets[arg_info['name']] = arg_widget
                self.args_layout.addWidget(arg_widget)
        else:
            no_args_label = QLabel("This script has no configurable arguments")
            no_args_label.setStyleSheet("color: #999;")
            self.args_layout.addWidget(no_args_label)
        
        self.args_layout.addStretch()
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        right_layout.addWidget(scroll_area)
        
        # Save button for current preset
        save_preset_btn = QPushButton("Save Current Preset")
        save_preset_btn.clicked.connect(self.save_current_preset)
        right_layout.addWidget(save_preset_btn)
        
        layout.addWidget(right_widget)

        # Pre-fill for edit
        if self.initial_name:
            self.preset_name_edit.setText(self.initial_name)
        for arg_name, arg_widget in self.argument_widgets.items():
            if arg_name in self.initial_args:
                arg_widget.set_value(self.initial_args[arg_name])

        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    # No preset selection here; handled by Settings -> Script Args
    
    def on_argument_changed(self, arg_name: str, value: Any):
        """Handle argument value changes"""
        # Could emit signal for real-time updates if needed
        pass
    
    # No local add/delete list; creation is implicit by saving
    
    def save_current_preset(self):
        """Save the current preset"""
        preset_name = self.preset_name_edit.text().strip()
        
        if not preset_name:
            QMessageBox.warning(self, "Invalid Name", 
                              "Please enter a preset name")
            return
        
        # Collect argument values
        arguments = {}
        for arg_name, arg_widget in self.argument_widgets.items():
            value = arg_widget.get_value()
            if value is not None:  # Only save non-None values
                arguments[arg_name] = value
        
        # No local list management in single-preset editor
        
        # Emit signal
        self.preset_saved.emit(preset_name, arguments)
        
        # Close dialog after saving (provides implicit feedback)
        self.accept()
    
    # No local delete/add helpers; handled in Settings tab

    def keyPressEvent(self, event):
        """Handle key press events - close on ESC"""
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event):
        """Close dialog when it loses focus (user clicks outside)"""
        self.close()
        super().focusOutEvent(event)

