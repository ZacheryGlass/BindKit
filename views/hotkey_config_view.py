"""
Hotkey Configuration View - Pure UI component for hotkey recording.

This view provides a dialog for recording and configuring hotkeys,
with no business logic - only UI display and user input handling.
"""
import logging
from typing import Optional, Set
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QLineEdit, QDialogButtonBox,
                             QMessageBox)
from PyQt6.QtCore import Qt, QObject, pyqtSignal, QEvent
from PyQt6.QtGui import QKeyEvent

logger = logging.getLogger('Views.HotkeyConfig')


# Key codes that are modifiers
MODIFIER_KEYS = {
    Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta,
    Qt.Key.Key_AltGr, Qt.Key.Key_Super_L, Qt.Key.Key_Super_R,
    Qt.Key.Key_Hyper_L, Qt.Key.Key_Hyper_R
}

# Keys that should be ignored
IGNORED_KEYS = {
    Qt.Key.Key_unknown, Qt.Key.Key_Escape
}


class HotkeyRecorderWidget(QLineEdit):
    """Custom line edit widget that records key combinations"""
    
    hotkey_recorded = pyqtSignal(str)  # Emits the hotkey string when recorded
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setPlaceholderText("Click here and press a key combination...")
        
        self.current_modifiers: Set[str] = set()
        self.current_key: Optional[str] = None
        self.recording = False
        
        # Install event filter to capture all key events
        self.installEventFilter(self)
    
    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """Filter and handle key events"""
        if obj == self and self.recording:
            if event.type() == QEvent.Type.KeyPress:
                self.handle_key_press(event)
                return True
            elif event.type() == QEvent.Type.KeyRelease:
                self.handle_key_release(event)
                return True
        
        return super().eventFilter(obj, event)
    
    def handle_key_press(self, event: QKeyEvent):
        """Handle key press events"""
        key = event.key()
        
        # Ignore certain keys
        if key in IGNORED_KEYS:
            return
        
        # Handle Escape to cancel recording
        if key == Qt.Key.Key_Escape:
            self.stop_recording()
            return
        
        # Handle modifiers
        modifiers = event.modifiers()
        self.current_modifiers.clear()
        
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            self.current_modifiers.add('Ctrl')
        if modifiers & Qt.KeyboardModifier.AltModifier:
            self.current_modifiers.add('Alt')
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            self.current_modifiers.add('Shift')
        if modifiers & Qt.KeyboardModifier.MetaModifier:
            self.current_modifiers.add('Win')
        
        # Handle the main key (non-modifier)
        if key not in MODIFIER_KEYS:
            # Get the key name
            if key >= Qt.Key.Key_F1 and key <= Qt.Key.Key_F12:
                # Function keys
                self.current_key = f"F{key - Qt.Key.Key_F1 + 1}"
            elif key >= Qt.Key.Key_0 and key <= Qt.Key.Key_9:
                # Number keys
                self.current_key = chr(key)
            elif key >= Qt.Key.Key_A and key <= Qt.Key.Key_Z:
                # Letter keys
                self.current_key = chr(key)
            else:
                # Special keys
                key_names = {
                    Qt.Key.Key_Space: 'Space',
                    Qt.Key.Key_Tab: 'Tab',
                    Qt.Key.Key_Return: 'Enter',
                    Qt.Key.Key_Enter: 'Enter',
                    Qt.Key.Key_Backspace: 'Backspace',
                    Qt.Key.Key_Delete: 'Delete',
                    Qt.Key.Key_Insert: 'Insert',
                    Qt.Key.Key_Home: 'Home',
                    Qt.Key.Key_End: 'End',
                    Qt.Key.Key_PageUp: 'PageUp',
                    Qt.Key.Key_PageDown: 'PageDown',
                    Qt.Key.Key_Up: 'Up',
                    Qt.Key.Key_Down: 'Down',
                    Qt.Key.Key_Left: 'Left',
                    Qt.Key.Key_Right: 'Right',
                    Qt.Key.Key_Plus: 'Plus',
                    Qt.Key.Key_Minus: 'Minus',
                    Qt.Key.Key_Asterisk: 'Multiply',
                    Qt.Key.Key_Slash: 'Slash',
                    Qt.Key.Key_Period: 'Period',
                    Qt.Key.Key_Comma: 'Comma',
                    Qt.Key.Key_Semicolon: 'Semicolon',
                    Qt.Key.Key_QuoteLeft: 'Grave',
                    Qt.Key.Key_BracketLeft: 'Bracket_Left',
                    Qt.Key.Key_BracketRight: 'Bracket_Right',
                    Qt.Key.Key_Backslash: 'Backslash',
                    Qt.Key.Key_Apostrophe: 'Quote',
                    Qt.Key.Key_Pause: 'Pause',
                    Qt.Key.Key_Print: 'PrintScreen',
                    Qt.Key.Key_ScrollLock: 'ScrollLock',
                    Qt.Key.Key_CapsLock: 'CapsLock',
                    Qt.Key.Key_NumLock: 'NumLock',
                }
                
                self.current_key = key_names.get(key)
                
                if not self.current_key:
                    # Try to get text representation
                    text = event.text()
                    if text and text.isprintable():
                        self.current_key = text.upper()
        
        # Update display
        self.update_display()
    
    def handle_key_release(self, event: QKeyEvent):
        """Handle key release events"""
        # We could potentially use this for more complex handling
        pass
    
    def update_display(self):
        """Update the displayed hotkey combination"""
        parts = []
        
        # Add modifiers in consistent order
        if 'Ctrl' in self.current_modifiers:
            parts.append('Ctrl')
        if 'Alt' in self.current_modifiers:
            parts.append('Alt')
        if 'Shift' in self.current_modifiers:
            parts.append('Shift')
        if 'Win' in self.current_modifiers:
            parts.append('Win')
        
        # Add the main key
        if self.current_key:
            parts.append(self.current_key)
        
        if parts:
            hotkey_string = '+'.join(parts)
            self.setText(hotkey_string)
            self.hotkey_recorded.emit(hotkey_string)
        else:
            self.setText("Press a key combination...")
    
    def start_recording(self):
        """Start recording key combinations"""
        self.recording = True
        self.current_modifiers.clear()
        self.current_key = None
        self.setText("Press a key combination...")
        self.setFocus()
        self.setStyleSheet("background-color: #2a2a2a; border: 2px solid #4a90e2;")
    
    def stop_recording(self):
        """Stop recording key combinations"""
        self.recording = False
        self.setStyleSheet("")
    
    def mousePressEvent(self, event):
        """Handle mouse clicks to start recording"""
        super().mousePressEvent(event)
        if not self.recording:
            self.start_recording()
    
    def focusOutEvent(self, event):
        """Handle focus loss"""
        super().focusOutEvent(event)
        if self.recording:
            self.stop_recording()

    def get_hotkey(self) -> str:
        """Return the currently displayed hotkey string (or empty)."""
        text = self.text().strip()
        return text if text and text != "Press a key combination..." else ""

    def set_hotkey(self, hotkey_string: str):
        """Programmatically set the displayed hotkey string."""
        self.setText(hotkey_string if hotkey_string else "")
        if hotkey_string:
            self.hotkey_recorded.emit(hotkey_string)

    def clear(self):
        """Clear the recorded state and display."""
        self.current_modifiers.clear()
        self.current_key = None
        self.setText("")
        self.setPlaceholderText("Click here and press a key combination...")




class HotkeyConfigView(QDialog):
    """
    View for configuring hotkeys - pure UI component.
    
    This view provides the interface for recording and setting hotkeys
    with no business logic - only UI display and user input handling.
    """
    
    # Signals for controller
    hotkey_set = pyqtSignal(str)  # Emits the new hotkey string
    hotkey_cleared = pyqtSignal()  # Emits when hotkey is cleared
    validation_requested = pyqtSignal(str)  # Request validation of hotkey
    
    def __init__(self, script_name: str, current_hotkey: Optional[str] = None, 
                 parent=None):
        super().__init__(parent)
        self.script_name = script_name
        self.current_hotkey = current_hotkey
        
        self.setWindowTitle(f"Configure Hotkey - {script_name}")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setModal(True)
        self.setMinimumWidth(400)
        
        self.init_ui()
        
        logger.info(f"HotkeyConfigView initialized for script: {script_name}")
    
    def init_ui(self):
        """Initialize the UI components"""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # Header
        header_label = QLabel(f"<b>Set hotkey for:</b> {self.script_name}")
        header_label.setWordWrap(True)
        layout.addWidget(header_label)
        
        # Current hotkey display
        if self.current_hotkey:
            current_label = QLabel(f"Current hotkey: <b>{self.current_hotkey}</b>")
            layout.addWidget(current_label)
        
        # Instructions
        instructions = QLabel(
            "Click in the box below and press your desired key combination.\n"
            "Use Ctrl, Alt, Shift, or Win as modifiers."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("color: #999;")
        layout.addWidget(instructions)
        
        # Hotkey recorder
        self.hotkey_recorder = HotkeyRecorderWidget()
        if self.current_hotkey:
            self.hotkey_recorder.set_hotkey(self.current_hotkey)
        self.hotkey_recorder.hotkey_recorded.connect(self.on_hotkey_recorded)
        layout.addWidget(self.hotkey_recorder)
        
        # Validation label
        self.validation_label = QLabel("")
        self.validation_label.setStyleSheet("color: #ff6b6b;")
        self.validation_label.setVisible(False)
        layout.addWidget(self.validation_label)
        
        # Clear button
        clear_button = QPushButton("Clear Hotkey")
        clear_button.clicked.connect(self.clear_hotkey)
        layout.addWidget(clear_button)
        
        # Button box
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept_hotkey)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.button_box = button_box
    
    def on_hotkey_recorded(self, hotkey_string: str):
        """Handle when a hotkey is recorded"""
        self.validation_requested.emit(hotkey_string)
    
    def show_validation_error(self, message: str):
        """Show a validation error message"""
        self.validation_label.setText(message)
        self.validation_label.setVisible(True)
    
    def show_validation_warning(self, message: str):
        """Show a validation warning message"""
        self.validation_label.setText(message)
        self.validation_label.setStyleSheet("color: #ffa500;")
        self.validation_label.setVisible(True)
    
    def clear_validation(self):
        """Clear any validation messages"""
        self.validation_label.setVisible(False)
        self.validation_label.setStyleSheet("color: #ff6b6b;")
    
    def clear_hotkey(self):
        """Clear the current hotkey"""
        self.hotkey_recorder.clear()
        self.hotkey_cleared.emit()
        self.clear_validation()
    
    def accept_hotkey(self):
        """Accept the configured hotkey"""
        hotkey = self.hotkey_recorder.get_hotkey()
        if hotkey:
            self.hotkey_set.emit(hotkey)
        else:
            self.hotkey_cleared.emit()
        self.accept()
    
    def get_hotkey(self) -> Optional[str]:
        """Get the configured hotkey"""
        hotkey = self.hotkey_recorder.get_hotkey()
        return hotkey if hotkey else None

    def keyPressEvent(self, event):
        """Handle key press events - close on ESC unless hotkey recorder is recording"""
        if event.key() == Qt.Key.Key_Escape:
            # Check if the hotkey recorder is in focus and recording
            if self.hotkey_recorder.recording and self.hotkey_recorder.hasFocus():
                # Let the recorder widget handle ESC (it will cancel recording)
                return
            # Otherwise close the dialog
            self.close()
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event):
        """Close dialog when it loses focus (user clicks outside)"""
        self.close()
        super().focusOutEvent(event)
