"""
Service Runtime - Manages long-running background script processes.

This module provides Windows-native service process management using:
- Detached processes (DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP)
- Win32 Job Objects for complete process tree cleanup
- Log file rotation for stdout/stderr capture
"""

import sys
import os
import subprocess
import logging
import time
import signal
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
from logging.handlers import RotatingFileHandler

# Windows-specific imports
if sys.platform == 'win32':
    import win32job
    import win32api
    import win32con
    import win32process
    import pywintypes
    # Set up Windows signal constants
    signal.CTRL_BREAK_EVENT = win32con.CTRL_BREAK_EVENT

logger = logging.getLogger('Core.ServiceRuntime')


class ServiceState(Enum):
    """Service process states"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"
    CRASHED = "crashed"


@dataclass
class ServiceHandle:
    """Tracks a running service process"""
    script_name: str
    script_path: Path
    process: subprocess.Popen
    pid: int
    start_time: float
    restart_count: int
    log_file_path: Path
    arguments: Dict[str, Any]  # Store original arguments for restart
    log_file: Optional[Any] = None  # File handle for cleanup
    job_handle: Optional[Any] = None  # Win32 job handle
    state: ServiceState = ServiceState.RUNNING


class ServiceRuntime:
    """
    Manages service process lifecycle with Windows Job Objects.

    Features:
    - Windows-native detached process spawning
    - Job Object ensures complete process tree cleanup
    - Stdout/stderr capture with log rotation
    - Graceful and forceful shutdown
    """

    def __init__(self, logs_directory: str = "logs/services"):
        """
        Initialize service runtime.

        Args:
            logs_directory: Directory for service log files
        """
        self.logs_directory = Path(logs_directory)
        self.logs_directory.mkdir(parents=True, exist_ok=True)

        # Track active service handles
        self._active_services: Dict[str, ServiceHandle] = {}

        logger.info(f"ServiceRuntime initialized. Logs: {self.logs_directory.absolute()}")

    def start_service(self, script_name: str, script_path: Path, arguments: Optional[Dict[str, Any]] = None) -> ServiceHandle:
        """
        Start a service process.

        Args:
            script_name: Name of the script (used for logging and tracking)
            script_path: Path to the script file
            arguments: Optional script arguments

        Returns:
            ServiceHandle for the running service

        Raises:
            RuntimeError: If service fails to start
        """
        if script_name in self._active_services:
            raise RuntimeError(f"Service '{script_name}' is already running")

        logger.info(f"Starting service: {script_name}")

        # Set up log file with rotation
        log_file_path = self.logs_directory / f"{script_name}.log"
        log_file = self._open_log_file(log_file_path)

        try:
            # Build command
            cmd = [sys.executable, str(script_path)]

            # Add arguments
            if arguments:
                for arg_name, value in arguments.items():
                    if value is not None and value != "":
                        cmd.extend([f"--{arg_name}", str(value)])

            logger.debug(f"Service command: {' '.join(cmd)}")

            # Windows-specific process creation flags
            creation_flags = 0
            if sys.platform == 'win32':
                # DETACHED_PROCESS: No console window
                # CREATE_NEW_PROCESS_GROUP: Independent process group for clean signals
                # CREATE_NO_WINDOW: Suppress any window creation
                creation_flags = (
                    subprocess.CREATE_NEW_PROCESS_GROUP |
                    subprocess.DETACHED_PROCESS |
                    subprocess.CREATE_NO_WINDOW
                )

            # Start the process
            process = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT,  # Merge stderr into stdout
                stdin=subprocess.DEVNULL,
                creationflags=creation_flags,
                close_fds=False  # Keep log file open
            )

            pid = process.pid
            start_time = time.time()

            logger.info(f"Service '{script_name}' started with PID {pid}")

            # Create Job Object for process tree cleanup (Windows only)
            job_handle = None
            if sys.platform == 'win32':
                job_handle = self._create_job_object(process)
                if job_handle:
                    logger.debug(f"Job Object created for service '{script_name}'")

            # Create service handle
            handle = ServiceHandle(
                script_name=script_name,
                script_path=script_path,
                process=process,
                pid=pid,
                start_time=start_time,
                restart_count=0,
                log_file_path=log_file_path,
                arguments=arguments or {},  # Store arguments for restart
                log_file=log_file,  # Store file handle for cleanup
                job_handle=job_handle,
                state=ServiceState.RUNNING
            )

            self._active_services[script_name] = handle

            return handle

        except Exception as e:
            # Clean up log file on failure
            try:
                log_file.close()
            except Exception:
                pass

            logger.error(f"Failed to start service '{script_name}': {e}")
            raise RuntimeError(f"Failed to start service '{script_name}': {e}")

    def stop_service(self, script_name: str, timeout: int = 10) -> bool:
        """
        Stop a running service.

        Uses graceful shutdown first (CTRL_BREAK_EVENT on Windows), then
        forceful termination via Job Object if needed.

        Args:
            script_name: Name of the service to stop
            timeout: Seconds to wait for graceful shutdown before forceful termination

        Returns:
            True if service was stopped successfully
        """
        if script_name not in self._active_services:
            logger.warning(f"Service '{script_name}' is not running")
            return False

        handle = self._active_services[script_name]
        handle.state = ServiceState.STOPPING

        logger.info(f"Stopping service '{script_name}' (PID {handle.pid})")

        # Check if already terminated
        if handle.process.poll() is not None:
            logger.info(f"Service '{script_name}' already terminated")
            self._cleanup_service(script_name)
            return True

        try:
            if sys.platform == 'win32':
                # Windows: Send CTRL_BREAK_EVENT to process group
                try:
                    # Try graceful shutdown first
                    os.kill(handle.pid, signal.CTRL_BREAK_EVENT)
                    logger.debug(f"Sent CTRL_BREAK_EVENT to service '{script_name}'")
                except (OSError, AttributeError):
                    # If that fails, try terminate
                    handle.process.terminate()
                    logger.debug(f"Sent terminate signal to service '{script_name}'")
            else:
                # Unix: SIGTERM
                handle.process.terminate()

            # Wait for graceful shutdown
            try:
                handle.process.wait(timeout=timeout)
                logger.info(f"Service '{script_name}' stopped gracefully")
                self._cleanup_service(script_name)
                return True
            except subprocess.TimeoutExpired:
                logger.warning(f"Service '{script_name}' did not stop gracefully, forcing termination")

                # Forceful termination
                if sys.platform == 'win32' and handle.job_handle:
                    # Use Job Object to kill entire process tree
                    try:
                        win32job.TerminateJobObject(handle.job_handle, 1)
                        logger.info(f"Terminated Job Object for service '{script_name}'")
                    except Exception as e:
                        logger.error(f"Failed to terminate Job Object: {e}")
                        handle.process.kill()
                else:
                    handle.process.kill()

                handle.process.wait()
                logger.info(f"Service '{script_name}' terminated forcefully")
                self._cleanup_service(script_name)
                return True

        except Exception as e:
            logger.error(f"Error stopping service '{script_name}': {e}")
            self._cleanup_service(script_name)
            return False

    def is_running(self, script_name: str) -> bool:
        """
        Check if a service is currently running.

        Args:
            script_name: Name of the service to check

        Returns:
            True if service is running, False otherwise
        """
        if script_name not in self._active_services:
            return False

        handle = self._active_services[script_name]
        return handle.process.poll() is None

    def get_status(self, script_name: str) -> ServiceState:
        """
        Get current status of a service.

        Args:
            script_name: Name of the service

        Returns:
            ServiceState enum value
        """
        if script_name not in self._active_services:
            return ServiceState.STOPPED

        handle = self._active_services[script_name]

        # Check if process is still running
        if handle.process.poll() is not None:
            # Process has terminated
            if handle.state == ServiceState.STOPPING:
                return ServiceState.STOPPED
            else:
                return ServiceState.CRASHED

        return handle.state

    def get_handle(self, script_name: str) -> Optional[ServiceHandle]:
        """Get service handle by name."""
        return self._active_services.get(script_name)

    def get_all_services(self) -> Dict[str, ServiceHandle]:
        """Get all active service handles."""
        return self._active_services.copy()

    def stop_all_services(self, timeout: int = 10):
        """Stop all running services."""
        logger.info(f"Stopping all services ({len(self._active_services)} active)")

        for script_name in list(self._active_services.keys()):
            try:
                self.stop_service(script_name, timeout)
            except Exception as e:
                logger.error(f"Error stopping service '{script_name}': {e}")

    def _create_job_object(self, process: subprocess.Popen) -> Optional[Any]:
        """
        Create a Windows Job Object and assign the process to it.

        Job Object ensures all child processes are terminated when:
        - The Job Object is closed
        - TerminateJobObject is called
        - The parent application exits

        Args:
            process: The subprocess.Popen object

        Returns:
            Job handle or None on failure
        """
        if sys.platform != 'win32':
            return None

        try:
            # Create Job Object
            job_handle = win32job.CreateJobObject(None, "")

            # Set job limits to terminate all processes when job is closed
            extended_info = win32job.QueryInformationJobObject(
                job_handle, win32job.JobObjectExtendedLimitInformation
            )
            extended_info['BasicLimitInformation']['LimitFlags'] = (
                win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE |
                win32job.JOB_OBJECT_LIMIT_BREAKAWAY_OK
            )
            win32job.SetInformationJobObject(
                job_handle,
                win32job.JobObjectExtendedLimitInformation,
                extended_info
            )

            # Open process handle and assign to job
            process_handle = win32api.OpenProcess(
                win32con.PROCESS_ALL_ACCESS, False, process.pid
            )
            win32job.AssignProcessToJobObject(job_handle, process_handle)
            win32api.CloseHandle(process_handle)

            return job_handle

        except Exception as e:
            logger.warning(f"Failed to create Job Object: {e}")
            return None

    def _open_log_file(self, log_path: Path):
        """
        Open a log file with rotation.

        Args:
            log_path: Path to the log file

        Returns:
            File handle
        """
        # Ensure parent directory exists
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Open in append mode, unbuffered for real-time logging
        return open(log_path, 'a', buffering=1, encoding='utf-8')

    def _cleanup_service(self, script_name: str):
        """Clean up service handle and resources."""
        if script_name not in self._active_services:
            return

        handle = self._active_services[script_name]

        # Close log file handle
        if handle.log_file:
            try:
                handle.log_file.close()
                logger.debug(f"Closed log file for service '{script_name}'")
            except Exception as e:
                logger.warning(f"Error closing log file for '{script_name}': {e}")

        # Close Job Object handle
        if handle.job_handle:
            try:
                win32api.CloseHandle(handle.job_handle)
            except Exception:
                pass

        # Remove from active services
        del self._active_services[script_name]
        handle.state = ServiceState.STOPPED

        logger.debug(f"Cleaned up service '{script_name}'")
