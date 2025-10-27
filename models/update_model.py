"""
Update Model - Manages application update state and information.

This model tracks the update checking process, available updates,
and download progress while remaining UI-agnostic.
"""
import logging
from typing import Optional, Dict, Any
from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger('Models.Update')


class UpdateModel(QObject):
    """
    Model for managing application update state and information.

    Tracks update availability, download progress, and installation state.
    Emits signals when update state changes.
    """

    # Update state: idle, checking, available, downloading, ready_to_install, installing, error
    # Signals emitted when state changes
    update_check_started = pyqtSignal()
    update_check_completed = pyqtSignal(bool)  # success
    update_available = pyqtSignal(dict)  # update info: version, url, notes
    update_not_available = pyqtSignal()
    download_started = pyqtSignal()
    download_progress = pyqtSignal(int, int)  # current, total (bytes)
    download_completed = pyqtSignal(str)  # file path
    download_failed = pyqtSignal(str)  # error message
    installation_started = pyqtSignal()
    check_error = pyqtSignal(str)  # error message

    def __init__(self):
        super().__init__()
        self._state = 'idle'  # idle, checking, available, downloading, ready_to_install
        self._current_version = ''
        self._latest_version = ''
        self._release_notes = ''
        self._download_url = ''
        self._installer_path = ''
        self._download_size = 0
        self._error_message = ''

        logger.info("UpdateModel initialized")

    # State management
    def get_state(self) -> str:
        """Get current update state"""
        return self._state

    def set_state(self, state: str):
        """Set current update state"""
        if self._state != state:
            old_state = self._state
            self._state = state
            logger.debug(f"Update state changed: {old_state} -> {state}")

    def is_checking(self) -> bool:
        """Check if currently checking for updates"""
        return self._state == 'checking'

    def is_available(self) -> bool:
        """Check if update is available"""
        return self._state == 'available'

    def is_downloading(self) -> bool:
        """Check if currently downloading update"""
        return self._state == 'downloading'

    def is_ready_to_install(self) -> bool:
        """Check if update is downloaded and ready to install"""
        return self._state == 'ready_to_install'

    # Version information
    def set_current_version(self, version: str):
        """Set current application version"""
        self._current_version = version
        logger.debug(f"Current version set to: {version}")

    def get_current_version(self) -> str:
        """Get current application version"""
        return self._current_version

    def set_latest_version(self, version: str):
        """Set latest available version"""
        self._latest_version = version
        logger.debug(f"Latest version set to: {version}")

    def get_latest_version(self) -> str:
        """Get latest available version"""
        return self._latest_version

    # Release information
    def set_release_info(self, version: str, notes: str, download_url: str, size: int = 0):
        """Set information about the latest release"""
        self._latest_version = version
        self._release_notes = notes
        self._download_url = download_url
        self._download_size = size
        logger.info(f"Release info set: {version}, URL: {download_url}, Size: {size}")

    def get_release_notes(self) -> str:
        """Get release notes for the latest version"""
        return self._release_notes

    def get_download_url(self) -> str:
        """Get download URL for the latest version"""
        return self._download_url

    def get_download_size(self) -> int:
        """Get expected download size in bytes"""
        return self._download_size

    # Download management
    def set_installer_path(self, path: str):
        """Set path to downloaded installer"""
        self._installer_path = path
        logger.debug(f"Installer path set to: {path}")

    def get_installer_path(self) -> str:
        """Get path to downloaded installer"""
        return self._installer_path

    # Error handling
    def set_error(self, message: str):
        """Set error message and change state"""
        self._error_message = message
        self._state = 'error'
        logger.error(f"Update error: {message}")

    def get_error_message(self) -> str:
        """Get last error message"""
        return self._error_message

    def clear_error(self):
        """Clear error state"""
        self._error_message = ''
        if self._state == 'error':
            self._state = 'idle'

    # Reset state
    def reset(self):
        """Reset model to initial state"""
        self._state = 'idle'
        self._latest_version = ''
        self._release_notes = ''
        self._download_url = ''
        self._installer_path = ''
        self._download_size = 0
        self._error_message = ''
        logger.debug("Update model reset")

    def get_update_info(self) -> Dict[str, Any]:
        """Get all update information as a dictionary"""
        return {
            'state': self._state,
            'current_version': self._current_version,
            'latest_version': self._latest_version,
            'release_notes': self._release_notes,
            'download_url': self._download_url,
            'installer_path': self._installer_path,
            'download_size': self._download_size,
            'error_message': self._error_message
        }
