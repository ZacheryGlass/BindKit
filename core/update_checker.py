"""
Update Checker - Checks for and downloads application updates.

This module handles checking GitHub releases for updates,
comparing versions, and downloading installers.
"""
import logging
import os
import tempfile
import requests
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from PyQt6.QtCore import QObject, QThread, pyqtSignal

logger = logging.getLogger('Core.UpdateChecker')

# GitHub repository information
GITHUB_OWNER = "ZacheryGlass"
GITHUB_REPO = "BindKit"
GITHUB_API_BASE = "https://api.github.com"


class UpdateCheckWorker(QThread):
    """Worker thread for checking updates without blocking UI"""

    # Signals
    check_completed = pyqtSignal(bool, dict)  # success, result_data
    check_failed = pyqtSignal(str)  # error_message

    def __init__(self, current_version: str, parent=None):
        super().__init__(parent)
        self.current_version = current_version
        self._is_cancelled = False

    def run(self):
        """Check for updates in background thread"""
        try:
            # Get latest release from GitHub
            url = f"{GITHUB_API_BASE}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
            logger.debug(f"Checking for updates at: {url}")

            headers = {'Accept': 'application/vnd.github.v3+json'}
            response = requests.get(url, headers=headers, timeout=10)

            if self._is_cancelled:
                return

            if response.status_code == 200:
                release_data = response.json()

                # Extract version from tag_name (e.g., "v1.2.3" -> "1.2.3")
                tag_name = release_data.get('tag_name', '')
                latest_version = tag_name.lstrip('v')

                # Compare versions
                if self._compare_versions(self.current_version, latest_version):
                    # Find installer asset
                    installer_asset = self._find_installer_asset(release_data.get('assets', []))

                    if installer_asset:
                        result = {
                            'latest_version': latest_version,
                            'release_notes': release_data.get('body', ''),
                            'download_url': installer_asset['browser_download_url'],
                            'download_size': installer_asset.get('size', 0),
                            'release_date': release_data.get('published_at', '')
                        }
                        self.check_completed.emit(True, result)
                    else:
                        self.check_failed.emit("No installer found in latest release")
                else:
                    # Already on latest version
                    self.check_completed.emit(False, {})

            elif response.status_code == 404:
                self.check_failed.emit("Repository or releases not found")
            elif response.status_code == 403:
                self.check_failed.emit("GitHub API rate limit exceeded")
            else:
                self.check_failed.emit(f"GitHub API error: {response.status_code}")

        except requests.exceptions.Timeout:
            self.check_failed.emit("Connection timeout")
        except requests.exceptions.ConnectionError:
            logger.debug("No internet connection - update check skipped")
            # Silently fail for network issues - don't bother user
            self.check_completed.emit(False, {})
        except Exception as e:
            logger.error(f"Update check failed: {e}")
            self.check_failed.emit(str(e))

    def cancel(self):
        """Cancel the update check"""
        self._is_cancelled = True

    @staticmethod
    def _compare_versions(current: str, latest: str) -> bool:
        """
        Compare two semantic versions.
        Returns True if latest > current, False otherwise.
        """
        try:
            current_parts = tuple(map(int, current.split('.')))
            latest_parts = tuple(map(int, latest.split('.')))
            return latest_parts > current_parts
        except (ValueError, AttributeError):
            logger.warning(f"Invalid version format: current={current}, latest={latest}")
            return False

    @staticmethod
    def _find_installer_asset(assets: list) -> Optional[Dict[str, Any]]:
        """
        Find the installer asset from GitHub release assets.
        Looks for files matching pattern: BindKit-*-Setup.exe
        """
        for asset in assets:
            name = asset.get('name', '')
            if name.startswith('BindKit-') and name.endswith('-Setup.exe'):
                logger.debug(f"Found installer asset: {name}")
                return asset
        return None


class DownloadWorker(QThread):
    """Worker thread for downloading updates without blocking UI"""

    # Signals
    progress = pyqtSignal(int, int)  # current_bytes, total_bytes
    completed = pyqtSignal(str)  # file_path
    failed = pyqtSignal(str)  # error_message

    def __init__(self, download_url: str, version: str, parent=None):
        super().__init__(parent)
        self.download_url = download_url
        self.version = version
        self._is_cancelled = False

    def run(self):
        """Download installer in background thread"""
        try:
            # Create temp directory for update
            temp_dir = Path(tempfile.gettempdir()) / "BindKit-Update"
            temp_dir.mkdir(exist_ok=True)

            # Determine filename from URL
            filename = f"BindKit-{self.version}-Setup.exe"
            file_path = temp_dir / filename

            logger.info(f"Downloading update to: {file_path}")

            # Download with progress tracking
            response = requests.get(self.download_url, stream=True, timeout=30)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0

            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if self._is_cancelled:
                        # Clean up partial download
                        try:
                            f.close()
                            file_path.unlink()
                        except Exception:
                            pass
                        return

                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        self.progress.emit(downloaded_size, total_size)

            # Verify download completed
            if total_size > 0 and downloaded_size != total_size:
                self.failed.emit(f"Download incomplete: {downloaded_size}/{total_size} bytes")
                return

            logger.info(f"Download completed: {file_path}")
            self.completed.emit(str(file_path))

        except requests.exceptions.Timeout:
            self.failed.emit("Download timeout")
        except requests.exceptions.ConnectionError:
            self.failed.emit("Network connection lost")
        except requests.exceptions.HTTPError as e:
            self.failed.emit(f"HTTP error: {e}")
        except Exception as e:
            logger.error(f"Download failed: {e}")
            self.failed.emit(str(e))

    def cancel(self):
        """Cancel the download"""
        self._is_cancelled = True


class UpdateChecker(QObject):
    """
    Main update checker class.

    Coordinates update checking and downloading operations.
    """

    # Signals
    check_started = pyqtSignal()
    check_completed = pyqtSignal(bool, dict)  # success, update_info
    check_failed = pyqtSignal(str)  # error_message
    download_started = pyqtSignal()
    download_progress = pyqtSignal(int, int)  # current, total
    download_completed = pyqtSignal(str)  # file_path
    download_failed = pyqtSignal(str)  # error_message

    def __init__(self, current_version: str, parent=None):
        super().__init__(parent)
        self.current_version = current_version
        self._check_worker = None
        self._download_worker = None

        logger.info(f"UpdateChecker initialized with version: {current_version}")

    def check_for_updates(self):
        """Start checking for updates asynchronously"""
        if self._check_worker and self._check_worker.isRunning():
            logger.warning("Update check already in progress")
            return

        logger.info("Starting update check...")
        self.check_started.emit()

        self._check_worker = UpdateCheckWorker(self.current_version, self)
        self._check_worker.check_completed.connect(self._on_check_completed)
        self._check_worker.check_failed.connect(self._on_check_failed)
        self._check_worker.start()

    def download_update(self, download_url: str, version: str):
        """Start downloading update installer asynchronously"""
        if self._download_worker and self._download_worker.isRunning():
            logger.warning("Download already in progress")
            return

        logger.info(f"Starting download: {download_url}")
        self.download_started.emit()

        self._download_worker = DownloadWorker(download_url, version, self)
        self._download_worker.progress.connect(self.download_progress.emit)
        self._download_worker.completed.connect(self._on_download_completed)
        self._download_worker.failed.connect(self._on_download_failed)
        self._download_worker.start()

    def cancel_check(self):
        """Cancel ongoing update check"""
        if self._check_worker and self._check_worker.isRunning():
            logger.info("Cancelling update check")
            self._check_worker.cancel()
            self._check_worker.wait()

    def cancel_download(self):
        """Cancel ongoing download"""
        if self._download_worker and self._download_worker.isRunning():
            logger.info("Cancelling download")
            self._download_worker.cancel()
            self._download_worker.wait()

    def _on_check_completed(self, update_available: bool, update_info: dict):
        """Handle update check completion"""
        if update_available:
            logger.info(f"Update available: {update_info.get('latest_version')}")
        else:
            logger.info("Already on latest version")
        self.check_completed.emit(update_available, update_info)

    def _on_check_failed(self, error_message: str):
        """Handle update check failure"""
        logger.error(f"Update check failed: {error_message}")
        self.check_failed.emit(error_message)

    def _on_download_completed(self, file_path: str):
        """Handle download completion"""
        logger.info(f"Download completed: {file_path}")
        self.download_completed.emit(file_path)

    def _on_download_failed(self, error_message: str):
        """Handle download failure"""
        logger.error(f"Download failed: {error_message}")
        self.download_failed.emit(error_message)

    @staticmethod
    def launch_installer(installer_path: str) -> bool:
        """
        Launch the installer and return success status.

        Uses Inno Setup silent install flags to run without user interaction
        and automatically close/restart the application.
        """
        try:
            import subprocess

            # Verify installer exists
            if not os.path.exists(installer_path):
                logger.error(f"Installer not found: {installer_path}")
                return False

            # Launch installer with silent flags
            # /SILENT - No prompts, but shows progress window
            # /CLOSEAPPLICATIONS - Automatically close running app
            # /RESTARTAPPLICATIONS - Restart app after install (if was running)
            cmd = [
                installer_path,
                '/SILENT',
                '/CLOSEAPPLICATIONS',
                '/RESTARTAPPLICATIONS'
            ]

            logger.info(f"Launching installer: {' '.join(cmd)}")
            subprocess.Popen(cmd)
            return True

        except Exception as e:
            logger.error(f"Failed to launch installer: {e}")
            return False
