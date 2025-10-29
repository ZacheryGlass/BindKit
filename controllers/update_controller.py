"""
Update Controller - Coordinates update checking and installation.

This controller manages the interaction between UpdateModel, UpdateChecker,
and UpdateDialog to handle the update process.
"""
import logging
import os
from pathlib import Path
from typing import Optional
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication

from models.update_model import UpdateModel
from core.update_checker import UpdateChecker
from views.update_dialog import UpdateDialog
from core.settings import SettingsManager

logger = logging.getLogger('Controllers.Update')


class UpdateController(QObject):
    """
    Controller for managing application updates.

    Coordinates between update model, checker, and dialog to provide
    a complete update experience.
    """

    # Signals
    update_check_started = pyqtSignal()
    update_available = pyqtSignal(str)  # version
    update_not_available = pyqtSignal()
    installation_started = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        # Get current version
        self._current_version = self._read_version_file()

        # Initialize components
        self._model = UpdateModel()
        self._model.set_current_version(self._current_version)

        self._checker = UpdateChecker(self._current_version)
        self._settings = SettingsManager()

        self._dialog = None  # Created on demand

        # Connect signals
        self._connect_signals()

        logger.info(f"UpdateController initialized (version {self._current_version})")

    def _connect_signals(self):
        """Connect signals between components"""
        # Checker -> Model signals
        self._checker.check_started.connect(self._on_check_started)
        self._checker.check_completed.connect(self._on_check_completed)
        self._checker.check_failed.connect(self._on_check_failed)

        # Download signals
        self._checker.download_started.connect(self._on_download_started)
        self._checker.download_progress.connect(self._on_download_progress)
        self._checker.download_completed.connect(self._on_download_completed)
        self._checker.download_failed.connect(self._on_download_failed)

    def check_for_updates(self, show_dialog_if_available: bool = True):
        """
        Check for available updates.

        Args:
            show_dialog_if_available: If True, show update dialog when update is found
        """
        # Check if updates are enabled
        if not self._is_update_check_enabled():
            logger.info("Update checks are disabled in settings")
            return

        # Don't check if already checking
        if self._model.is_checking():
            logger.debug("Update check already in progress")
            return

        logger.info("Checking for updates...")
        self._model.set_state('checking')
        self._show_dialog = show_dialog_if_available
        self._checker.check_for_updates()

    def _on_check_started(self):
        """Handle update check start"""
        logger.debug("Update check started")
        self._model.update_check_started.emit()
        self.update_check_started.emit()

    def _on_check_completed(self, update_available: bool, update_info: dict):
        """Handle update check completion"""
        if update_available:
            latest_version = update_info.get('latest_version', '')

            # Check if this version is skipped
            if self._is_version_skipped(latest_version):
                logger.info(f"Version {latest_version} is skipped by user")
                self._model.set_state('idle')
                return

            # Update model with release info
            self._model.set_release_info(
                version=latest_version,
                notes=update_info.get('release_notes', ''),
                download_url=update_info.get('download_url', ''),
                size=update_info.get('download_size', 0)
            )
            self._model.set_state('available')
            self._model.update_available.emit(update_info)
            self.update_available.emit(latest_version)

            # Show dialog if requested
            if self._show_dialog:
                self._show_update_dialog()
        else:
            logger.info("No updates available")
            self._model.set_state('idle')
            self._model.update_not_available.emit()
            self.update_not_available.emit()

    def _on_check_failed(self, error_message: str):
        """Handle update check failure"""
        logger.error(f"Update check failed: {error_message}")
        self._model.set_error(error_message)
        self._model.check_error.emit(error_message)

    def _show_update_dialog(self):
        """Show the update dialog with current update information"""
        if not self._model.is_available():
            return

        # Create dialog if needed
        if not self._dialog:
            self._dialog = UpdateDialog()
            self._dialog.update_now_clicked.connect(self._on_update_now)
            self._dialog.skip_version_clicked.connect(self._on_skip_version)

        # Set update information
        self._dialog.set_update_info(
            current_version=self._model.get_current_version(),
            latest_version=self._model.get_latest_version(),
            release_notes=self._model.get_release_notes(),
            download_size=self._model.get_download_size()
        )

        # Show dialog
        logger.info("Showing update dialog")
        self._dialog.show()
        self._dialog.raise_()
        self._dialog.activateWindow()

    def _on_update_now(self):
        """Handle user clicking 'Update Now' button"""
        logger.info("User initiated update installation")

        if not self._model.is_available():
            logger.warning("No update available to install")
            return

        # Start download
        download_url = self._model.get_download_url()
        latest_version = self._model.get_latest_version()

        if not download_url:
            logger.error("Download URL not available")
            if self._dialog:
                self._dialog.show_download_error("Download URL not available")
            return

        self._model.set_state('downloading')
        self._checker.download_update(download_url, latest_version)

    def _on_skip_version(self):
        """Handle user skipping a version"""
        latest_version = self._model.get_latest_version()
        logger.info(f"User skipped version: {latest_version}")

        # Add to skipped versions
        skipped = self._settings.get('behavior/skipped_versions', [])
        if latest_version not in skipped:
            skipped.append(latest_version)
            self._settings.set('behavior/skipped_versions', skipped)

        # Reset model
        self._model.reset()

    def _on_download_started(self):
        """Handle download start"""
        logger.debug("Download started")
        if self._dialog:
            self._dialog.show_download_progress()
        self._model.download_started.emit()

    def _on_download_progress(self, current: int, total: int):
        """Handle download progress update"""
        if self._dialog:
            self._dialog.update_download_progress(current, total)
        self._model.download_progress.emit(current, total)

    def _on_download_completed(self, file_path: str):
        """Handle download completion"""
        logger.info(f"Download completed: {file_path}")

        self._model.set_installer_path(file_path)
        self._model.set_state('ready_to_install')

        if self._dialog:
            self._dialog.show_download_complete()

        self._model.download_completed.emit(file_path)

        # Launch installer
        self._install_update(file_path)

    def _on_download_failed(self, error_message: str):
        """Handle download failure"""
        logger.error(f"Download failed: {error_message}")

        if self._dialog:
            self._dialog.show_download_error(error_message)

        self._model.set_state('available')  # Return to available state
        self._model.download_failed.emit(error_message)

    def _install_update(self, installer_path: str):
        """
        Install the update by launching the installer.

        Args:
            installer_path: Path to the downloaded installer
        """
        logger.info("Installing update...")
        self._model.set_state('installing')
        self._model.installation_started.emit()
        self.installation_started.emit()

        # Launch installer
        success = self._checker.launch_installer(installer_path)

        if success:
            logger.info("Installer launched successfully - application will exit")

            # Close the dialog
            if self._dialog:
                self._dialog.accept()

            # Give installer a moment to start
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(500, self._quit_application)
        else:
            logger.error("Failed to launch installer")
            if self._dialog:
                self._dialog.show_download_error("Failed to launch installer")
            self._model.set_state('ready_to_install')

    def _quit_application(self):
        """Quit the application to allow installer to proceed"""
        logger.info("Quitting application for update installation")
        QApplication.instance().quit()

    def _is_update_check_enabled(self) -> bool:
        """Check if automatic update checks are enabled"""
        return self._settings.get('behavior/check_for_updates', True)

    def _is_version_skipped(self, version: str) -> bool:
        """Check if a version has been skipped by the user"""
        skipped = self._settings.get('behavior/skipped_versions', [])
        return version in skipped

    @staticmethod
    def _read_version_file() -> str:
        """Read current version from VERSION file"""
        try:
            version_file = Path(__file__).parent.parent / 'VERSION'
            if version_file.exists():
                version = version_file.read_text().strip()
                logger.debug(f"Read version from file: {version}")
                return version
            else:
                logger.warning("VERSION file not found")
                return "0.0.0"
        except Exception as e:
            logger.error(f"Failed to read VERSION file: {e}")
            return "0.0.0"

    def get_model(self) -> UpdateModel:
        """Get the update model"""
        return self._model

    def cleanup(self):
        """Clean up resources"""
        # Cancel any ongoing operations
        self._checker.cancel_check()
        self._checker.cancel_download()

        # Close dialog
        if self._dialog:
            self._dialog.reject()
            self._dialog = None

        logger.info("UpdateController cleaned up")
