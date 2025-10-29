"""
Update Dialog - UI for displaying update information and download progress.

This view shows available updates and allows users to download and install them.
"""
import logging
from typing import Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QProgressBar, QGroupBox, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

logger = logging.getLogger('Views.UpdateDialog')


class UpdateDialog(QDialog):
    """
    Dialog for displaying update information and handling installation.

    Shows version information, release notes, and download progress.
    Emits signals for user actions (update, skip, later).
    """

    # Signals
    update_now_clicked = pyqtSignal()
    remind_later_clicked = pyqtSignal()
    skip_version_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self._current_version = ''
        self._latest_version = ''
        self._release_notes = ''
        self._download_size = 0

        # UI components
        self.current_version_label = None
        self.latest_version_label = None
        self.release_notes_text = None
        self.progress_bar = None
        self.progress_label = None
        self.update_button = None
        self.later_button = None
        self.skip_button = None
        self.progress_group = None

        self._init_ui()

        logger.info("UpdateDialog initialized")

    def _init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("Update Available")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setModal(True)
        self.setMinimumSize(500, 400)
        self.resize(600, 500)

        layout = QVBoxLayout(self)

        # Title
        title_label = QLabel("A new version of BindKit is available!")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        # Version information
        version_group = QGroupBox("Version Information")
        version_layout = QVBoxLayout()

        self.current_version_label = QLabel("Current Version: ")
        version_layout.addWidget(self.current_version_label)

        self.latest_version_label = QLabel("Latest Version: ")
        latest_font = QFont()
        latest_font.setBold(True)
        self.latest_version_label.setFont(latest_font)
        version_layout.addWidget(self.latest_version_label)

        version_group.setLayout(version_layout)
        layout.addWidget(version_group)

        # Release notes
        notes_group = QGroupBox("What's New")
        notes_layout = QVBoxLayout()

        self.release_notes_text = QTextEdit()
        self.release_notes_text.setReadOnly(True)
        self.release_notes_text.setMinimumHeight(150)
        notes_layout.addWidget(self.release_notes_text)

        notes_group.setLayout(notes_layout)
        layout.addWidget(notes_group)

        # Download progress (initially hidden)
        self.progress_group = QGroupBox("Download Progress")
        progress_layout = QVBoxLayout()

        self.progress_label = QLabel("Preparing download...")
        progress_layout.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)

        self.progress_group.setLayout(progress_layout)
        self.progress_group.setVisible(False)  # Hidden by default
        layout.addWidget(self.progress_group)

        # Buttons
        button_layout = QHBoxLayout()

        self.skip_button = QPushButton("Skip This Version")
        self.skip_button.clicked.connect(self._on_skip_clicked)
        button_layout.addWidget(self.skip_button)

        button_layout.addStretch()

        self.later_button = QPushButton("Remind Me Later")
        self.later_button.clicked.connect(self._on_later_clicked)
        button_layout.addWidget(self.later_button)

        self.update_button = QPushButton("Update Now")
        self.update_button.setDefault(True)
        self.update_button.clicked.connect(self._on_update_clicked)
        button_layout.addWidget(self.update_button)

        layout.addLayout(button_layout)

    def set_update_info(self, current_version: str, latest_version: str,
                       release_notes: str, download_size: int = 0):
        """
        Set update information to display.

        Args:
            current_version: Current application version
            latest_version: Latest available version
            release_notes: Release notes for the new version
            download_size: Size of download in bytes
        """
        self._current_version = current_version
        self._latest_version = latest_version
        self._release_notes = release_notes
        self._download_size = download_size

        # Update UI
        self.current_version_label.setText(f"Current Version: {current_version}")
        self.latest_version_label.setText(f"Latest Version: {latest_version}")

        # Format release notes (convert markdown to plain text if needed)
        self.release_notes_text.setPlainText(release_notes if release_notes else "No release notes available.")

        # Update button text with size if available
        if download_size > 0:
            size_mb = download_size / (1024 * 1024)
            self.update_button.setText(f"Update Now ({size_mb:.1f} MB)")

        logger.debug(f"Update info set: {current_version} -> {latest_version}")

    def show_download_progress(self):
        """Show download progress UI"""
        self.progress_group.setVisible(True)
        self.update_button.setEnabled(False)
        self.skip_button.setEnabled(False)
        self.later_button.setEnabled(False)
        logger.debug("Download progress shown")

    def hide_download_progress(self):
        """Hide download progress UI"""
        self.progress_group.setVisible(False)
        self.update_button.setEnabled(True)
        self.skip_button.setEnabled(True)
        self.later_button.setEnabled(True)
        logger.debug("Download progress hidden")

    def update_download_progress(self, current: int, total: int):
        """
        Update download progress bar.

        Args:
            current: Current downloaded bytes
            total: Total bytes to download
        """
        if total > 0:
            percentage = int((current / total) * 100)
            self.progress_bar.setValue(percentage)

            # Update label with human-readable sizes
            current_mb = current / (1024 * 1024)
            total_mb = total / (1024 * 1024)
            self.progress_label.setText(f"Downloading: {current_mb:.1f} MB / {total_mb:.1f} MB ({percentage}%)")
        else:
            self.progress_bar.setMaximum(0)  # Indeterminate progress
            self.progress_label.setText("Downloading...")

    def show_download_complete(self):
        """Show download completion state"""
        self.progress_bar.setValue(100)
        self.progress_label.setText("Download complete! Installing...")
        logger.debug("Download complete shown")

    def show_download_error(self, error_message: str):
        """
        Show download error message.

        Args:
            error_message: Error message to display
        """
        self.hide_download_progress()
        QMessageBox.critical(
            self,
            "Download Failed",
            f"Failed to download update:\n\n{error_message}\n\nPlease try again later or download manually from GitHub."
        )
        logger.error(f"Download error shown: {error_message}")

    def _on_update_clicked(self):
        """Handle Update Now button click"""
        logger.info("User clicked 'Update Now'")
        self.update_now_clicked.emit()

    def _on_later_clicked(self):
        """Handle Remind Me Later button click"""
        logger.info("User clicked 'Remind Me Later'")
        self.remind_later_clicked.emit()
        self.reject()  # Close dialog

    def _on_skip_clicked(self):
        """Handle Skip This Version button click"""
        logger.info("User clicked 'Skip This Version'")

        # Confirm before skipping
        reply = QMessageBox.question(
            self,
            "Skip Version",
            f"Are you sure you want to skip version {self._latest_version}?\n\n"
            "You won't be notified about this version again.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.skip_version_clicked.emit()
            self.reject()  # Close dialog

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
