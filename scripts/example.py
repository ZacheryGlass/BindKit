#!/usr/bin/env python3
import sys
import json
from PyQt6.QtWidgets import QMessageBox, QApplication

def main():
    # Get or create QApplication instance
    # When run via FUNCTION_CALL (on main thread), the app already exists
    # When run via SUBPROCESS or if needed, create a new one
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    # Create and show message box
    msg = QMessageBox()
    msg.setWindowTitle("Example Script")
    msg.setText("Hello from BindKit!")
    msg.setIcon(QMessageBox.Icon.Information)
    msg.exec()

    # Return success result in JSON format
    return {
        "success": True,
        "message": "Popup displayed successfully"
    }

if __name__ == "__main__":
    print(json.dumps(main()))